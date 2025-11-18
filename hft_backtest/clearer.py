from hft_backtest import Event, EventEngine, Data, Component

from abc import ABC, abstractmethod

class ClearerEngine(Component, ABC):
    """
    清算引擎
    
    监听Data事件，处理如资金费率结算，期权到期等结算时间
    """

    @abstractmethod
    def on_data(self, data: Data):
        pass

    def start(self, engine: EventEngine):
        engine.register(Data, self.on_data)

    def stop(self):
        pass