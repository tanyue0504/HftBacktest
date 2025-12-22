from abc import ABC
from hft_backtest import Order, Component, Account

class Strategy(Component, ABC):
    """
    策略抽象基类
    """

    def __init__(self, account: Account):
        super().__init__()
        self.account = account

    def send_order(self, order: Order):
        """发送订单到事件引擎"""
        assert order.is_created or order.is_cancel_order
        order.state = Order.ORDER_STATE_SUBMITTED
        self.event_engine.put(order)