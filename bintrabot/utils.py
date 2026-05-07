from plyer import notification
import json
import os
from datetime import datetime
from typing import List, Dict

ALERTS_FILE = "alerts_history.json"

def notify_desktop(title: str, message: str, timeout: int = 8):
    try:
        notification.notify(
            title=title,
            message=message,
            toast=True,
            timeout=timeout
        )
    except Exception:
        pass

def save_alert_to_history(symbol: str, direction: str, entry: float, stop_loss: float, take_profit: float):
    alert = {
        "timestamp": datetime.now().isoformat(),
        "symbol": symbol,
        "direction": direction,
        "entry": entry,
        "stop_loss": stop_loss,
        "take_profit": take_profit
    }
    history = []
    if os.path.exists(ALERTS_FILE):
        with open(ALERTS_FILE, "r") as f:
            try:
                history = json.load(f)
            except json.JSONDecodeError:
                history = []
    history.append(alert)
    # Mantener solo las últimas 100 alertas
    if len(history) > 100:
        history = history[-100:]
    with open(ALERTS_FILE, "w") as f:
        json.dump(history, f, indent=2)

def load_alert_history() -> List[Dict]:
    if not os.path.exists(ALERTS_FILE):
        return []
    with open(ALERTS_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []