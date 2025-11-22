import pandas as pd
from math import isclose

from hft_backtest import EventEngine, Component, Order, OrderState, Data, Account

class BinanceAccount(Account):
    """
    账户类
    1. 监听Order事件 维护订单状态和持仓状态
    2. 监听Data:trade事件 维护每个品种最新价
    3. 提供get_orders/get_positions/get_prices方法查询当前订单 持仓 最新价
    4. 注入接口到event engine中
    """
    def __init__(self):
        # 活跃订单与持仓、价格快照
        self.order_dict: dict[int, Order] = {}
        self.position_dict: dict[str, float] = {}
        self.price_dict: dict[str, float] = {}

    def on_order(self, order: Order):
        assert isinstance(order, Order)
        # 撤单指令本身不计入账户状态（目标订单的状态变更会单独推送）
        if order.is_cancel:
            return
        # 状态机处理
        state = order.state
        # 不能是CREATED状态, 这表明不是通过send_order接口发出的订单
        assert state != OrderState.CREATED
        if state in (OrderState.SUBMITTED, OrderState.RECEIVED):
            self.order_dict[order.order_id] = order
            return
        elif state == OrderState.FILLED:
            # 更新持仓
            pos = self.position_dict[order.symbol] = self.position_dict.get(order.symbol, 0.0) + order.quantity
            if isclose(pos, 0.0):
                del self.position_dict[order.symbol]
        # 走到这里要么是成交了要么是撤单了，都从活跃订单移除
        del self.order_dict[order.order_id]

    def on_data(self, data: Data):
        # 仅维护成交价数据
        if data.name != "trades":
            return
        df: pd.DataFrame = data.data
        if df.empty or 'symbol' not in df.columns or 'price' not in df.columns:
            return
        # 每个 symbol 的最后价格
        last = df.groupby('symbol', sort=False).tail(1)
        price_map = last.set_index('symbol')['price'].to_dict()
        self.price_dict.update(price_map)

    def get_orders(self):
        return self.order_dict.copy()
    
    def get_positions(self):
        return self.position_dict.copy()

    def get_prices(self):
        return self.price_dict.copy()