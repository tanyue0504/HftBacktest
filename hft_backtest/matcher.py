from abc import ABC, abstractmethod

from hft_backtest import EventEngine, Component, Order, Data

class MatchEngine(Component, ABC):
    """
    撮合引擎抽象基类
    监听订单事件和数据事件，处理订单撮合逻辑
    订单状态发生变化时，推送订单最新状态到事件引擎
    """
    
    @abstractmethod
    def on_order(self, order: Order):
        """处理订单事件的抽象方法"""
        pass

    @abstractmethod
    def start(self, engine: EventEngine):
        raise NotImplementedError()

    def stop(self):
        pass