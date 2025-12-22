# cython: language_level=3

from hft_backtest.account cimport Account
from hft_backtest.order cimport Order
from hft_backtest.okx.event cimport OKXTrades, OKXFundingRate, OKXDelivery

cdef class OKXAccount(Account):
    # --- 核心状态 ---
    cdef public double cash_balance
    
    # position_dict 仍需保持 object (defaultdict)，因为依赖 += 操作的自动初始化
    cdef public object position_dict
    
    cdef public dict order_dict
    
    # 【优化】改为 dict，性能更好
    cdef public dict price_dict

    # --- 累计统计 (保持 object/defaultdict) ---
    cdef public object total_turnover
    cdef public object total_commission
    cdef public object total_funding_fee
    cdef public object net_cash_flow
    cdef public object total_trade_count

    # --- 声明 C 方法 ---
    cpdef void on_trade_data(self, OKXTrades event)
    cpdef void on_funding_data(self, OKXFundingRate event)
    cpdef void on_delivery_data(self, OKXDelivery event)
    
    # --- cpdef 方法声明 ---
    cpdef dict get_prices(self)
    cpdef double get_position_cashvalue(self)
    cpdef double get_total_margin(self)
    
    # 辅助计算方法 (C 内部调用)
    cdef double _get_position_cashvalue(self)