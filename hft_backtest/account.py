from abc import abstractmethod

from hft_backtest import Order, EventEngine, Data, Component

class Account(Component):
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

    def start(self, engine: EventEngine):
        # 注册监听
        engine.register(Order, self.on_order)
        engine.register(Data, self.on_data)
        # 接口注入
        engine.get_orders = self.get_orders
        engine.get_positions = self.get_positions
        engine.get_prices = self.get_prices

    def stop(self):
        pass
    
    @abstractmethod
    def on_order(self, order: Order):
        pass

    @abstractmethod
    def on_data(self, data: Data):
        pass

    def get_orders(self):
        return self.order_dict.copy()
    
    def get_positions(self):
        return self.position_dict.copy()

    def get_prices(self):
        return self.price_dict.copy()