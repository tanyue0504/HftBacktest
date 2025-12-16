from abc import abstractmethod

from hft_backtest import Order, EventEngine, Component

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

    # 提供订单、持仓和价格查询接口
    @abstractmethod
    def get_orders(self):
        return self.order_dict.copy()
    
    @abstractmethod
    def get_positions(self):
        return self.position_dict.copy()

    @abstractmethod
    def get_prices(self):
        return self.price_dict.copy()
    
    # 提供账户瞬时状态查询接口
    @abstractmethod
    def get_equity(self):
        raise NotImplementedError("Account.get_equity not implemented")
    
    @abstractmethod
    def get_balance(self):
        raise NotImplementedError("Account.get_balance not implemented")
    
    @abstractmethod
    def get_total_margin(self):
        raise NotImplementedError("Account.get_total_margin not implemented")
    
    @abstractmethod
    def get_leverage(self):
        raise NotImplementedError("Account.get_leverage not implemented")
    
    # 提供累计字段查询接口
    @abstractmethod
    def get_total_turnover(self):
        raise NotImplementedError("Account.get_turnover not implemented")
    
    @abstractmethod
    def get_total_trade_count(self):
        raise NotImplementedError("Account.get_total_trade_count not implemented")
    
    @abstractmethod
    def get_total_commission(self):
        raise NotImplementedError("Account.get_total_commission not implemented")
    
    @abstractmethod
    def get_total_funding_fee(self):
        raise NotImplementedError("Account.get_total_funding_fee not implemented")
    
    @abstractmethod
    def get_total_realized_pnl(self):
        raise NotImplementedError("Account.get_total_realized_pnl not implemented")