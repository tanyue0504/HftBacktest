# cython: language_level=3
from hft_backtest.event_engine cimport Component, EventEngine
from hft_backtest.order cimport Order

cdef class MatchEngine(Component):
    """
    撮合引擎抽象基类
    监听订单事件和数据事件，处理订单撮合逻辑
    订单状态发生变化时，推送订单最新状态到事件引擎
    """
    
    cpdef on_order(self, Order order):
        """处理订单事件的抽象方法"""
        pass

    cpdef start(self, EventEngine engine):
        raise NotImplementedError("MatchEngine.start must be implemented")

    cpdef stop(self):
        pass