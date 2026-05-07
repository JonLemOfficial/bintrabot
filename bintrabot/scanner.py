import asyncio
import aiohttp
import pandas as pd
from typing import List, Dict, Optional
from analyzer import PriceExtremesAnalyzer
from telegram_alerts import enviar_alerta_tg
import logging
from telegram.error import TelegramError

logger = logging.getLogger(__name__)

class FuturesScanner:
    def __init__(self, analyzer: PriceExtremesAnalyzer, chat_id: str, bot_token: str):
        self.analyzer = analyzer
        self.chat_id = chat_id
        self.bot_token = bot_token
        self.base_url = "https://fapi.binance.com"
        self.active_alerts = {}  # para control de repeticiones
        self.alert_send_semaphore = asyncio.Semaphore(2)

    async def fetch_json(self, session, endpoint, params=None):
        url = f"{self.base_url}{endpoint}"
        async with session.get(url, params=params) as resp:
            if resp.status == 200:
                return await resp.json()
            logger.error(f"Error fetching {url}: {resp.status}")
            return None

    async def get_usdt_futures_symbols(self, session) -> List[str]:
        data = await self.fetch_json(session, "/fapi/v1/exchangeInfo")
        if not data:
            return []
        symbols = []
        for s in data['symbols']:
            if s['quoteAsset'] == 'USDT' and s['status'] == 'TRADING' and s['contractType'] == 'PERPETUAL':
                symbols.append(s['symbol'])
        return symbols

    async def get_klines(self, session, symbol: str, interval: str, limit: int = 200) -> pd.DataFrame:
        endpoint = "/fapi/v1/klines"
        params = {'symbol': symbol, 'interval': interval, 'limit': limit}
        data = await self.fetch_json(session, endpoint, params)
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])
        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col])
        df.set_index('open_time', inplace=True)
        return df

    async def evaluate_pair(self, session, symbol: str) -> None:
        # Obtener datos para 5m, 15m, 4h en paralelo
        tasks = [
            self.get_klines(session, symbol, '5m', 300),
            self.get_klines(session, symbol, '15m', 300),
            self.get_klines(session, symbol, '4h', 400)
        ]
        results = await asyncio.gather(*tasks)
        df_5m, df_15m, df_4h = results

        if df_5m.empty or df_15m.empty or df_4h.empty:
            return

        # Analizar cada timeframe
        anal_5 = self.analyzer.analyze_extremes(df_5m, lookback=5, window=20)
        anal_15 = self.analyzer.analyze_extremes(df_15m, lookback=5, window=20)
        anal_4h = self.analyzer.analyze_extremes(df_4h, lookback=3, window=15)

        if not anal_4h:
            return

        # Confluencia de señal
        signal = self.determine_signal(symbol, anal_5m=anal_5, anal_15m=anal_15, anal_4h=anal_4h)
        if signal:
            if symbol not in self.active_alerts or signal != self.active_alerts[symbol]:
                self.active_alerts[symbol] = signal
                await self.send_alert(symbol, signal, anal_4h, anal_15, anal_5)

    def determine_signal(self, symbol, anal_5m, anal_15m, anal_4h) -> Optional[Dict]:
        """
        Lógica de confluencia:
        - Precio cerca de un soporte/resistencia de 4h (< 0.5 ATR)
        - En 15m se forma un swing bajo/alto que confirma rebote
        - En 5m el volumen actual es > media + desviación
        """
        if not anal_4h or not anal_15m or not anal_5m:
            return None

        price = anal_4h['current_price']
        atr = anal_4h['atr']
        df_4h = anal_4h['df_swings']

        # 1. Zona relevante de 4h
        levels_4h = [p for _, p in anal_4h['supports']] + [p for _, p in anal_4h['resistances']]
        if not levels_4h:
            return None
        nearest_level = min(levels_4h, key=lambda x: abs(x - price))
        if abs(price - nearest_level) > atr * 0.5:
            return None

        # 2. Confirmación en 15m: último swing apunta a rebote desde esa zona
        swing_lows_15 = anal_15m['swing_lows']
        swing_highs_15 = anal_15m['swing_highs']
        if not swing_lows_15.empty and not swing_highs_15.empty:
            last_swing_low_val = swing_lows_15['low'].iloc[-1]
            last_swing_high_val = swing_highs_15['high'].iloc[-1]
        else:
            return None

        # Lado compra: precio rebotando en soporte, último swing low en 15m es más alto que el anterior
        if nearest_level <= price and last_swing_low_val > swing_lows_15['low'].iloc[-2] if len(swing_lows_15) > 1 else False:
            direction = 'LONG'
        # Lado venta: precio en resistencia, último swing high en 15m es más bajo que el anterior
        elif nearest_level >= price and last_swing_high_val < swing_highs_15['high'].iloc[-2] if len(swing_highs_15) > 1 else False:
            direction = 'SHORT'
        else:
            return None

        # 3. Volumen de confirmación en 5m
        df_5m = anal_5m['df']
        if len(df_5m) < 20:
            return None
        avg_vol_5m = df_5m['volume'].rolling(20).mean().iloc[-1]
        current_vol = df_5m['volume'].iloc[-1]
        if current_vol < avg_vol_5m * 1.2:
            return None

        return {
            'direction': direction,
            'entry_zone': nearest_level,
            'current_price': price,
            'stop_loss': price - atr * 1.5 if direction == 'LONG' else price + atr * 1.5,
            'take_profit': price + atr * 3 if direction == 'LONG' else price - atr * 3,
            'atr': atr,
            'vwap': anal_4h['vwap'],
            'fib_levels': anal_4h['fibonacci']
        }

    async def send_alert(self, symbol, signal, anal_4h, anal_15, anal_5):
        # Crear imagen con matplotlib combinando 4h, 15m y 5m
        # Llamar a la función que envía el mensaje de Telegram con la imagen
        try:
            async with self.alert_send_semaphore:
                await enviar_alerta_tg(symbol, signal, anal_4h, anal_15, anal_5, self.chat_id, self.bot_token)
        except TelegramError as exc:
            logger.warning("No se pudo enviar alerta de %s a Telegram: %s", symbol, exc)
        except Exception:
            logger.exception("Error inesperado al enviar alerta de %s", symbol)

    async def run_scan_loop(self):
        async with aiohttp.ClientSession() as session:
            symbols = await self.get_usdt_futures_symbols(session)
            logger.info(f"Escaneando {len(symbols)} futuros USDT-M")
            while True:
                tasks = [self.evaluate_pair(session, sym) for sym in symbols]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for symbol, result in zip(symbols, results):
                    if isinstance(result, Exception):
                        logger.exception("Fallo evaluando %s", symbol, exc_info=result)
                await asyncio.sleep(60)  # esperar 1 minuto entre escaneos