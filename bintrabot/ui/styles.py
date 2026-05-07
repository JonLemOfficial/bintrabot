from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.metrics import dp

class DarkLabel(Label):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.color = (0.9, 0.9, 0.9, 1)
        self.font_size = dp(14)

class DarkButton(Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_color = (0.2, 0.6, 0.8, 1)
        self.color = (1, 1, 1, 1)
        self.font_size = dp(14)

class DarkSpinner(Spinner):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_color = (0.3, 0.3, 0.3, 1)
        self.color = (1, 1, 1, 1)
        self.font_size = dp(14)