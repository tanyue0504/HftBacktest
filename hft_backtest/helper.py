from hft_backtest import Component, Order
from hft_backtest.event_engine import EventEngine
from loguru import logger

class EventPrinter(Component):
    def __init__(self, tips: str = "", event_types: list = None):
        super().__init__()
        self.tips = tips
        self.event_types = set(event_types) if event_types is not None else set()

    def on_event(self, event):
        if type(event) not in self.event_types:
            return
        print(f"{self.tips} {self.event_engine.timestamp} {event}")

    def start(self, engine: EventEngine):
        self.event_engine = engine
        engine.global_register(self.on_event, ignore_self=True, is_senior=True)

    def stop(self):
        pass

class OrderTracer(Component):
    def __init__(self, target_order_id):
        super().__init__()
        self.target_order_id = target_order_id

    def on_order(self, order:Order):
        if order.order_id != self.target_order_id:
            return
        logger.info(f"OrderTracer: {self.event_engine.timestamp} {order}")

    def start(self, engine: EventEngine):
        self.event_engine = engine
        engine.register(Order, self.on_order)
        
    def stop(self):
        pass