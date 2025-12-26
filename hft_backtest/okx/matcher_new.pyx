# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: cdivision=True

import math
from hft_backtest.matcher cimport MatchEngine
from hft_backtest.order cimport Order, ORDER_STATE_FILLED, ORDER_STATE_CANCELED, ORDER_STATE_REJECTED, ORDER_STATE_RECEIVED, ORDER_STATE_SUBMITTED
from hft_backtest.event_engine cimport EventEngine
from hft_backtest.okx.event cimport OKXBookticker, OKXTrades, OKXDelivery
from libc.math cimport round, abs

cdef class OKXMatcherNew(MatchEngine):
    
    def __init__(self, str symbol, double taker_fee = 2e-4, double maker_fee = 1.1e-4):
        self.symbol = symbol
        self.taker_fee = taker_fee
        self.maker_fee = maker_fee
        
        # 从 Python Order 类获取 SCALER，或者直接硬编码
        from hft_backtest.order import Order as PyOrder
        self.PRICE_SCALAR = PyOrder.SCALER
        
        self.INIT_RANK = 10.0**9
        
        self.best_bid_price_int = 0
        self.best_ask_price_int = 9223372036854775807 # Max Long as inf

        self.buy_book = []
        self.sell_book = []
        
    cpdef start(self, EventEngine engine):
        self.event_engine = engine
        # Order 是类对象，作为键注册
        from hft_backtest.order import Order as PyOrder
        engine.register(PyOrder, self.on_order)
        engine.register(OKXBookticker, self.on_bookticker)
        engine.register(OKXTrades, self.on_trade)
        engine.register(OKXDelivery, self.on_delivery)

    cdef long to_int_price(self, double price):
        return <long>round(price * self.PRICE_SCALAR)

    cdef void _add_order(self, Order order):
        if order._quantity > 0:
            self.buy_book.append(order)
        else:
            self.sell_book.append(order)

    cdef bint _remove_order(self, Order order):
        cdef Order o
        cdef int i
        # 遍历移除，Cython list 遍历很快
        if order._quantity > 0:
            for i in range(len(self.buy_book)):
                o = self.buy_book[i]
                if o.order_id == order.order_id:
                    self.buy_book.pop(i)
                    return True
        else:
            for i in range(len(self.sell_book)):
                o = self.sell_book[i]
                if o.order_id == order.order_id:
                    self.sell_book.pop(i)
                    return True
        return False

    cdef void fill_order(self, Order order, double filled_price, bint is_taker):
        cdef Order new_order = order.derive()
        new_order.state = ORDER_STATE_FILLED
        new_order.filled_price = filled_price
        cdef double amount = abs(filled_price * new_order._quantity)
        new_order.commission_fee = amount * self.taker_fee if is_taker else amount * self.maker_fee
        
        self._remove_order(order)
        self.event_engine.put(new_order)

    cdef void cancel_order(self, Order order):
        cdef Order new_order = order.derive()
        if self._remove_order(order):
            new_order.state = ORDER_STATE_CANCELED
        else:
            new_order.state = ORDER_STATE_REJECTED
        self.event_engine.put(new_order)

    cpdef on_order(self, Order order):
        if order.symbol != self.symbol:
            return
        
        # state 是 int
        cdef bint is_submitted = (order.state == ORDER_STATE_SUBMITTED)
        cdef bint is_cancel = (order.order_type == 3) # ORDER_TYPE_CANCEL
        
        if not (is_submitted or is_cancel):
            return
            
        if is_cancel:
            self.cancel_order(order)
            return
            
        cdef Order new_order = order.derive()
        new_order.state = ORDER_STATE_RECEIVED
        self.event_engine.put(new_order)
        
        cdef bint is_buy = order._quantity > 0
        cdef long match_price_int
        if is_buy:
            match_price_int = self.best_ask_price_int
        else:
            match_price_int = self.best_bid_price_int
            
        cdef bint should_fill = False
        # ORDER_TYPE_MARKET = 1, LIMIT = 0
        if order.order_type == 1: # Market
            should_fill = True
        elif order.order_type == 0: # Limit
            # 计算并缓存 price_int
            order._price_int_cache = self.to_int_price(order._price)
            order._price_cache_valid = True
            
            if is_buy:
                should_fill = (order._price_int_cache >= match_price_int)
            else:
                should_fill = (order._price_int_cache <= match_price_int)
                
        if should_fill:
            self.fill_order(order, match_price_int / <double>self.PRICE_SCALAR, True)
            return
            
        order.rank = self.INIT_RANK
        # 如果是限价单但没成交，确保 int price 已缓存
        if not order._price_cache_valid:
            order._price_int_cache = self.to_int_price(order._price)
            order._price_cache_valid = True
        
        self._add_order(order)

    cpdef on_delivery(self, OKXDelivery event):
        if event.symbol != self.symbol:
            return
        self.stop()
        
    cpdef on_bookticker(self, OKXBookticker event):
        if event.symbol != self.symbol:
            return
            
        # 1. Update BBO
        self.best_bid_price_int = self.to_int_price(event.bid_price_1)
        self.best_ask_price_int = self.to_int_price(event.ask_price_1)
        
        # 2. Extract top 5 levels for fast lookup (避免创建 dict)
        cdef long ask_p[5]
        cdef double ask_q[5]
        cdef long bid_p[5]
        cdef double bid_q[5]
        
        ask_p[0] = self.to_int_price(event.ask_price_1); ask_q[0] = event.ask_amount_1
        ask_p[1] = self.to_int_price(event.ask_price_2); ask_q[1] = event.ask_amount_2
        ask_p[2] = self.to_int_price(event.ask_price_3); ask_q[2] = event.ask_amount_3
        ask_p[3] = self.to_int_price(event.ask_price_4); ask_q[3] = event.ask_amount_4
        ask_p[4] = self.to_int_price(event.ask_price_5); ask_q[4] = event.ask_amount_5
        
        bid_p[0] = self.to_int_price(event.bid_price_1); bid_q[0] = event.bid_amount_1
        bid_p[1] = self.to_int_price(event.bid_price_2); bid_q[1] = event.bid_amount_2
        bid_p[2] = self.to_int_price(event.bid_price_3); bid_q[2] = event.bid_amount_3
        bid_p[3] = self.to_int_price(event.bid_price_4); bid_q[3] = event.bid_amount_4
        bid_p[4] = self.to_int_price(event.bid_price_5); bid_q[4] = event.bid_amount_5

        # 3. Process Buy Book
        # 复制列表以避免遍历时修改问题 (Python逻辑如此)
        cdef list orders_to_check = list(self.buy_book) 
        cdef Order order
        cdef double qty
        cdef double front_cancel
        cdef long p_int
        cdef int i
        
        for order in orders_to_check:
            p_int = order._price_int_cache
            
            # Check for cross
            if p_int >= self.best_ask_price_int:
                self.fill_order(order, self.best_ask_price_int / <double>self.PRICE_SCALAR, False)
                continue
            
            # Find qty in bids (Lookup 5 levels)
            qty = math.inf
            for i in range(5):
                if bid_p[i] == p_int:
                    qty = bid_q[i]
                    break
            
            # Queue simulation logic (Copied from python)
            front_cancel = max(0.0, order.rank - order.traded - qty)
            order.rank = order.rank - order.traded - front_cancel
            order.traded = 0.0
            
            if order.rank <= -order._quantity:
                self.fill_order(order, order._price, False)

        # 4. Process Sell Book
        orders_to_check = list(self.sell_book)
        for order in orders_to_check:
            p_int = order._price_int_cache
            
            if p_int <= self.best_bid_price_int:
                self.fill_order(order, self.best_bid_price_int / <double>self.PRICE_SCALAR, False)
                continue
                
            qty = math.inf
            for i in range(5):
                if ask_p[i] == p_int:
                    qty = ask_q[i]
                    break
            
            front_cancel = max(0.0, order.rank - order.traded - qty)
            order.rank = order.rank - order.traded - front_cancel
            order.traded = 0.0
            
            if order.rank <= -order._quantity: 
                self.fill_order(order, order._price, False)

    cpdef on_trade(self, OKXTrades event):
        if event.symbol != self.symbol:
            return
            
        cdef list orders_to_check
        cdef Order order
        cdef long price_int = self.to_int_price(event.price)
        
        if event.side == 'buy':
            self.best_ask_price_int = price_int
            orders_to_check = list(self.sell_book)
            for order in orders_to_check:
                if order._price_int_cache < self.best_ask_price_int:
                    self.fill_order(order, order._price, False)
                elif order._price_int_cache == self.best_ask_price_int:
                    order.traded += event.size
                    # 原逻辑: if (order.rank - order.traded) <= -order.quantity:
                    if (order.rank - order.traded) <= -order._quantity:
                        self.fill_order(order, order._price, False)
            
            orders_to_check = list(self.buy_book)
            for order in orders_to_check:
                if order._price_int_cache >= self.best_ask_price_int:
                    self.fill_order(order, self.best_ask_price_int / <double>self.PRICE_SCALAR, False)
                    
        else: # side == 'sell' (taker sell, matches bids)
            self.best_bid_price_int = price_int
            orders_to_check = list(self.sell_book)
            for order in orders_to_check:
                if order._price_int_cache <= self.best_bid_price_int:
                    self.fill_order(order, self.best_bid_price_int / <double>self.PRICE_SCALAR, False)
            
            orders_to_check = list(self.buy_book)
            for order in orders_to_check:
                if order._price_int_cache > self.best_bid_price_int:
                    self.fill_order(order, order._price, False)
                    continue
                if order._price_int_cache == self.best_bid_price_int:
                    order.traded += event.size
                    if (order.rank - order.traded) <= -order._quantity:
                        self.fill_order(order, order._price, False)