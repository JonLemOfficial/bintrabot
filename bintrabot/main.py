import asyncio
import threading
import sys
import logging
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.graphics import Color, Rectangle
from kivy.core.window import Window
from config import setup_logging, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from ui.app_layout import AppLayout
from scanner import FuturesScanner
from analyzer import PriceExtremesAnalyzer
from utils import notify_desktop, load_alert_history

setup_logging()
logger = logging.getLogger(__name__)

class BintrabotApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.scanner = None
        self.scanner_thread = None
        self.event_loop = None

    def build(self):
        Window.clearcolor = (0.1, 0.1, 0.1, 1)
        self.title = "Bintrabot - Analizador de Futuros"
        self.layout = AppLayout(self)
        return self.layout

    def on_start(self):
        notify_desktop("Bintrabot", "Bienvenido al analizador de futuros")
        # Cargar historial de alertas en pestaña escáner
        history = load_alert_history()
        for alert in history[-10:]:
            self.layout.scanner_tab.add_alert_to_history(
                alert['symbol'], alert['direction'], alert['entry']
            )

    def start_scanner_thread(self):
        if self.scanner_thread and self.scanner_thread.is_alive():
            return
        token = TELEGRAM_BOT_TOKEN or self.layout.config_tab.token_input.text.strip()
        chat_id = TELEGRAM_CHAT_ID or self.layout.config_tab.chat_id_input.text.strip()
        if not token or not chat_id:
            logger.warning("Token o Chat ID no configurados")
            self.layout.scanner_tab.status_label.text = "Configura token y chat ID primero"
            return

        analyzer = PriceExtremesAnalyzer()
        self.scanner = FuturesScanner(analyzer, chat_id, token)
        self.scanner.status_callback = self.update_scanner_ui

        def run_async_loop():
            self.event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.event_loop)
            self.event_loop.run_until_complete(self.scanner.run_scan_loop())

        self.scanner_thread = threading.Thread(target=run_async_loop, daemon=True)
        self.scanner_thread.start()
        self.layout.scanner_tab.status_label.text = "Escáner iniciado"
        logger.info("Scanner iniciado")

    def stop_scanner_thread(self):
        if self.scanner:
            self.scanner.stop()
        self.layout.scanner_tab.status_label.text = "Escáner detenido"
        logger.info("Scanner detenido")

    def update_scanner_ui(self, total, scanned):
        Clock.schedule_once(lambda dt: self.layout.scanner_tab.update_progress(total, scanned))

    def on_stop(self):
        self.stop_scanner_thread()
        notify_desktop("Bintrabot", "Aplicación cerrada")

if __name__ == "__main__":
    BintrabotApp().run()