from abc import ABC, abstractmethod

from hft_backtest import EventEngine, Data, Order, OrderState, Component

class Strategy(Component, ABC):
    """
    策略抽象基类
    on_data方法需要被子类实现
    """

    def __init__(self):
        super().__init__()

    def send_order(self, order: Order):
        """发送订单到事件引擎"""
        assert order.state == OrderState.CREATED or order.is_cancel
        order.state = OrderState.SUBMITTED
        self.event_engine.put(order)

    @abstractmethod
    def on_data(self, data: Data):
        """处理数据事件"""
        pass

    def on_order(self, order: Order):
        """处理订单事件，子类可选实现"""
        pass

    def start(self, engine: EventEngine):
        engine.register(Data, self.on_data)
        engine.register(Order, self.on_order)

    def stop(self):
        pass