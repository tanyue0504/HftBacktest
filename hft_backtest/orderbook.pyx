# cython: language_level=3
from libcpp.vector cimport vector
from hft_backtest.orderbook cimport OrderBook as CppOrderBook, Fill
from libc.math cimport round

# 配置全局精度
cdef long long SCALE = 100000000 # 1e8

class PyFill:
    def __init__(self, order_id, price, qty, is_maker):
        self.order_id = order_id
        # 转回 float 给 Python 用
        self.price = price / float(SCALE)
        self.qty = qty / float(SCALE)
        self.is_maker = is_maker
    
    def __repr__(self):
        return f"Fill(id={self.order_id}, px={self.price}, qty={self.qty})"

cdef class PyOrderBook:
    cdef CppOrderBook* _core

    def __cinit__(self):
        self._core = new CppOrderBook()

    def __dealloc__(self):
        if self._core:
            del self._core

    def add_order(self, unsigned long long oid, bool is_buy, double price, double qty, double initial_rank):
        # Python(Float) -> C++(Int)
        cdef long long p_int = <long long>round(price * SCALE)
        cdef long long q_int = <long long>round(qty * SCALE)
        cdef long long r_int = <long long>round(initial_rank * SCALE)
        
        self._core.add_order(oid, is_buy, p_int, q_int, r_int)

    def cancel_order(self, unsigned long long oid):
        self._core.cancel_order(oid)

    def reduce_qty(self, unsigned long long oid, double delta):
        cdef long long d_int = <long long>round(delta * SCALE)
        self._core.reduce_qty(oid, d_int)

    def update_bbo(self, bool is_buy, double price, double market_qty):
        cdef long long p_int = <long long>round(price * SCALE)
        cdef long long q_int = <long long>round(market_qty * SCALE)
        self._core.update_bbo(is_buy, p_int, q_int)

    def execute_trade(self, bool maker_is_buy, double price, double volume):
        cdef long long p_int = <long long>round(price * SCALE)
        cdef long long v_int = <long long>round(volume * SCALE)
        self._core.execute_trade(maker_is_buy, p_int, v_int)

    def get_fills(self):
        cdef vector[Fill] fills = self._core.get_fills()
        cdef list result = []
        for f in fills:
            result.append(PyFill(f.order_id, f.price, f.qty, f.is_maker))
        return result
    
    def has_order(self, unsigned long long oid):
        return self._core.has_order(oid)