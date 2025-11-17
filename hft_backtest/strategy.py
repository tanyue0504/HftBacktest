from abc import ABC, abstractmethod

from event_engine import EventEngine
from dataset import Data
from order import Order, OrderState

class Strategy(ABC):
    """
    策略抽象基类
    on_data方法需要被子类实现
    """

    def __init__(self, event_engine: EventEngine):
        self.event_engine = event_engine

    def send_order(self, order: Order):
        """发送订单到事件引擎"""
        order.state = OrderState.SUBMITTED
        self.event_engine.put(order)

    @abstractmethod
    def on_data(self, data: Data):
        """处理数据事件"""
        pass

    def on_order(self, order: Order):
        """处理订单事件，子类可选实现"""
        pass