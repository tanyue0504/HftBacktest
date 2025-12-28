# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: cdivision=True

import math
from hft_backtest.matcher cimport MatchEngine
from hft_backtest.order cimport (
    Order, 
    ORDER_STATE_FILLED, 
    ORDER_STATE_CANCELED, 
    ORDER_STATE_REJECTED, 
    ORDER_STATE_RECEIVED, 
    ORDER_STATE_SUBMITTED,
    ORDER_TYPE_LIMIT,
    ORDER_TYPE_MARKET,
    ORDER_TYPE_CANCEL,
    ORDER_TYPE_TRACKING
)
from hft_backtest.event_engine cimport EventEngine
from hft_backtest.okx.event cimport OKXBookticker, OKXTrades, OKXDelivery
from libc.math cimport round, abs, fmax

cdef class OKXMatcher(MatchEngine):
    
    def __init__(self, str symbol, double taker_fee = 2e-4, double maker_fee = 1.1e-4):
        self.symbol = symbol
        self.taker_fee = taker_fee
        self.maker_fee = maker_fee
        
        from hft_backtest.order import Order as PyOrder
        self.PRICE_SCALAR = PyOrder.SCALER
        
        self.INIT_RANK = 10.0**9
        
        self.best_bid_price_int = 0
        self.best_ask_price_int = 9223372036854775807 # Max Long

        self.buy_book = []
        self.sell_book = []
    
    cpdef start(self, EventEngine engine):
        self.event_engine = engine
        from hft_backtest.order import Order as PyOrder
        engine.register(PyOrder, self.on_order)
        engine.register(OKXBookticker, self.on_bookticker)
        engine.register(OKXTrades, self.on_trade)
        engine.register(OKXDelivery, self.on_delivery)

    cdef long to_int_price(self, double price):
        # 保持与 Order.price_int 一致的舍入逻辑
        if price >= 0:
            return <long>(price * self.PRICE_SCALAR + 0.5)
        else:
            return <long>(price * self.PRICE_SCALAR - 0.5)

    cdef void _add_order(self, Order order):
        if order._quantity > 0:
            self.buy_book.append(order)
        else:
            self.sell_book.append(order)

    cdef bint _remove_order(self, Order order):
        cdef Order o
        cdef int i
        # 遍历移除，HFT场景下挂单通常不多，List遍历足够快
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
        cdef Order new_order
        # 【优化】只在成功移除订单时推送 CANCELED 事件
        # 如果订单已成交或已撤单，则静默失败，不推送 REJECTED，减少无效消息
        if self._remove_order(order):
            new_order = order.derive()
            new_order.state = ORDER_STATE_CANCELED
            self.event_engine.put(new_order)

    cdef double _get_level_volume(self, OKXBookticker event, bint is_ask, long target_price_int):
        """
        使用二分查找在 25 档行情中快速查找指定价格的量。
        OKXBookticker 内存布局: [ask_p, ask_q, bid_p, bid_q] * 25
        """
        cdef double* ptr = <double*>&event.ask_price_1
        cdef int low = 0
        cdef int high = 24
        cdef int mid
        cdef long mid_price
        cdef long min_price
        cdef long max_price
        
        # 偏移量: Ask P=0, Ask Q=1; Bid P=2, Bid Q=3
        # 步长: 4
        
        if is_ask:
            # --- Ask 队列 (升序) ---
            # 边界检查
            min_price = self.to_int_price(ptr[0])        # Ask 1 Price
            max_price = self.to_int_price(ptr[24 * 4])   # Ask 25 Price
            
            if target_price_int < min_price:
                return 0.0 # 优于盘口 (已穿价)
            if target_price_int > max_price:
                return float('inf') # 劣于盘尾 (排在后面)
                
            # 二分查找
            while low <= high:
                mid = (low + high) >> 1
                mid_price = self.to_int_price(ptr[mid * 4])
                
                if mid_price == target_price_int:
                    return ptr[mid * 4 + 1] # Return Ask Vol
                elif mid_price < target_price_int:
                    low = mid + 1
                else:
                    high = mid - 1
            
            # 在范围内但未匹配到 (间隙)
            return 0.0
            
        else:
            # --- Bid 队列 (降序) ---
            # 边界检查
            max_price = self.to_int_price(ptr[2])        # Bid 1 Price (Max)
            min_price = self.to_int_price(ptr[24 * 4 + 2]) # Bid 25 Price (Min)
            
            if target_price_int > max_price:
                return 0.0 # 优于盘口
            if target_price_int < min_price:
                return float('inf') # 劣于盘尾
                
            # 二分查找 (降序)
            while low <= high:
                mid = (low + high) >> 1
                mid_price = self.to_int_price(ptr[mid * 4 + 2])
                
                if mid_price == target_price_int:
                    return ptr[mid * 4 + 3] # Return Bid Vol
                elif mid_price > target_price_int: # 注意方向
                    low = mid + 1
                else:
                    high = mid - 1
                    
            return 0.0

    cpdef on_order(self, Order order):
        if order.symbol != self.symbol:
            return
        
        # 使用常量判断，性能优于属性访问
        cdef bint is_submitted = (order.state == ORDER_STATE_SUBMITTED)
        cdef bint is_cancel = (order.order_type == ORDER_TYPE_CANCEL)
        
        if not (is_submitted or is_cancel):
            return
            
        # 1. 撤单指令处理 (保持不变)
        if is_cancel:
            self.cancel_order(order)
            return

        cdef bint is_buy = order._quantity > 0
        cdef Order new_order = order.derive()
        
        # 2. [新增] Tracking (跟随/本方最优) 订单处理逻辑
        # 必须在发送 RECEIVED 回报之前处理，确保回报中的价格和类型是修正后的
        if new_order.order_type == ORDER_TYPE_TRACKING:
            if is_buy:
                # 买单 Tracking -> 挂在买一价 (Best Bid)
                if self.best_bid_price_int > 0:
                    new_order.order_type = ORDER_TYPE_LIMIT
                    new_order._price_int_cache = self.best_bid_price_int
                    # 反算浮点价格用于显示和记录
                    new_order._price = self.best_bid_price_int / <double>self.PRICE_SCALAR
                    new_order._price_cache_valid = True
                else:
                    new_order.state = ORDER_STATE_REJECTED
                    self.event_engine.put(new_order)
                    return
            else:
                # 卖单 Tracking -> 挂在卖一价 (Best Ask)
                if self.best_ask_price_int < 9223372036854775807:
                    new_order.order_type = ORDER_TYPE_LIMIT
                    new_order._price_int_cache = self.best_ask_price_int
                    new_order._price = self.best_ask_price_int / <double>self.PRICE_SCALAR
                    new_order._price_cache_valid = True
                else:
                    new_order.state = ORDER_STATE_REJECTED
                    self.event_engine.put(new_order)
                    return

        # 3. 推送 RECEIVED 回报 (此时订单已经是 LIMIT 类型，价格已修正)
        new_order.state = ORDER_STATE_RECEIVED
        self.event_engine.put(new_order)
        
        # 4. 撮合逻辑 (统一处理 Limit / Market)
        cdef long match_price_int
        if is_buy:
            match_price_int = self.best_ask_price_int
        else:
            match_price_int = self.best_bid_price_int
            
        cdef bint should_fill = False
        
        if new_order.order_type == ORDER_TYPE_MARKET:
            should_fill = True
        elif new_order.order_type == ORDER_TYPE_LIMIT:
            # 缓存价格 (如果是 Tracking 转过来的，这里其实已经 valid 了，但防守性编程再检查一次)
            if not new_order._price_cache_valid:
                new_order._price_int_cache = self.to_int_price(new_order._price)
                new_order._price_cache_valid = True
            
            if is_buy:
                should_fill = (new_order._price_int_cache >= match_price_int)
            else:
                should_fill = (new_order._price_int_cache <= match_price_int)
                
        if should_fill:
            self.fill_order(new_order, match_price_int / <double>self.PRICE_SCALAR, True)
            return
            
        # 5. 入队挂单
        new_order.rank = self.INIT_RANK
        if not new_order._price_cache_valid: # Double check
            new_order._price_int_cache = self.to_int_price(new_order._price)
            new_order._price_cache_valid = True
        
        self._add_order(new_order)

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
        
        # 2. Process Buy Book
        # 注意: 拷贝列表以防在遍历中修改
        cdef list orders_to_check = list(self.buy_book) 
        cdef Order order
        cdef double qty
        cdef double front_cancel
        cdef long p_int
        
        for order in orders_to_check:
            p_int = order._price_int_cache
            
            # Cross Check
            if p_int >= self.best_ask_price_int:
                self.fill_order(order, self.best_ask_price_int / <double>self.PRICE_SCALAR, False)
                continue

            # Queue Simulation
            # 买单排在 Bid 队列，查找 Bid (is_ask=False)
            qty = self._get_level_volume(event, False, p_int)
            
            # 【优化】使用 fmax
            front_cancel = fmax(0.0, order.rank - order.traded - qty)
            order.rank = order.rank - order.traded - front_cancel
            order.traded = 0.0
            
            if order.rank <= -order._quantity:
                self.fill_order(order, order._price, False)

        # 3. Process Sell Book
        orders_to_check = list(self.sell_book)
        for order in orders_to_check:
            p_int = order._price_int_cache
            
            if p_int <= self.best_bid_price_int:
                self.fill_order(order, self.best_bid_price_int / <double>self.PRICE_SCALAR, False)
                continue
                
            # 卖单排在 Ask 队列，查找 Ask (is_ask=True)
            qty = self._get_level_volume(event, True, p_int)
            
            front_cancel = fmax(0.0, order.rank - order.traded - qty)
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
            # 主动买入，推高价格，更新 Ask BBO (逻辑上)
            self.best_ask_price_int = price_int
            orders_to_check = list(self.sell_book)
            for order in orders_to_check:
                # 低于现价的卖单全部成交
                if order._price_int_cache < self.best_ask_price_int:
                    self.fill_order(order, order._price, False)
                # 等于现价的卖单，减少排队量
                elif order._price_int_cache == self.best_ask_price_int:
                    order.traded += event.size
                    if (order.rank - order.traded) <= -order._quantity:
                        self.fill_order(order, order._price, False)
            
            # 检查 Buy Book 是否有人挂的比现价还高 (异常情况或穿价)
            orders_to_check = list(self.buy_book)
            for order in orders_to_check:
                if order._price_int_cache >= self.best_ask_price_int:
                    self.fill_order(order, self.best_ask_price_int / <double>self.PRICE_SCALAR, False)
                    
        else: # side == 'sell'
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