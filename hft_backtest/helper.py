from hft_backtest import Component
from hft_backtest.event_engine import EventEngine
class EventPrinter(Component):
    def __init__(self, tips: str = "", event_types: list = None):
        super().__init__()
        self.tips = tips
        self.event_types = event_types if event_types is not None else []

    def on_event(self, event):
        if type(event) not in self.event_types:
            return
        print(f"{self.tips} {self.event_engine.timestamp} {event}")

    def start(self, engine: EventEngine):
        self.event_engine = engine
        engine.global_register(self.on_event, ignore_self=True, is_senior=True)

    def stop(self):
        pass