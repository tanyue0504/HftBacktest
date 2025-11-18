from hft_backtest import Component, Order, Data,  EventEngine
from abc import abstractmethod, ABC

class Recorder(Component, ABC):
    def __init__(self):
        pass

    @abstractmethod
    def on_order(self, order: Order):
        pass

    @abstractmethod
    def on_data(self, data: Data):
        pass

    def start(self, event_engine: EventEngine):
        event_engine.register(Order, self.on_order)
        event_engine.register(Data, self.on_data)

    def stop(self):
        pass
