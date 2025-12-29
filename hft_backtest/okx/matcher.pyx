# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: cdivision=True

import math
from hft_backtest.matcher cimport MatchEngine
from hft_backtest.order import Order
from hft_backtest.order cimport (
    Order, 
    ORDER_STATE_FILLED, 
    ORDER_STATE_CANCELED, 
    ORDER_STATE_RECEIVED, 
    ORDER_STATE_SUBMITTED,
    ORDER_TYPE_LIMIT,
    ORDER_TYPE_MARKET,
    ORDER_TYPE_CANCEL,
    ORDER_TYPE_TRACKING
)
from hft_backtest.event_engine cimport EventEngine
from hft_backtest.okx.event cimport OKXBookticker, OKXTrades, OKXDelivery
from libc.math cimport abs, fmax

# Constant for Max Ask Price (Max Long)
cdef long MAX_ASK = 9223372036854

cdef class OKXMatcher(MatchEngine):
    
    def __init__(self, str symbol, double taker_fee = 2e-4, double maker_fee = 1.1e-4):
        self.symbol = symbol
        self.taker_fee = taker_fee
        self.maker_fee = maker_fee
        
        from hft_backtest.order import Order as PyOrder
        self.PRICE_SCALAR = PyOrder.SCALER
        
        self.INIT_RANK = 10.0**9
        
        self.best_bid_price_int = 0
        self.best_ask_price_int = MAX_ASK

        self.buy_book = []
        self.sell_book = []
    
    cpdef start(self, EventEngine engine):
        self.event_engine = engine
        engine.register(Order, self.on_order)
        engine.register(OKXBookticker, self.on_bookticker)
        engine.register(OKXTrades, self.on_trade)
        engine.register(OKXDelivery, self.on_delivery)

    # --- Price Conversion ---
    cdef inline long _to_int(self, double price):
        return <long>(price * self.PRICE_SCALAR + 0.5)

    cpdef long to_int_price(self, double price):
        return self._to_int(price)

    # --- Order Book Ops ---
    cdef void _add_order(self, Order order):
        if order.quantity > 0:
            self.buy_book.append(order)
        else:
            self.sell_book.append(order)

    cdef bint _remove_order(self, Order order):
        cdef Order o
        cdef int i
        if order.quantity > 0:
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
        cdef double amount = abs(filled_price * new_order.quantity)
        new_order.commission_fee = amount * self.taker_fee if is_taker else amount * self.maker_fee
        
        self._remove_order(order)
        self.event_engine.put(new_order)

    cdef void cancel_order(self, Order order):
        cdef Order new_order
        if self._remove_order(order):
            new_order = order.derive()
            new_order.state = ORDER_STATE_CANCELED
            self.event_engine.put(new_order)

    # --- Unrolled Binary Search (Ask: Ascending) ---
    cdef double _search_ask_book(self, OKXBookticker event, long target):
        cdef long p
        
        if target < self._to_int(event.ask_price_1): return 0.0
        if target > self._to_int(event.ask_price_25): return self.INIT_RANK
        
        p = self._to_int(event.ask_price_13)
        if target == p: return event.ask_amount_13
        
        if target < p:
            p = self._to_int(event.ask_price_6)
            if target == p: return event.ask_amount_6
            if target < p:
                p = self._to_int(event.ask_price_3)
                if target == p: return event.ask_amount_3
                if target < p:
                    p = self._to_int(event.ask_price_1)
                    if target == p: return event.ask_amount_1
                    if target > p:
                        p = self._to_int(event.ask_price_2)
                        if target == p: return event.ask_amount_2
                else:
                    p = self._to_int(event.ask_price_4)
                    if target == p: return event.ask_amount_4
                    if target > p:
                        p = self._to_int(event.ask_price_5)
                        if target == p: return event.ask_amount_5
            else:
                p = self._to_int(event.ask_price_9)
                if target == p: return event.ask_amount_9
                if target < p:
                    p = self._to_int(event.ask_price_7)
                    if target == p: return event.ask_amount_7
                    if target > p:
                        p = self._to_int(event.ask_price_8)
                        if target == p: return event.ask_amount_8
                else:
                    p = self._to_int(event.ask_price_11)
                    if target == p: return event.ask_amount_11
                    if target < p:
                        p = self._to_int(event.ask_price_10)
                        if target == p: return event.ask_amount_10
                    elif target > p:
                        p = self._to_int(event.ask_price_12)
                        if target == p: return event.ask_amount_12
        else:
            p = self._to_int(event.ask_price_19)
            if target == p: return event.ask_amount_19
            if target < p:
                p = self._to_int(event.ask_price_16)
                if target == p: return event.ask_amount_16
                if target < p:
                    p = self._to_int(event.ask_price_14)
                    if target == p: return event.ask_amount_14
                    if target > p:
                        p = self._to_int(event.ask_price_15)
                        if target == p: return event.ask_amount_15
                else:
                    p = self._to_int(event.ask_price_17)
                    if target == p: return event.ask_amount_17
                    if target > p:
                        p = self._to_int(event.ask_price_18)
                        if target == p: return event.ask_amount_18
            else:
                p = self._to_int(event.ask_price_22)
                if target == p: return event.ask_amount_22
                if target < p:
                    p = self._to_int(event.ask_price_20)
                    if target == p: return event.ask_amount_20
                    if target > p:
                        p = self._to_int(event.ask_price_21)
                        if target == p: return event.ask_amount_21
                else:
                    p = self._to_int(event.ask_price_24)
                    if target == p: return event.ask_amount_24
                    if target < p:
                        p = self._to_int(event.ask_price_23)
                        if target == p: return event.ask_amount_23
                    elif target > p:
                        p = self._to_int(event.ask_price_25)
                        if target == p: return event.ask_amount_25
        return 0.0

    # --- Unrolled Binary Search (Bid: Descending) ---
    cdef double _search_bid_book(self, OKXBookticker event, long target):
        cdef long p
        
        if target > self._to_int(event.bid_price_1): return 0.0
        if target < self._to_int(event.bid_price_25): return self.INIT_RANK
        
        p = self._to_int(event.bid_price_13)
        if target == p: return event.bid_amount_13
        
        if target > p:
            p = self._to_int(event.bid_price_6)
            if target == p: return event.bid_amount_6
            if target > p:
                p = self._to_int(event.bid_price_3)
                if target == p: return event.bid_amount_3
                if target > p:
                    p = self._to_int(event.bid_price_1)
                    if target == p: return event.bid_amount_1
                    if target < p:
                        p = self._to_int(event.bid_price_2)
                        if target == p: return event.bid_amount_2
                else:
                    p = self._to_int(event.bid_price_4)
                    if target == p: return event.bid_amount_4
                    if target < p:
                        p = self._to_int(event.bid_price_5)
                        if target == p: return event.bid_amount_5
            else:
                p = self._to_int(event.bid_price_9)
                if target == p: return event.bid_amount_9
                if target > p:
                    p = self._to_int(event.bid_price_7)
                    if target == p: return event.bid_amount_7
                    if target < p:
                        p = self._to_int(event.bid_price_8)
                        if target == p: return event.bid_amount_8
                else:
                    p = self._to_int(event.bid_price_11)
                    if target == p: return event.bid_amount_11
                    if target > p:
                        p = self._to_int(event.bid_price_10)
                        if target == p: return event.bid_amount_10
                    elif target < p:
                        p = self._to_int(event.bid_price_12)
                        if target == p: return event.bid_amount_12
        else:
            p = self._to_int(event.bid_price_19)
            if target == p: return event.bid_amount_19
            if target > p:
                p = self._to_int(event.bid_price_16)
                if target == p: return event.bid_amount_16
                if target > p:
                    p = self._to_int(event.bid_price_14)
                    if target == p: return event.bid_amount_14
                    if target < p:
                        p = self._to_int(event.bid_price_15)
                        if target == p: return event.bid_amount_15
                else:
                    p = self._to_int(event.bid_price_17)
                    if target == p: return event.bid_amount_17
                    if target < p:
                        p = self._to_int(event.bid_price_18)
                        if target == p: return event.bid_amount_18
            else:
                p = self._to_int(event.bid_price_22)
                if target == p: return event.bid_amount_22
                if target > p:
                    p = self._to_int(event.bid_price_20)
                    if target == p: return event.bid_amount_20
                    if target < p:
                        p = self._to_int(event.bid_price_21)
                        if target == p: return event.bid_amount_21
                else:
                    p = self._to_int(event.bid_price_24)
                    if target == p: return event.bid_amount_24
                    if target > p:
                        p = self._to_int(event.bid_price_23)
                        if target == p: return event.bid_amount_23
                    elif target < p:
                        p = self._to_int(event.bid_price_25)
                        if target == p: return event.bid_amount_25
        return 0.0

    cpdef on_order(self, Order order):
        if order.symbol != self.symbol: return
        
        if not (order.is_submitted or order.is_cancel_order):
            return
        if order.is_cancel_order:
            self.cancel_order(order)
            return

        cdef bint is_buy = order.quantity > 0
        cdef Order new_order = order.derive()
        
        # Tracking Order
        if new_order.is_tracking_order:
            new_order.order_type = ORDER_TYPE_LIMIT
            if is_buy:
                new_order.price = self.best_bid_price_int / <double>self.PRICE_SCALAR
            else:
                new_order.price = self.best_ask_price_int / <double>self.PRICE_SCALAR
        new_order.state = ORDER_STATE_RECEIVED
        self.event_engine.put(new_order)
        
        cdef long match_price_int = self.best_ask_price_int if is_buy else self.best_bid_price_int
        cdef bint should_fill = False
        cdef long order_p_int
        
        if new_order.is_market_order:
            should_fill = True
        elif new_order.is_limit_order:
            order_p_int = new_order.price_int
            if is_buy: should_fill = (order_p_int >= match_price_int)
            else: should_fill = (order_p_int <= match_price_int)
                
        if should_fill:
            self.fill_order(new_order, match_price_int / <double>self.PRICE_SCALAR, True)
            return
            
        new_order.rank = self.INIT_RANK
        order_p_int = new_order.price_int # cache
        self._add_order(new_order)

    cpdef on_delivery(self, OKXDelivery event):
        if event.symbol != self.symbol: return
        self.stop()
        
    cpdef on_bookticker(self, OKXBookticker event):
        if event.symbol != self.symbol: return
            
        self.best_bid_price_int = self._to_int(event.bid_price_1)
        self.best_ask_price_int = self._to_int(event.ask_price_1)
        
        cdef list orders_to_check = list(self.buy_book) 
        cdef Order order
        cdef double qty
        cdef double front_cancel
        cdef long p_int
        
        for order in orders_to_check:
            p_int = order.price_int
            if p_int >= self.best_ask_price_int:
                self.fill_order(order, self.best_ask_price_int / <double>self.PRICE_SCALAR, False)
                continue

            qty = self._search_bid_book(event, p_int)
            front_cancel = fmax(0.0, order.rank - order.traded - qty)
            order.rank = order.rank - order.traded - front_cancel
            order.traded = 0.0
            # 买单数量为正
            if order.rank <= -order.quantity:
                self.fill_order(order, order.price, False)

        orders_to_check = list(self.sell_book)
        for order in orders_to_check:
            p_int = order.price_int
            if p_int <= self.best_bid_price_int:
                self.fill_order(order, self.best_bid_price_int / <double>self.PRICE_SCALAR, False)
                continue
                
            qty = self._search_ask_book(event, p_int)
            front_cancel = fmax(0.0, order.rank - order.traded - qty)
            order.rank = order.rank - order.traded - front_cancel
            order.traded = 0.0
            # 卖单数量为负
            if order.rank <= order.quantity: 
                self.fill_order(order, order.price, False)

    cpdef on_trade(self, OKXTrades event):
        if event.symbol != self.symbol: return
            
        cdef list orders_to_check
        cdef Order order
        cdef long price_int = self._to_int(event.price)
        cdef long order_p_int
        
        if event.side == 'buy':
            self.best_ask_price_int = price_int
            orders_to_check = list(self.sell_book)
            for order in orders_to_check:
                order_p_int = order.price_int
                if order_p_int < self.best_ask_price_int:
                    self.fill_order(order, order.price, False)
                elif order_p_int == self.best_ask_price_int:
                    order.traded += event.size
                    # 卖单数量为负
                    if (order.rank - order.traded) <= order.quantity:
                        self.fill_order(order, order.price, False)
            
            orders_to_check = list(self.buy_book)
            for order in orders_to_check:
                if order.price_int >= self.best_ask_price_int:
                    self.fill_order(order, self.best_ask_price_int / <double>self.PRICE_SCALAR, False)
                    
        else:
            self.best_bid_price_int = price_int
            orders_to_check = list(self.sell_book)
            for order in orders_to_check:
                if order.price_int <= self.best_bid_price_int:
                    self.fill_order(order, self.best_bid_price_int / <double>self.PRICE_SCALAR, False)
            
            orders_to_check = list(self.buy_book)
            for order in orders_to_check:
                order_p_int = order.price_int
                if order_p_int > self.best_bid_price_int:
                    self.fill_order(order, order.price, False)
                    continue
                if order_p_int == self.best_bid_price_int:
                    order.traded += event.size
                    if (order.rank - order.traded) <= -order.quantity:
                        self.fill_order(order, order.price, False)