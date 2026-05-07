import pandas as pd
import numpy as np
import requests
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class PriceExtremesAnalyzer:
    def __init__(self):
        pass

    def calculate_support_resistance(self, prices: np.ndarray, window: int = 20) -> Tuple[List[Tuple], List[Tuple]]:
        supports = []
        resistances = []
        if len(prices) < window * 2 + 1:
            return supports, resistances
        for i in range(window, len(prices) - window):
            if prices[i] == min(prices[i-window:i+window+1]) and prices[i] != prices[i-1] and prices[i] != prices[i+1]:
                supports.append((i, prices[i]))
            if prices[i] == max(prices[i-window:i+window+1]) and prices[i] != prices[i-1] and prices[i] != prices[i+1]:
                resistances.append((i, prices[i]))
        return supports, resistances

    def find_swing_high_low(self, df: pd.DataFrame, lookback_period: int = 5) -> pd.DataFrame:
        df = df.copy()
        df['swing_high'] = False
        df['swing_low'] = False
        if len(df) <= lookback_period * 2:
            return df
        for i in range(lookback_period, len(df) - lookback_period):
            is_low = True
            current_low = df['low'].iloc[i]
            for j in range(1, lookback_period + 1):
                if current_low >= df['low'].iloc[i-j] or current_low >= df['low'].iloc[i+j]:
                    is_low = False
                    break
            df.loc[df.index[i], 'swing_low'] = is_low

            is_high = True
            current_high = df['high'].iloc[i]
            for j in range(1, lookback_period + 1):
                if current_high <= df['high'].iloc[i-j] or current_high <= df['high'].iloc[i+j]:
                    is_high = False
                    break
            df.loc[df.index[i], 'swing_high'] = is_high
        return df

    def get_binance_data(self, symbol: str, interval: str, limit: int = 500) -> Optional[pd.DataFrame]:
        url = f"https://api.binance.com/api/v3/klines"
        params = {'symbol': symbol.upper(), 'interval': interval, 'limit': limit}
        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code != 200:
                return None
            data = resp.json()
            if not data:
                return None
            df = pd.DataFrame(data, columns=[
                'open_time', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df.set_index('open_time', inplace=True)
            return df
        except Exception as e:
            logger.error(f"Error fetching {symbol} {interval}: {e}")
            return None

    def atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        high, low, close = df['high'], df['low'], df['close']
        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs()
        ], axis=1).max(axis=1)
        return tr.ewm(span=period, adjust=False).mean()

    def vwap(self, df: pd.DataFrame) -> pd.Series:
        df = df.copy()
        df['date'] = df.index.date
        cum_vol = df.groupby('date')['volume'].cumsum()
        cum_pv = (df['close'] * df['volume']).groupby(df['date']).cumsum()
        return cum_pv / cum_vol

    def fibonacci_retracement(self, high: float, low: float) -> Dict[str, float]:
        diff = high - low
        return {
            '0': low,
            '0.236': low + 0.236 * diff,
            '0.382': low + 0.382 * diff,
            '0.5': low + 0.5 * diff,
            '0.618': low + 0.618 * diff,
            '0.786': low + 0.786 * diff,
            '1': high
        }

    def analyze_extremes(self, df: pd.DataFrame, lookback: int = 5, window: int = 20) -> Optional[Dict]:
        min_points = max(lookback * 2 + 1, window * 2 + 1)
        if df is None or len(df) < min_points:
            return None
        try:
            df_swings = self.find_swing_high_low(df, lookback)
            prices = df['close'].values
            supports, resistances = self.calculate_support_resistance(prices, window)
            atr_series = self.atr(df, 14)
            vwap_series = self.vwap(df)
            last_atr = atr_series.iloc[-1]
            last_vwap = vwap_series.iloc[-1]

            swing_highs = df_swings[df_swings['swing_high']]
            swing_lows = df_swings[df_swings['swing_low']]
            fib_levels = {}
            if not swing_highs.empty and not swing_lows.empty:
                last_high = swing_highs['high'].iloc[-1]
                last_low = swing_lows['low'].iloc[-1]
                fib_levels = self.fibonacci_retracement(last_high, last_low)
            elif not swing_highs.empty and len(swing_highs) >= 2:
                last_high = swing_highs['high'].iloc[-1]
                previous_high = swing_highs['high'].iloc[-2]
                last_low = df['low'][last_high.name:].min()  # aproximado
                fib_levels = self.fibonacci_retracement(last_high, last_low)

            return {
                'swing_highs': swing_highs[['high']],
                'swing_lows': swing_lows[['low']],
                'supports': [(df.index[i], price) for i, price in supports],
                'resistances': [(df.index[i], price) for i, price in resistances],
                'current_price': df['close'].iloc[-1],
                'atr': last_atr,
                'vwap': last_vwap,
                'fibonacci': fib_levels,
                'df_swings': df_swings,
                'df': df
            }
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            return None
