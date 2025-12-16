from abc import ABC
from hft_backtest import Order, OrderState, Component, Account

class Strategy(Component, ABC):
    """
    策略抽象基类
    """

    def __init__(self, account: Account):
        super().__init__()
        self.account = account

    def send_order(self, order: Order):
        """发送订单到事件引擎"""
        assert order.state == OrderState.CREATED or order.is_cancel
        order.state = OrderState.SUBMITTED
        self.event_engine.put(order)