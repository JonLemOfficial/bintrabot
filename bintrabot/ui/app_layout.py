from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.progressbar import ProgressBar
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
from kivy.metrics import dp
from ui.styles import DarkLabel, DarkButton, DarkSpinner
from ui.chart_widget import PriceChartWidget
from analyzer import PriceExtremesAnalyzer
from scanner import FuturesScanner
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
import asyncio
import threading

class ConfigTab(TabbedPanelItem):

    def __init__(self, **kwargs):
        super().__init__(text='Configuración', **kwargs)
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        layout.add_widget(DarkLabel(text='Token de Telegram:'))
        self.token_input = TextInput(text=TELEGRAM_BOT_TOKEN, multiline=False, size_hint_y=None, height=40)
        layout.add_widget(self.token_input)
        layout.add_widget(DarkLabel(text='Chat ID:'))
        self.chat_id_input = TextInput(text=TELEGRAM_CHAT_ID, multiline=False, size_hint_y=None, height=40)
        layout.add_widget(self.chat_id_input)
        self.add_widget(layout)

class ScannerTab(TabbedPanelItem):
    
    def __init__(self, main_app, **kwargs):
        super().__init__(text='Escáner', **kwargs)
        self.main_app = main_app
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)

        self.progress_bar = ProgressBar(max=100, size_hint=(1, 0.05))
        layout.add_widget(self.progress_bar)

        self.status_label = DarkLabel(text='Escáner detenido', size_hint=(1, 0.05))
        layout.add_widget(self.status_label)

        btn_layout = BoxLayout(size_hint=(1, 0.1), spacing=10)
        self.start_btn = DarkButton(text='Iniciar Escaneo')
        self.start_btn.bind(on_press=self.start_scanner)
        self.stop_btn = DarkButton(text='Detener Escaneo', background_color=(0.8, 0.2, 0.2, 1))
        self.stop_btn.bind(on_press=self.stop_scanner)
        btn_layout.add_widget(self.start_btn)
        btn_layout.add_widget(self.stop_btn)
        layout.add_widget(btn_layout)

        # Historial de señales (scroll)
        scroll = ScrollView(size_hint=(1, 0.8))
        self.history_grid = BoxLayout(orientation='vertical', size_hint_y=None)
        self.history_grid.bind(minimum_height=self.history_grid.setter('height'))
        scroll.add_widget(self.history_grid)
        layout.add_widget(scroll)

        self.add_widget(layout)

    def start_scanner(self, instance):
        self.main_app.start_scanner_thread()

    def stop_scanner(self, instance):
        self.main_app.stop_scanner_thread()

    def update_progress(self, total, scanned):
        if total > 0:
            self.progress_bar.max = total
            self.progress_bar.value = scanned

    def add_alert_to_history(self, symbol, direction, entry):
        label = DarkLabel(text=f"{symbol}: {direction} @ {entry:.6f}", size_hint_y=None, height=30)
        self.history_grid.add_widget(label)

class ManualAnalysisTab(TabbedPanelItem):
    
    def __init__(self, **kwargs):
        super().__init__(text='Análisis Manual', **kwargs)
        self.analyzer = PriceExtremesAnalyzer()
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)

        controls = BoxLayout(size_hint=(1, 0.1), spacing=10)
        self.symbol_input = TextInput(text='BTCUSDT', multiline=False, size_hint=(0.3, 1))
        self.tf_spinner = DarkSpinner(text='15m', values=['1m','5m','15m','1h','4h','1d'], size_hint=(0.2, 1))
        btn_analyze = DarkButton(text='Analizar', size_hint=(0.2, 1))
        btn_analyze.bind(on_press=self.run_manual_analysis)

        controls.add_widget(self.symbol_input)
        controls.add_widget(self.tf_spinner)
        controls.add_widget(btn_analyze)
        layout.add_widget(controls)

        self.chart_widget = PriceChartWidget()
        layout.add_widget(self.chart_widget)
        self.add_widget(layout)

    def run_manual_analysis(self, instance):
        symbol = self.symbol_input.text.upper().strip()
        tf = self.tf_spinner.text
        thread = threading.Thread(target=self._analysis_thread, args=(symbol, tf))
        thread.daemon = True
        thread.start()

    def _analysis_thread(self, symbol, tf):
        df = self.analyzer.get_binance_data(symbol, tf, 300)
        if df is not None:
            anal = self.analyzer.analyze_extremes(df, lookback=5, window=20)
            Clock.schedule_once(lambda dt: self.chart_widget.update_chart([anal], symbol))

class AppLayout(TabbedPanel):
    
    def __init__(self, main_app, **kwargs):
        super().__init__(**kwargs)
        self.main_app = main_app
        self.do_default_tab = False

        self.config_tab = ConfigTab()
        self.scanner_tab = ScannerTab(main_app)
        self.manual_tab = ManualAnalysisTab()

        self.add_widget(self.config_tab)
        self.add_widget(self.scanner_tab)
        self.add_widget(self.manual_tab)
        self.default_tab = self.scanner_tab