import os
from dotenv import load_dotenv
import logging

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Límites de escaneo
MAX_SCAN_PAIRS = 200
SCAN_INTERVAL_SECONDS = 60  # tiempo entre escaneos completos

# Logging
LOG_LEVEL = logging.INFO

def setup_logging():
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("bintrabot.log", encoding="utf-8")
        ]
    )
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)