# hft_backtest/account.pyx
# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False

from hft_backtest.order cimport Order
from hft_backtest.event_engine cimport Component, EventEngine

cdef class Account(Component):
    """
    账户抽象基类 (接口定义)
    
    不包含任何具体逻辑，仅定义接口契约。
    所有具体账户实现 (如 OKXAccount, BinanceAccount) 必须继承此类，
    并实现所有定义的 cpdef 方法。
    """
    
    # --- Component 接口 ---
    # Component 基类已提供默认的 start/stop (pass)，
    # 如果子类不需要特殊的启动逻辑，可以不重写 start。
    
    # --- 核心逻辑 ---
    cpdef void on_order(self, Order order):
        raise NotImplementedError("Account.on_order must be implemented by subclass")

    # --- 状态查询 ---
    cpdef dict get_positions(self):
        raise NotImplementedError("Account.get_positions must be implemented")

    cpdef dict get_orders(self):
        raise NotImplementedError("Account.get_orders must be implemented")
        
    cpdef dict get_prices(self):
        raise NotImplementedError("Account.get_prices must be implemented")

    cpdef double get_balance(self):
        raise NotImplementedError("Account.get_balance must be implemented")

    cpdef double get_equity(self):
        raise NotImplementedError("Account.get_equity must be implemented")

    # --- 统计接口 ---
    cpdef double get_total_turnover(self):
        raise NotImplementedError("Account.get_total_turnover must be implemented")
    
    cpdef double get_total_commission(self):
        raise NotImplementedError("Account.get_total_commission must be implemented")
        
    cpdef double get_total_funding_fee(self):
        raise NotImplementedError("Account.get_total_funding_fee must be implemented")
        
    cpdef double get_total_trade_pnl(self):
        raise NotImplementedError("Account.get_total_trade_pnl must be implemented")
        
    cpdef int get_total_trade_count(self):
        raise NotImplementedError("Account.get_total_trade_count must be implemented")