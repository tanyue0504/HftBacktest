# cython: language_level=3
from libcpp.vector cimport vector
from libcpp cimport bool

cdef extern from "orderbook.h":
    struct Fill:
        unsigned long long order_id
        long long price
        long long qty
        bool is_maker

    cdef cppclass OrderBook:
        OrderBook() except +
        
        void add_order(unsigned long long id, bool is_buy, long long price, long long qty, long long initial_rank)
        void cancel_order(unsigned long long id)
        void reduce_qty(unsigned long long id, long long delta)
        
        void update_bbo(bool is_buy, long long price, long long market_qty)
        void execute_trade(bool maker_is_buy, long long price, long long volume)
        
        vector[Fill] get_fills()
        bool has_order(unsigned long long id)