from collections import deque, defaultdict
from hft_backtest import MatchEngine, Order, OrderState, OrderType, Data

class BinanceMatcher(MatchEngine):
    """
    Binance 高频撮合引擎 (最终优化版)
    
    Data Structures:
    - OrderBook: Symbol -> Side -> Price(Int) -> Deque[Order]
    - Pending: Symbol -> Deque[Order]
    
    Key Logics:
    1. Scaled Integer: Global scalar 1e8 for safe price comparison.
    2. Lazy Bounds: Maintain max_buy/min_sell, recalculate only on depletion.
    3. Strict Sequencing: Maintenance -> Entry -> Cache Update.
    4. Truth Table Matching: Crossing(Fill) / Capture(Fill) / Queue(Rank).
    """
    
    PRICE_SCALAR = 100_000_000  # 1e8，支持8位小数精度
    SIDE_BUY = 0
    SIDE_SELL = 1

    def __init__(
        self,
        taker_fee: float = 2e-4,
        maker_fee: float = 1.1e-4,
    ):
        self.taker_fee = taker_fee
        self.maker_fee = maker_fee
        
        # --- 数据结构 ---
        
        # 等待队列：Symbol -> Deque[Order]
        self.pending_order_dict = defaultdict(deque)
        
        # 核心订单簿：Symbol -> Side (0/1) -> Price(Int) -> Deque[Order]
        # 使用 lambda 嵌套实现自动初始化
        self.order_book = defaultdict(lambda: {
            self.SIDE_BUY: defaultdict(deque),
            self.SIDE_SELL: defaultdict(deque)
        })
        
        # 极值缓存：Symbol -> {'max_buy': int|None, 'min_sell': int|None}
        self.bounds = defaultdict(lambda: {'max_buy': None, 'min_sell': None})
        
        # 辅助索引：Order ID -> (Symbol, Side, PriceInt)
        # 用于快速定位撤单
        self.order_index = {}

        # 数据分发
        self.data_processors = {
            "bookTicker": self.process_bookTicker_data,
            "trades": self.process_trades_data,
        }

    # ==========================
    # Helper: 价格转换与账本维护
    # ==========================

    def to_int_price(self, price: float) -> int:
        """ 将浮点价格转换为整数，避免精度问题 """
        return int(round(price * self.PRICE_SCALAR))

    def _add_order_to_book(self, order: Order, price_int: int, side: int):
        """ 将订单加入订单簿并维护极值 """
        symbol = order.symbol
        book = self.order_book[symbol][side]
        bounds = self.bounds[symbol]
        
        # 1. 入库
        book[price_int].append(order)
        self.order_index[order.order_id] = (symbol, side, price_int)
        
        # 2. 维护极值 (O(1))
        if side == self.SIDE_BUY:
            if bounds['max_buy'] is None or price_int > bounds['max_buy']:
                bounds['max_buy'] = price_int
        else:
            if bounds['min_sell'] is None or price_int < bounds['min_sell']:
                bounds['min_sell'] = price_int

    def _remove_order_from_book(self, order: Order):
        """ 从订单簿移除订单并维护极值 (Lazy Update) """
        if order.order_id not in self.order_index:
            return

        symbol, side, price_int = self.order_index[order.order_id]
        
        # 1. 从 deque 移除 (注意：这里假设 Order 对象引用一致，deque.remove 是 O(N))
        # 在极高频优化中，可以使用双向链表节点。但在 Python deque 中，若 N 不大尚可接受。
        try:
            self.order_book[symbol][side][price_int].remove(order)
        except ValueError:
            pass # 已经被删除了
            
        del self.order_index[order.order_id]
        
        # 2. 检查 Bucket 是否空了
        if not self.order_book[symbol][side][price_int]:
            del self.order_book[symbol][side][price_int]
            
            # 3. 只有当删除了极值 Bucket 时，才触发 O(K) 重算
            bounds = self.bounds[symbol]
            if side == self.SIDE_BUY:
                if price_int == bounds['max_buy']:
                    keys = self.order_book[symbol][side].keys()
                    bounds['max_buy'] = max(keys) if keys else None
            else:
                if price_int == bounds['min_sell']:
                    keys = self.order_book[symbol][side].keys()
                    bounds['min_sell'] = min(keys) if keys else None

    def fill_order(self, order: Order, filled_price: float, is_taker: bool):
        """ 原子成交 """
        # 使用derive方法创建新事件，避免修改原事件导致时间戳问题
        new_order = order.derive()
        new_order.state = OrderState.FILLED
        new_order.filled_price = filled_price
        
        raw_fee = abs(filled_price * order.quantity)
        new_order.commission_fee = raw_fee * self.taker_fee if is_taker else raw_fee * self.maker_fee
        
        # 从账本中移除
        self._remove_order_from_book(order)
        self.event_engine.put(new_order)

    # ==========================
    # Core: 事件入口
    # ==========================

    def on_order(self, order: Order):
        if not (order.is_cancel or order.state == OrderState.SUBMITTED):
            return
        
        assert order.order_id not in self.order_index
        
        # 使用derive方法创建新事件，避免修改原事件导致时间戳问题
        new_order = order.derive()
        new_order.state = OrderState.RECEIVED
        
        self.pending_order_dict[order.symbol].append(new_order)

    def on_data(self, data: Data):
        assert data.name in self.data_processors
        self.data_processors[data.name](data)

    # ==========================
    # Logic: 订单处理流程
    # ==========================

    def _process_new_entry_order(self, order: Order, line, bid_int: int, ask_int: int):
        """ 处理 Pending 订单入场 """
        # Tracking Order 转换
        if order.order_type == OrderType.TRACKING_ORDER:
            order.order_type = OrderType.LIMIT_ORDER
            if order.quantity > 0:
                order.price = line.best_ask_price
                order._price_int = ask_int
            else:
                order.price = line.best_bid_price
                order._price_int = bid_int

        # --- Limit Buy ---
        if order.quantity > 0:
            # 1. Taker (Crossing Ask)
            if order._price_int >= ask_int:
                self.fill_order(order, line.best_ask_price, is_taker=True)
                return

            # 2. Maker (Init Rank or None)
            if order._price_int == bid_int:
                order.rank = line.best_bid_qty
                order.traded = 0
            else:
                order.rank = None
                order.traded = 0
            
            self._add_order_to_book(order, order._price_int, self.SIDE_BUY)
            # 推送事件：订单已挂入
            self.event_engine.put(order)

        # --- Limit Sell ---
        elif order.quantity < 0:
            # 1. Taker (Crossing Bid)
            if order._price_int <= bid_int:
                self.fill_order(order, line.best_bid_price, is_taker=True)
                return

            # 2. Maker (Init Rank or None)
            if order._price_int == ask_int:
                order.rank = line.best_ask_qty
                order.traded = 0
            else:
                order.rank = None
                order.traded = 0
                
            self._add_order_to_book(order, order._price_int, self.SIDE_SELL)
            # 推送事件：订单已挂入
            self.event_engine.put(order)

    def process_bookTicker_data(self, data: Data):
        line = data.data
        symbol = line.symbol
        
        bid_int = self.to_int_price(line.best_bid_price)
        ask_int = self.to_int_price(line.best_ask_price)

        # ==========================
        # Stage 1: Maintenance Phase
        # ==========================
        # 遍历所有存量订单。由于订单分散在 buckets 中，我们需要遍历
        # 这里的遍历效率取决于挂单价位的数量，通常是可以接受的
        
        # --- Update Buy Orders ---
        buy_book = self.order_book[symbol][self.SIDE_BUY]
        if buy_book:
            # 复制 keys 防止运行时修改
            for price_int in list(buy_book.keys()):
                bucket = buy_book[price_int]
                # 对该价位的所有订单进行快照遍历
                for order in list(bucket):
                    # 1. 被动成交 (Ask 砸穿)
                    if price_int >= ask_int:
                        self.fill_order(order, order.price, is_taker=False)
                        continue
                    
                    # 2. 排队维护 (At Bid)
                    elif price_int == bid_int:
                        if order.rank is not None:
                            # FC = max(0, R0 - T - Q1)
                            front_cancel = max(0, order.rank - order.traded - line.best_bid_qty)
                            order.rank = order.rank - order.traded - front_cancel
                            order.traded = 0
                            
                            if order.rank < 0:
                                self.fill_order(order, order.price, is_taker=False)
                        else:
                            # 价格回归 BBO，初始化 Rank
                            order.rank = line.best_bid_qty
                            order.traded = 0
                    
                    # 3. 远离 BBO
                    else:
                        order.rank = None
                        order.traded = 0

        # --- Update Sell Orders ---
        sell_book = self.order_book[symbol][self.SIDE_SELL]
        if sell_book:
            for price_int in list(sell_book.keys()):
                bucket = sell_book[price_int]
                for order in list(bucket):
                    if price_int <= bid_int:
                        self.fill_order(order, order.price, is_taker=False)
                        continue
                    
                    elif price_int == ask_int:
                        if order.rank is not None:
                            front_cancel = max(0, order.rank - order.traded - line.best_ask_qty)
                            order.rank = order.rank - order.traded - front_cancel
                            order.traded = 0
                            
                            if order.rank < 0:
                                self.fill_order(order, order.price, is_taker=False)
                        else:
                            order.rank = line.best_ask_qty
                            order.traded = 0
                    else:
                        order.rank = None
                        order.traded = 0

        # ==========================
        # Stage 2: Entry Phase
        # ==========================
        pending = self.pending_order_dict[symbol]
        while pending:
            order = pending.popleft()
            if order.order_type == OrderType.CANCEL_ORDER:
                self._process_cancel_internal(order)
            elif order.order_type == OrderType.MARKET_ORDER:
                self._process_market_order(order, line)
            else:
                self._process_new_entry_order(order, line, bid_int, ask_int)

    def process_trades_data(self, data: Data):
        """ Walk the Book 撮合 """
        line = data.data
        symbol = line.symbol
        
        # 快速检查：如果没有任何订单，直接返回
        if not self.order_book[symbol][self.SIDE_BUY] and not self.order_book[symbol][self.SIDE_SELL]:
            return
            
        trade_price_int = self.to_int_price(line.price)
        bounds = self.bounds[symbol]

        # ------------------------------------
        # 1. 撮合买单 (Limit Buy)
        # ------------------------------------
        # 穿价逻辑：循环吃掉所有 Buy Price > Trade Price 的单子
        # 使用 max_buy 快速判定
        while bounds['max_buy'] is not None and bounds['max_buy'] > trade_price_int:
            current_max_price = bounds['max_buy']
            bucket = self.order_book[symbol][self.SIDE_BUY][current_max_price]
            
            # 整个 bucket 全部成交
            while bucket:
                order = bucket.popleft()
                self.fill_order(order, order.price, is_taker=False)
            
            # Bucket 空了，移除并更新 max_buy (Lazy Update logic inside _remove is optimized, 
            # but here we manually cleared the deque. We need to trigger bound update.)
            # 手动触发极值更新逻辑：
            del self.order_book[symbol][self.SIDE_BUY][current_max_price]
            keys = self.order_book[symbol][self.SIDE_BUY].keys()
            bounds['max_buy'] = max(keys) if keys else None

        # 同价逻辑：Trade Price == Buy Price
        if bounds['max_buy'] == trade_price_int:
            bucket = self.order_book[symbol][self.SIDE_BUY][trade_price_int]
            # 必须复制 list，因为 fill_order 会修改 deque
            for order in list(bucket):
                # Case A: Capture (Buyer Taker 吃 Ask)
                if not line.is_buyer_maker:
                    self.fill_order(order, order.price, is_taker=False)
                    continue
                # Case B: Queue (Seller Taker 砸 Bid)
                if order.rank is None:
                    continue
                order.traded += line.qty
                if order.traded > order.rank:
                    self.fill_order(order, order.price, is_taker=False)

        # ------------------------------------
        # 2. 撮合卖单 (Limit Sell)
        # ------------------------------------
        # 穿价逻辑：循环吃掉所有 Sell Price < Trade Price 的单子
        while bounds['min_sell'] is not None and bounds['min_sell'] < trade_price_int:
            current_min_price = bounds['min_sell']
            bucket = self.order_book[symbol][self.SIDE_SELL][current_min_price]
            
            while bucket:
                order = bucket.popleft()
                self.fill_order(order, order.price, is_taker=False)
            
            del self.order_book[symbol][self.SIDE_SELL][current_min_price]
            keys = self.order_book[symbol][self.SIDE_SELL].keys()
            bounds['min_sell'] = min(keys) if keys else None

        # 同价逻辑
        if bounds['min_sell'] == trade_price_int:
            bucket = self.order_book[symbol][self.SIDE_SELL][trade_price_int]
            for order in list(bucket):
                # Case A: Capture (Seller Taker 吃 Bid) - 注意这里的反直觉：
                # 对 Sell Order 来说，如果 Trade 是 Buyer Maker (False)，代表 Buyer Taker 吃 Ask，这是同向排队。
                # 如果 Trade 是 Buyer Maker (True)，代表 Seller Taker 砸 Bid，这才是 Capture？
                # 不！修正逻辑：
                # Trade @ Sell Price. 
                # If is_buyer_maker=True (Seller Taker): 主动卖方砸盘 -> 捕获流动性 -> Fill My Sell Order
                if line.is_buyer_maker:
                    self.fill_order(order, order.price, is_taker=False)
                    continue
                # If is_buyer_maker=False (Buyer Taker): 主动买方吃单 -> 消耗排队 -> Rank
                if order.rank is None:
                    continue
                order.traded += line.qty
                if order.traded > order.rank:
                    self.fill_order(order, order.price, is_taker=False)

    def _process_cancel_internal(self, order: Order):
        """ 处理撤单 """
        target_id = order.cancel_target_id
        if target_id in self.order_index:
            symbol, side, price_int = self.order_index[target_id]
            bucket = self.order_book[symbol][side][price_int]
            
            # 找到目标订单并标记取消
            # 这里的查找是 O(N)，但在 bucket 内 N 通常很小
            target_order = None
            for o in bucket:
                if o.order_id == target_id:
                    target_order = o
                    break
            
            if target_order:
                # 使用derive方法创建新事件，避免修改原事件导致时间戳问题
                canceled_order = target_order.derive()
                canceled_order.state = OrderState.CANCELED
                self._remove_order_from_book(target_order)
                self.event_engine.put(canceled_order)
        
        # 使用derive方法创建新事件，避免修改原事件导致时间戳问题
        filled_cancel_order = order.derive()
        filled_cancel_order.state = OrderState.FILLED

    def _process_market_order(self, order: Order, line):
        if order.quantity > 0:
            self.fill_order(order, line.best_ask_price, is_taker=True)
        else:
            self.fill_order(order, line.best_bid_price, is_taker=True)