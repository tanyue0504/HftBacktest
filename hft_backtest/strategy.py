# hft_backtest/strategy.py
from abc import ABC
from hft_backtest.event_engine import Component, EventEngine
from hft_backtest.order import Order
from hft_backtest.account import Account

_strategy_id_counter: int = 0

class Strategy(Component, ABC):
    """
    策略抽象基类
    """
    def __init__(self, account: Account):
        # 注意：Component 没有 __init__，或者如果是 Python 类继承 Cython 类，
        # 这里的 super().__init__() 调用的是 object.__init__，通常没问题。
        self.account = account
        self.event_engine = None
        global _strategy_id_counter
        _strategy_id_counter += 1
        self.id_num = _strategy_id_counter

        if self.account is not None:
            self.account.register_strategy(self.id_num)

    def start(self, engine: EventEngine):
        """
        生命周期钩子：策略启动
        继承后需要调用父类方法绑定事件引擎
        """
        self.event_engine = engine


    def send_order(self, order: Order):
        """发送订单到事件引擎"""
        if self.event_engine is None:
            raise RuntimeError("Strategy not started: event_engine is None")
            
        # 确保是初始状态或撤单指令
        assert order.is_created or order.is_cancel_order, f"Invalid order state: {order.state}"

        # 给订单打上策略标记
        order.strategy_id = self.id_num
        
        # 修改状态为 SUBMITTED
        order.state = Order.ORDER_STATE_SUBMITTED
        self.event_engine.put(order)