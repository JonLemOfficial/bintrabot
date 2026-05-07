import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from io import BytesIO
from kivy.uix.boxlayout import BoxLayout
from kivy.core.image import Image as CoreImage
from kivy.uix.image import Image
from kivy.uix.label import Label
from ui.styles import DarkLabel

class ChartImage(Image):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.allow_stretch = True
        self.keep_ratio = True

class PriceChartWidget(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = 10
        self.spacing = 10

        self.chart_area = BoxLayout(size_hint=(1, 0.7))
        self.add_widget(self.chart_area)

        self.info_area = BoxLayout(orientation='vertical', size_hint=(1, 0.3))
        self.add_widget(self.info_area)

        self.price_label = DarkLabel(text="Precio actual: --", size_hint=(1, 0.2))
        self.signals_label = DarkLabel(text="Señales: --", size_hint=(1, 0.2))
        self.levels_label = DarkLabel(text="Niveles: --", size_hint=(1, 0.6))

        self.info_area.add_widget(self.price_label)
        self.info_area.add_widget(self.signals_label)
        self.info_area.add_widget(self.levels_label)

        self.chart_image = ChartImage()
        self.chart_area.add_widget(self.chart_image)

    def update_chart(self, analysis_list, symbol: str):
        # analysis_list: lista de análisis para cada timeframe (4h,15m,5m)
        if not analysis_list:
            return
        try:
            fig, axes = plt.subplots(len(analysis_list), 1, figsize=(12, 4*len(analysis_list)),
                                     facecolor='#1e1e1e')
            if len(analysis_list) == 1:
                axes = [axes]

            for ax, anal in zip(axes, analysis_list):
                df = anal['df']
                ax.plot(df.index, df['close'], color='#00ff88', linewidth=1.5)
                if not anal['swing_highs'].empty:
                    ax.scatter(anal['swing_highs'].index, anal['swing_highs']['high'],
                               color='#ff4444', marker='v', s=50)
                if not anal['swing_lows'].empty:
                    ax.scatter(anal['swing_lows'].index, anal['swing_lows']['low'],
                               color='#44ff44', marker='^', s=50)
                ax.set_facecolor('#1e1e1e')
                ax.tick_params(colors='white')
                for spine in ax.spines.values():
                    spine.set_color('#444444')

            fig.tight_layout()
            buf = BytesIO()
            fig.savefig(buf, format='png', dpi=100, bbox_inches='tight', facecolor='#1e1e1e')
            buf.seek(0)
            im = CoreImage(buf, ext='png')
            self.chart_image.texture = im.texture
            buf.close()
            plt.close(fig)
        except Exception as e:
            print(f"Error al actualizar chart: {e}")

    def update_info(self, signal_info):
        if not signal_info:
            return
        self.price_label.text = f"Precio: {signal_info['current_price']:.6f}"
        self.signals_label.text = f"Señal: {signal_info['direction']} | Entrada: {signal_info['entry_zone']:.6f}"
        self.levels_label.text = f"SL: {signal_info['stop_loss']:.6f} | TP: {signal_info['take_profit']:.6f} | ATR: {signal_info['atr']:.4f}"