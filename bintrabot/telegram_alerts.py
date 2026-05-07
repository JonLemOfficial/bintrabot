import io
import asyncio
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import json
from telegram import Bot
from telegram.error import TimedOut, NetworkError, RetryAfter
from typing import Dict
import logging

matplotlib.use("Agg")
logger = logging.getLogger(__name__)

async def enviar_alerta_tg(
    symbol: str,
    signal: Dict,
    anal_4h,
    anal_15,
    anal_5,
    chat_id: str,
    bot_token: str
):
    # Crear figura con 3 subplots (4h, 15m, 5m)
    fig, axes = plt.subplots(3, 1, figsize=(12, 14), facecolor='#1e1e1e')
    for ax, anal, title in zip(axes,
                               [anal_4h, anal_15, anal_5],
                               ['4h', '15m', '5m']):
        df = anal['df']
        ax.plot(df.index, df['close'], color='#00ff88', linewidth=1.5, label='Close')
        # Swings
        if not anal['swing_highs'].empty:
            ax.scatter(anal['swing_highs'].index, anal['swing_highs']['high'],
                       color='#ff4444', marker='v', s=40, label='Swing High')
        if not anal['swing_lows'].empty:
            ax.scatter(anal['swing_lows'].index, anal['swing_lows']['low'],
                       color='#44ff44', marker='^', s=40, label='Swing Low')
        # VWAP
        ax.axhline(y=anal['vwap'], color='#ffaa00', linestyle=':', label='VWAP')
        # Niveles
        for _, price in anal['supports']:
            ax.axhline(y=price, color='#44ff44', linestyle='--', alpha=0.5)
        for _, price in anal['resistances']:
            ax.axhline(y=price, color='#ff4444', linestyle='--', alpha=0.5)

        ax.set_title(f"{symbol} - {title}", color='white')
        ax.legend(loc='upper left', fontsize=8, facecolor='#2e2e2e', edgecolor='#444444', labelcolor='white')
        ax.tick_params(colors='white')
        ax.set_facecolor('#1e1e1e')
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        for spine in ax.spines.values():
            spine.set_color('#444444')

    fig.tight_layout(pad=3.0)

    # Guardar a buffer
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=120, bbox_inches='tight', facecolor='#1e1e1e')
    buf.seek(0)
    plt.close(fig)

    # Mensaje
    direction_emoji = "🟢" if signal['direction'] == 'LONG' else "🔴"
    msg = (
        f"{direction_emoji} <b>Señal de {signal['direction']} en {symbol}</b>\n"
        f"💰 Precio actual: {signal['current_price']:.6f} USDT\n"
        f"🎯 Entrada sugerida: {signal['entry_zone']:.6f}\n"
        f"🛑 Stop Loss: {signal['stop_loss']:.6f} (ATR 1.5x)\n"
        f"🏆 Take Profit: {signal['take_profit']:.6f} (ATR 3x)\n"
        f"📊 VWAP: {signal['vwap']:.6f}\n"
        f"📈 ATR(14): {signal['atr']:.4f}\n"
        f"🔗 URL: https://www.binance.com/es/futures/{symbol}\n"
        f"🔮 <b>Fibonacci:</b> \n<code>{json.dumps(signal.get('fib_levels', {}), indent=2)}</code>"
    )

    bot = Bot(token=bot_token)
    try:
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=buf,
                    caption=msg,
                    parse_mode='HTML',
                    connect_timeout=15,
                    read_timeout=30,
                    write_timeout=30,
                    pool_timeout=15,
                )
                return
            except RetryAfter as exc:
                if attempt == max_attempts:
                    raise
                wait_seconds = float(exc.retry_after) + 1.0
                logger.warning(
                    "Telegram rate limit para %s, reintentando en %.1fs (intento %d/%d)",
                    symbol,
                    wait_seconds,
                    attempt,
                    max_attempts,
                )
                await asyncio.sleep(wait_seconds)
            except (TimedOut, NetworkError) as exc:
                if attempt == max_attempts:
                    raise
                wait_seconds = attempt * 2
                logger.warning(
                    "Error de red enviando %s (%s). Reintento en %ss (%d/%d)",
                    symbol,
                    exc,
                    wait_seconds,
                    attempt,
                    max_attempts,
                )
                await asyncio.sleep(wait_seconds)
    finally:
        buf.close()