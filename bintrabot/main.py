import logging
import os
import sys
from datetime import datetime
from io import BytesIO
from threading import Thread
from typing import Any, Dict, Self, Tuple

import requests
import warnings
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.progressbar import ProgressBar
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, Rectangle
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.core.image import Image as CoreImage
from kivy.uix.image import Image
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes
from dotenv import load_dotenv
from PIL import Image as PILImage
from pandas import DataFrame, to_datetime, to_numeric
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from plyer import notification

load_dotenv()

# Configuration of matplotlib for dark theme
plt.style.use('dark_background')
matplotlib.use('Agg')  # Use non-interactive backend

warnings.filterwarnings('ignore')

# Configuration of telegram bot to send alerts
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

tgbot = ApplicationBuilder() \
  .token(TELEGRAM_BOT_TOKEN) \
  .build()

async def send_pair_analisys_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
  # update.message
  pass

class PriceExtremesAnalyzer(object):

  def __init__(self: Self) -> None:
    self.data = None
      
  def calculate_support_resistance(self: Self, prices: Tuple, window: int = 20) -> Tuple:
    """Detect support and resistence levels"""
    supports = []
    resistances = []
    
    if len(prices) < window * 2 + 1:
      return supports, resistances
    
    for i in range(window, len(prices) - window):
      # Verify if it is a local minimum (support)
      if (prices[i] == min(prices[i-window:i+window+1]) and 
        prices[i] != prices[i-1] and prices[i] != prices[i+1]):
        supports.append((i, prices[i]))
      
      # Verify if it is a local maximum (resistance)
      if (prices[i] == max(prices[i-window:i+window+1]) and 
        prices[i] != prices[i-1] and prices[i] != prices[i+1]):
        resistances.append((i, prices[i]))
            
    return supports, resistances
  
  def find_swing_high_low(self: Self, df: DataFrame, lookback_period: int = 5) -> DataFrame:
    """Find maximum y minimums from swing"""
    df = df.copy()
    df['swing_high'] = False
    df['swing_low'] = False
    
    if len(df) <= lookback_period * 2:
      return df
    
    for i in range(lookback_period, len(df) - lookback_period):
      # Verify minimum of the swing
      is_low = True
      current_low = df['low'].iloc[i]
      
      for j in range(1, lookback_period + 1):
        if current_low >= df['low'].iloc[i-j] or current_low >= df['low'].iloc[i+j]:
          is_low = False
          break
      
      df.loc[df.index[i], 'swing_low'] = is_low
      
      # Verify maximum of the swing
      is_high = True
      current_high = df['high'].iloc[i]
      
      for j in range(1, lookback_period + 1):
        if current_high <= df['high'].iloc[i-j] or current_high <= df['high'].iloc[i+j]:
          is_high = False
          break
      
      df.loc[df.index[i], 'swing_high'] = is_high
        
    return df
    
  def get_binance_data(self: Self, symbol: str, interval: str, limit: int = 500) -> DataFrame:
    """Get historial data from Binance"""
    url = f"https://api.binance.com/api/v3/klines"
    params = {
      'symbol': symbol.upper(),
      'interval': interval,
      'limit': limit
    }
    
    try:
      response = requests.get(url, params=params, timeout=10)
      
      if response.status_code != 200:
        return None
          
      data = response.json()
      
      if not data:
        return None
      
      df = DataFrame(
        data,
        columns=[
          'open_time', 'open', 'high', 'low', 'close', 'volume',
          'close_time', 'quote_asset_volume', 'number_of_trades',
          'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ]
      )
      
      if len(df) == 0:
        return None
      
      # Convert data types
      df['open_time'] = to_datetime(df['open_time'], unit='ms')
      df['close_time'] = to_datetime(df['close_time'], unit='ms')
      
      for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = to_numeric(df[col], errors='coerce')
          
      df.set_index('open_time', inplace=True)
      
      return df
    except:
      return None
  
  def analyze_extremes(self: Self, df: DataFrame, lookback_period: int = 5, window: int = 20) -> None:
    """Analyze and return the extremes of the price"""
    if df is None or len(df) == 0:
      return None
        
    min_data_points = max(lookback_period * 2 + 1, window * 2 + 1)
    if len(df) < min_data_points:
      return None
    
    try:
      # Find swings
      df_with_swings = self.find_swing_high_low(df, lookback_period)
      
      # Get high and low swings
      swing_highs = df_with_swings[df_with_swings['swing_high']]
      swing_lows = df_with_swings[df_with_swings['swing_low']]
      
      # Calculate supports and resistances
      prices = df['close'].values
      supports, resistances = self.calculate_support_resistance(prices, window)
      
      return {
        'swing_highs': swing_highs[['high']],
        'swing_lows': swing_lows[['low']],
        'supports': [(df.index[i], price) for i, price in supports],
        'resistances': [(df.index[i], price) for i, price in resistances],
        'current_price': df['close'].iloc[-1],
        'df_with_swings': df_with_swings,
        'df': df
      }
    except:
      return None

class DarkLabel(Label):
    
  def __init__(self: Self, **kwargs) -> None:
    super().__init__(**kwargs)
    self.color = (0.9, 0.9, 0.9, 1)
    self.font_size = dp(14)

class DarkButton(Button):
    
  def __init__(self: Self, **kwargs) -> None:
    super().__init__(**kwargs)
    self.background_color = (0.2, 0.6, 0.8, 1)
    self.color = (1, 1, 1, 1)
    self.font_size = dp(14)

class DarkSpinner(Spinner):
    
  def __init__(self: Self, **kwargs) -> None:
    super().__init__(**kwargs)
    self.background_color = (0.3, 0.3, 0.3, 1)
    self.color = (1, 1, 1, 1)
    self.font_size = dp(14)

class ChartImage(Image):
  """Custom widget to show matplotlib charts"""
  
  def __init__(self: Self, **kwargs) -> None:
    super().__init__(**kwargs)
    self.allow_stretch = True
    self.keep_ratio = True

class PriceChartWidget(BoxLayout):

  def __init__(self: Self, **kwargs) -> None:
    super().__init__(**kwargs)
    self.orientation = 'vertical'
    self.padding = dp(10)
    self.spacing = dp(10)
    
    # Area for the chart
    self.chart_area = BoxLayout(size_hint=(1, 0.7))
    self.add_widget(self.chart_area)
    
    # Area for information
    self.info_area = BoxLayout(orientation='vertical', size_hint=(1, 0.3))
    self.add_widget(self.info_area)
    
    # Labels for information
    self.price_label = DarkLabel(text="Current price: --", size_hint=(1, 0.2))
    self.signals_label = DarkLabel(text="Signals: --", size_hint=(1, 0.2))
    self.levels_label = DarkLabel(text="Levels: --", size_hint=(1, 0.6))
    
    self.info_area.add_widget(self.price_label)
    self.info_area.add_widget(self.signals_label)
    self.info_area.add_widget(self.levels_label)
    
    # Widget image for the chart
    self.chart_image = ChartImage()
    self.chart_area.add_widget(self.chart_image)
    
  def update_chart(self: Self, analysis: Dict | None, symbol: str) -> None:
    """Update the chart with new data"""
    if analysis is None:
      return
        
    try:
      # Create figure with dark theme
      fig, ax = plt.subplots(figsize=(12, 6), facecolor='#1e1e1e')
      ax.set_facecolor('#1e1e1e')
      
      df = analysis['df']
      
      # Price
      ax.plot(
        df.index, df['close'],
        label='Price', linewidth=2, alpha=0.8, color='#00ff88'
      )
      
      # Swing highs
      swing_highs = analysis['swing_highs']
      if len(swing_highs) > 0:
        ax.scatter(
          swing_highs.index, swing_highs['high'], 
          color='#ff4444', marker='v', s=80, label='Maxims', zorder=5
        )
      
      # Swing lows
      swing_lows = analysis['swing_lows']
      if len(swing_lows) > 0:
        ax.scatter(
          swing_lows.index, swing_lows['low'], 
          color='#44ff44', marker='^', s=80, label='Minims', zorder=5
        )
      
      # Supports and resistances
      support_prices = [price for _, price in analysis['supports']]
      resistance_prices = [price for _, price in analysis['resistances']]
      
      for price in set(support_prices):
        ax.axhline(y=price, color='#44ff44', linestyle='--', alpha=0.7, linewidth=1)
          
      for price in set(resistance_prices):
        ax.axhline(y=price, color='#ff4444', linestyle='--', alpha=0.7, linewidth=1)
      
      # Configuration of the chart
      ax.set_title(f'{symbol} - Extreme Analysis', color='white', fontsize=14, pad=20)
      ax.set_xlabel('Time', color='white')
      ax.set_ylabel('Price (USDT)', color='white')
      ax.legend(facecolor='#2e2e2e', edgecolor='#444444', labelcolor='white')
      ax.grid(True, alpha=0.3, color='#444444')
      
      # Color of the axes
      ax.tick_params(colors='white')
      for spine in ax.spines.values():
        spine.set_color('#444444')
      
      plt.xticks(rotation=45)
      plt.tight_layout()
      
      # CORRECTION: Save figure in buffer and convert correctly
      buf = BytesIO()
      plt.savefig(
        buf,
        format='png', dpi=100, bbox_inches='tight', facecolor='#1e1e1e', edgecolor='none'
      )
      buf.seek(0)
      
      # CORRECIÓN: Usar CoreImage directamente con el buffer
      im = CoreImage(buf, ext='png')
      self.chart_image.texture = im.texture
      
      # Close figure and buffer to free memory
      plt.close(fig)
      buf.close()
      
      # Update information
      self.update_info(analysis)
        
    except Exception as e:
      print(f"Error updating chart: {e}")
      import traceback
      traceback.print_exc()
  
  def update_info(self: Self, analysis: Dict | None) -> None:
    """Update the textual information"""
    try:
      current_price = analysis['current_price']
      self.price_label.text = f"Current price: ${current_price:.6f}"
      
      # Generate simple signals
      signals = []
      support_prices = [price for _, price in analysis['supports']]
      resistance_prices = [price for _, price in analysis['resistances']]
      
      nearest_support = min(support_prices, key=lambda x: abs(x - current_price)) if support_prices else None
      nearest_resistance = min(resistance_prices, key=lambda x: abs(x - current_price)) if resistance_prices else None
      
      if nearest_support and (current_price - nearest_support) / nearest_support < 0.02:
        signals.append(f"Support: ${nearest_support:.6f}")
          
      if nearest_resistance and (nearest_resistance - current_price) / current_price < 0.02:
        signals.append(f"Resistance: ${nearest_resistance:.6f}")
          
      self.signals_label.text = f"Signals: {', '.join(signals) if signals else 'None'}"
      
      # Information of levels
      levels_text = f"Supports: {len(set(support_prices))} | "
      levels_text += f"Resistances: {len(set(resistance_prices))} | "
      levels_text += f"Swings: {len(analysis['swing_highs']) + len(analysis['swing_lows'])}"
      self.levels_label.text = levels_text
        
    except Exception as e:
      print(f"Error updating information: {e}")

class BintrabotUI(BoxLayout):

  def __init__(self: Self, **kwargs) -> None:
    super().__init__(**kwargs)
    self.orientation = 'vertical'
    self.padding = dp(10)
    self.spacing = dp(10)
    
    # Configure dark background
    with self.canvas.before:
      Color(0.1, 0.1, 0.1, 1)
      self.rect = Rectangle(size=self.size, pos=self.pos)
    self.bind(size=self._update_rect, pos=self._update_rect)
    
    # Initialize analyzer
    self.analyzer = PriceExtremesAnalyzer()
    
    # Create interface
    self.create_interface()
  
  def _update_rect(self: Self, instance, value) -> None:
    self.rect.pos = instance.pos
    self.rect.size = instance.size
  
  def create_interface(self: Self) -> None:
    """Create the user interface"""
    # Superior control panel
    controls_layout = GridLayout(
      cols=6,
      rows=1,
      size_hint=(1, 0.08),
      spacing=dp(10)
    )
    
    # Trading pair
    self.symbol_input = TextInput(
      text='BTCUSDT',
      hint_text='Par (ej: BTCUSDT)',
      size_hint=(0.10, 0.7),
      background_color=(0.2, 0.2, 0.2, 1),
      foreground_color=(1, 1, 1, 1),
      multiline=False
    )
    
    # Timeframe selector
    self.timeframe_spinner = DarkSpinner(
      text='15m',
      values=['1m', '5m', '15m', '1h', '4h', '1d'],
      size_hint=(0.05, 0.35)
    )
    
    # Lookback period
    self.lookback_spinner = DarkSpinner(
      text='3',
      values=['2', '3', '5', '8', '13'],
      size_hint=(0.05, 0.35)
    )
    
    # Window size
    self.window_spinner = DarkSpinner(
      text='10',
      values=['5', '10', '15', '20', '25'],
      size_hint=(0.05, 0.35)
    )
    
    # Analysis button
    self.analyze_btn = DarkButton(
      text='ANALYZE',
      size_hint=(0.2, 0.35)
    )
    self.analyze_btn.bind(on_press=self.start_analysis)
    
    # Automatic update button
    self.auto_btn = DarkButton(
      text='AUTO: OFF',
      size_hint=(0.15, 0.35)
    )
    
    self.auto_btn.bind(on_press=self.toggle_auto_update)
    
    controls_layout.add_widget(self.symbol_input)
    controls_layout.add_widget(self.timeframe_spinner)
    controls_layout.add_widget(self.lookback_spinner)
    controls_layout.add_widget(self.window_spinner)
    controls_layout.add_widget(self.analyze_btn)
    controls_layout.add_widget(self.auto_btn)

    self.add_widget(controls_layout)
    
    # Progress bar
    self.progress_bar = ProgressBar(max=100, size_hint=(1, 0.02))
    self.progress_bar.value = 0
    self.add_widget(self.progress_bar)
    
    # Status label
    self.status_label = DarkLabel(text="Ready to analyze...", size_hint=(1, 0.03))
    self.add_widget(self.status_label)
    
    # Chart widget
    self.chart_widget = PriceChartWidget()
    self.add_widget(self.chart_widget)
    
    # Automatic update state
    self.auto_update = False
    self.auto_event = None
  
  def toggle_auto_update(self: Self, instance) -> None:
    """Activate/deactivate automatic update"""
    self.auto_update = not self.auto_update
    
    if self.auto_update:
      self.auto_btn.text = 'AUTO: ON'
      self.auto_btn.background_color = (0.2, 0.8, 0.2, 1)
      self.start_auto_update()
      self.status_label.text = "Automatic update ACTIVATED"
    else:
      self.auto_btn.text = 'AUTO: OFF'
      self.auto_btn.background_color = (0.2, 0.6, 0.8, 1)
      self.stop_auto_update()
      self.status_label.text = "Automatic update DEACTIVATED"
  
  def start_auto_update(self: Self) -> None:
    """Start automatic update every 30 seconds"""
    if self.auto_event is None:
      self.auto_event = Clock.schedule_interval(lambda dt: self.start_analysis(None), 30)
  
  def stop_auto_update(self: Self) -> None:
    """Stop automatic update"""
    if self.auto_event:
      self.auto_event.cancel()
      self.auto_event = None
  
  def start_analysis(self: Self, instance) -> None:
    """Start analysis in a separate thread"""
    self.status_label.text = "Getting data..."
    self.progress_bar.value = 10
    
    # Get parameters
    symbol = self.symbol_input.text.upper().strip()
    timeframe = self.timeframe_spinner.text
    lookback = int(self.lookback_spinner.text)
    window_size = int(self.window_spinner.text)
    
    if not symbol:
      self.status_label.text = "Error: Enter a valid pair"
      return
    
    # Execute in a separate thread
    thread = Thread(
      target=self.run_analysis,
      args=(symbol, timeframe, lookback, window_size)
    )
    thread.daemon = True
    thread.start()
  
  def run_analysis(self: Self, symbol: str, timeframe: str, lookback: int, window_size: int) -> None:
    """Execute the analysis (in a separate thread)"""
    try:
      # Get data
      Clock.schedule_once(lambda dt: setattr(self.progress_bar, 'value', 30))
      Clock.schedule_once(lambda dt: setattr(self.status_label, 'text', "Getting data from Binance..."))
      
      df = self.analyzer.get_binance_data(symbol, timeframe, 200)
      
      if df is not None and len(df) > 0:
        # Perform analysis
        Clock.schedule_once(lambda dt: setattr(self.progress_bar, 'value', 70))
        Clock.schedule_once(lambda dt: setattr(self.status_label, 'text', "Analyzing data..."))
        
        analysis = self.analyzer.analyze_extremes(df, lookback, window_size)
        
        if analysis is not None:
          # Update UI in the main thread
          Clock.schedule_once(lambda dt: self.update_ui(analysis, symbol))
          Clock.schedule_once(lambda dt: setattr(self.progress_bar, 'value', 100))
          Clock.schedule_once(lambda dt: setattr(self.status_label, 'text', "Analysis completed"))
        else:
          Clock.schedule_once(lambda dt: self.show_error("Error in the data analysis"))
      else:
        Clock.schedule_once(lambda dt: self.show_error(f"Could not get data for {symbol}"))
            
    except Exception as e:
      Clock.schedule_once(lambda dt: self.show_error(f"Error: {str(e)}"))
    
    # Reset progress bar after a time
    Clock.schedule_once(lambda dt: setattr(self.progress_bar, 'value', 0), 3)
    
  def update_ui(self: Self, analysis: Dict | None, symbol: str) -> None:
    """Update the user interface with the results"""
    self.chart_widget.update_chart(analysis, symbol)
    self.status_label.text = f"Analysis of {symbol} completed - {datetime.now().strftime('%H:%M:%S')}"
    
  def show_error(self: Self, message: str) -> None:
    """Show an error message"""
    self.status_label.text = f"Error: {message}"
    self.progress_bar.value = 0

class BintrabotApp(App):
    
  def build(self: Self) -> BintrabotUI:
    self.title = "Bintrabot - Financial Analyzer"
    return BintrabotUI()

  def on_start(self: Self) -> None:
    notification.notify(
      title='Bintrabot',
      message='Welcome to bintrabot, your financial analyzer for cripto trading.',
      toast=True,
      timeout=8
    )

  def on_stop(self: Self) -> None:
    notification.notify(
      title='Bintrabot',
      message='Thank you for using Bintrabot.',
      toast=True,
      timeout=8
    )

  def on_pause(self: Self) -> None:
    pass

  def on_resume(self: Self) -> None:
    pass

def main() -> None:
  return_code: Any = 1

  try:
    app = BintrabotApp()
    app.run()
  except SystemExit as e:  # pragma: no cover
    return_code = e
  except KeyboardInterrupt as e:
    return_code = 0
    notification.notify(
      title='Bintrabot - (INTERNAL_USER_STOP)',
      message='Thank you for using Bintrabot.',
      toast=True,
      timeout=8
    )
  except Exception:
    logger.exception("Fatal exception!")
  finally:
    sys.exit(return_code)

if __name__ == "__main__":
  main()