from collections import deque, defaultdict, OrderedDict
import math
from operator import is_
from hft_backtest import MatchEngine, Order, OrderState, OrderType, Data

class BinanceMatcher(MatchEngine):

    PRICE_SCALAR = Order.SCALER 
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
        self.pending_order_dict = defaultdict(deque)
        
        # Symbol -> Side -> Price(Int) -> OrderedDict[order_id, Order]
        self.order_book = defaultdict(lambda: {
            self.SIDE_BUY: defaultdict(OrderedDict),
            self.SIDE_SELL: defaultdict(OrderedDict)
        })
        # 辅助索引: order_id -> (symbol, side, price_int)
        self.order_index = {}
        
        # 极值缓存: symbol -> max or min price int
        self.max_buy_int = {}
        self.min_sell_int = {}

        # 缓存最新bid ask price, 用于on_trade处理
        self.bid_price_int = {}
        self.ask_price_int = {}

        self.data_processors = {
            "bookTicker": self.process_bookTicker_data,
            "trades": self.process_trades_data,
        }

    # ==========================
    # Helper Methods
    # ==========================

    def to_int_price(self, price: float) -> int:
        return int(round(price * self.PRICE_SCALAR))

    def _add_order_to_book(self, order: Order):
        symbol = order.symbol
        side = self.SIDE_BUY if order.quantity > 0 else self.SIDE_SELL
        price_int = order.price_int
        book = self.order_book[symbol][side]
        
        # 1. 入库
        book[price_int][order.order_id] = order
        self.order_index[order.order_id] = (symbol, side, price_int)
        
        # 2. 极值更新
        if side == self.SIDE_BUY:
            if price_int > self.max_buy_int.get(symbol, -math.inf):
                self.max_buy_int[symbol] = price_int
        else:
            if price_int < self.min_sell_int.get(symbol, math.inf):
                self.min_sell_int[symbol] = price_int

    def _remove_order_from_book(self, order: Order):
        if order.order_id not in self.order_index:
            return

        symbol, side, price_int = self.order_index[order.order_id]
        bucket = self.order_book[symbol][side][price_int]
        
        if order.order_id in bucket:
            del bucket[order.order_id]
        
        del self.order_index[order.order_id]
        
        # Lazy Update: 如果 bucket 空了，删除 key
        if not bucket:
            del self.order_book[symbol][side][price_int]
            # 极值更新, 重新计算
            keys = self.order_book[symbol][side].keys()
            if keys:
                if side == self.SIDE_BUY:
                    self.max_buy_int[symbol] = max(keys)
                else:
                    self.min_sell_int[symbol] = min(keys)
            else:
                if side == self.SIDE_BUY:
                    self.max_buy_int[symbol] = -math.inf
                else:
                    self.min_sell_int[symbol] = math.inf

    def _fill_order(self, order: Order, filled_price: float, is_taker: bool):
        new_order = order.derive()
        new_order.state = OrderState.FILLED
        new_order.filled_price = filled_price
        
        raw_fee = abs(filled_price * new_order.quantity)
        new_order.commission_fee = raw_fee * self.taker_fee if is_taker else raw_fee * self.maker_fee
        
        self._remove_order_from_book(order)
        self.event_engine.put(new_order)

    def _cancel_order(self, order_id:int):
        if order_id not in self.order_index:
            return
        symbol, side, price_int = self.order_index[order_id]
        order = self.order_book[symbol][side][price_int][order_id]
        new_order = order.derive()
        new_order.state = OrderState.CANCELED
        self._remove_order_from_book(order)
        self.event_engine.put(new_order)

    # ==========================
    # Core Event Handlers
    # ==========================

    def on_order(self, order: Order):
        # 过滤on data里面推送出去的其他订单状态，只处理 SUBMITTED 状态的订单或撤单
        if not (order.state == OrderState.SUBMITTED or order.is_cancel):
            return
        assert order.order_id not in self.order_index
        new_order = order.derive()
        new_order.state = OrderState.RECEIVED
        self.pending_order_dict[order.symbol].append(new_order)
        self.event_engine.put(new_order)

    def on_data(self, data: Data):
        if data.name not in self.data_processors:
            return
        self.data_processors[data.name](data)

    # ==========================
    # Data Processing Logic
    # ==========================

    def process_bookTicker_data(self, data: Data):
        line = data.data
        symbol = line.symbol
        
        bid_int = self.to_int_price(line.best_bid_price)
        ask_int = self.to_int_price(line.best_ask_price)

        # 更新缓存的 BBO 价格
        self.bid_price_int[symbol] = bid_int
        self.ask_price_int[symbol] = ask_int

        # 2. 维护阶段 (Maintenance Phase)
        # 遍历存量订单，处理穿价和更新 Rank
        
        # --- Buy Orders ---
        buy_book = self.order_book[symbol][self.SIDE_BUY]
        for price_int in list(buy_book.keys()):
            # 当max buy price < best bid price, 就可以结束了
            if self.max_buy_int.get(symbol, -math.inf) < bid_int:
                break
            # ask 打穿 limit buy order -> 成交
            if ask_int < price_int:
                for order in list(buy_book[price_int].values()):
                    self._fill_order(order, order.price, is_taker=False)
            # 价格在 bid ask 之间(不含), 排第一
            elif bid_int < price_int < ask_int:
                for order in list(buy_book[price_int].values()):
                    order.rank = 0
                    order.traded = 0
            # 价格刚好等于 bid, 更新排位
            elif price_int == bid_int:
                for order in list(buy_book[price_int].values()):
                    if order.rank is None:
                        # 刚挂到 best bid，初始化 rank
                        order.rank = line.best_bid_qty
                        order.traded = 0
                    else:
                        front_cancel = max(0, order.rank - order.traded - line.best_bid_qty)
                        order.rank = order.rank - order.traded - front_cancel
                        order.traded = 0
                        if order.rank < 0:
                            self._fill_order(order, order.price, is_taker=False)

        # --- Sell Orders ---
        sell_book = self.order_book[symbol][self.SIDE_SELL]
        for price_int in list(sell_book.keys()):
            if self.min_sell_int.get(symbol, math.inf) > ask_int:
                break
            # bid 打穿 limit sell order -> 成交
            if bid_int > price_int:
                for order in list(sell_book[price_int].values()):
                    self._fill_order(order, order.price, is_taker=False)
            # 价格在 bid ask 之间(不含), 排第一
            elif bid_int < price_int < ask_int:
                for order in list(sell_book[price_int].values()):
                    order.rank = 0
                    order.traded = 0
            # 价格刚好等于 ask, 更新排位
            elif price_int == ask_int:
                for order in list(sell_book[price_int].values()):
                    if order.rank is None:
                        order.rank = line.best_ask_qty
                        order.traded = 0
                    else:
                        front_cancel = max(0, order.rank - order.traded - line.best_ask_qty)
                        order.rank = order.rank - order.traded - front_cancel
                        order.traded = 0
                        if order.rank < 0:
                            self._fill_order(order, order.price, is_taker=False)

        # 3. 入场阶段 (Entry Phase)
        # BookTicker 时也是处理 Pending 的好时机，直接用最新的 Book 价格
        pending_queue = self.pending_order_dict[symbol]
        while pending_queue:
            order = pending_queue.popleft()
            
            # --- 1. 撤单 ---
            if order.order_type == OrderType.CANCEL_ORDER:
                self._process_cancel_internal(order)
                continue

            # --- 2. Market Order (Assumption: Infinite Liquidity) ---
            if order.order_type == OrderType.MARKET_ORDER:
                if order.quantity > 0:
                    self._fill_order(order, line.best_ask_price, is_taker=True)
                else:
                    self._fill_order(order, line.best_bid_price, is_taker=True)
                continue

            # --- 3. Tracking -> Limit ---
            if order.order_type == OrderType.TRACKING_ORDER:
                order = order.derive()
                order.order_type = OrderType.LIMIT_ORDER
                if order.quantity > 0:
                    order.price = line.best_bid_price
                else:
                    order.price = line.best_ask_price

            # --- 4. Limit Order ---
            price_int = order.price_int
            
            # 4.1 Check Taker (Immediate Fill)
            if order.quantity > 0:
                if price_int >= ask_int:
                    self._fill_order(order, line.best_ask_price, is_taker=True)
                    continue
            else:
                if price_int <= bid_int:
                    self._fill_order(order, line.best_bid_price, is_taker=True)
                    continue
            
            # 4.2 Maker (Add to Book)
            self._add_order_to_book(order)
            
            # 初始化 Rank
            if order.quantity > 0:
                if price_int == bid_int:
                    order.rank = line.best_bid_qty
                    order.traded = 0
                elif bid_int < price_int < ask_int:
                    order.rank = 0
                    order.traded = 0
                else:
                    order.rank = None
                    order.traded = None
            else:
                if price_int == ask_int:
                    order.rank = line.best_ask_qty
                    order.traded = 0
                elif bid_int < price_int < ask_int:
                    order.rank = 0
                    order.traded = 0
                else:
                    order.rank = None
                    order.traded = None
            
            # 推送 Order Entered 事件
            self.event_engine.put(order.derive())

    def process_trades_data(self, data: Data):
        """ 
        改进后的逻辑：
        1. 推断当前 BBO (基于 Trade 价格)
        2. Flush Pending Queue (用推断 BBO 成交市价单/Taker单)
        3. Match Existing Orders (用 Trade 扫书)
        """
        line = data.data
        symbol = line.symbol
        trade_price = line.price
        trade_price_int = self.to_int_price(trade_price)
        
        # === Step 1: 更新 BBO 推断===
        if line.is_buyer_maker: # Seller Taker (砸盘)
            self.bid_price_int[symbol] = trade_price_int
            if self.ask_price_int[symbol] < trade_price_int:
                self.ask_price_int[symbol] = trade_price_int
        else: # Buyer Taker (拉盘)
            self.ask_price_int[symbol] = trade_price_int
            if self.bid_price_int[symbol] > trade_price_int:
                self.bid_price_int[symbol] = trade_price_int
        
        # === Step: 2 先处理book队列防止重复处理pending===
        max_buy_int = self.max_buy_int.get(symbol, -math.inf)
        # --- 撮合 Buy Limit ---
        # 只要买价 > trade price 就一直处理直到全部撮合完
        while max_buy_int > trade_price_int:
            bucket = self.order_book[symbol][self.SIDE_BUY][max_buy_int]
            for order in list(bucket.values()):
                self._fill_order(order, order.price, is_taker=False)
            max_buy_int = self.max_buy_int.get(symbol, -math.inf)

        # 同价逻辑
        if max_buy_int == trade_price_int:
            bucket = self.order_book[symbol][self.SIDE_BUY][trade_price_int]
            # Buyer Taker (吃 Ask), 表明这一瞬间的trade_price是ask price, 要撮合所有 Buy Limit
            if not line.is_buyer_maker:
                for order in list(bucket.values()):
                    self._fill_order(order, order.price, is_taker=False)
            # Seller Taker (砸 Bid), 累计成交量
            else:
                for order in list(bucket.values()):
                    if order.rank is None:
                        continue
                    order.traded += line.qty
                    if order.traded > order.rank:
                        self._fill_order(order, order.price, is_taker=False)

        # --- 撮合 Sell Limit ---
        min_sell_int = self.min_sell_int.get(symbol, math.inf)
        while trade_price_int > min_sell_int:
            bucket = self.order_book[symbol][self.SIDE_SELL][min_sell_int]
            for order in list(bucket.values()):
                self._fill_order(order, order.price, is_taker=False)
            min_sell_int = self.min_sell_int.get(symbol, math.inf)

        # 同价逻辑
        if min_sell_int == trade_price_int:
            bucket = self.order_book[symbol][self.SIDE_SELL][trade_price_int]
            if line.is_buyer_maker:
                for order in list(bucket.values()):
                    self._fill_order(order, order.price, is_taker=False)
            else:
                for order in list(bucket.values()):
                    # Buyer Taker (吃 Ask) -> 正常排队
                    if order.rank is None:
                        continue
                    order.traded += line.qty
                    if order.traded > order.rank:
                        self._fill_order(order, order.price, is_taker=False)

        # === Step 3: Flush Pending Queue ===
        pending_queue = self.pending_order_dict[symbol]
        while pending_queue:
            order = pending_queue.popleft()
            bid_price = self.bid_price_int[symbol]
            ask_price = self.ask_price_int[symbol]
            
            # --- 1. 撤单 ---
            if order.order_type == OrderType.CANCEL_ORDER:
                self._cancel_order(order.cancel_target_id)
                continue

            # --- 2. Market Order (Assumption: Infinite Liquidity) ---
            if order.order_type == OrderType.MARKET_ORDER:
                if order.quantity > 0:
                    self._fill_order(order, ask_price / self.PRICE_SCALAR, is_taker=True)
                else:
                    self._fill_order(order, bid_price / self.PRICE_SCALAR, is_taker=True)
                continue

            # --- 3. Tracking -> Limit ---
            if order.order_type == OrderType.TRACKING_ORDER:
                order = order.derive()
                order.order_type = OrderType.LIMIT_ORDER
                if order.quantity > 0:
                    order.price = bid_price / self.PRICE_SCALAR
                else:
                    order.price = ask_price / self.PRICE_SCALAR

            # --- 4. Limit Order ---
            price_int = order.price_int
            
            # 4.1 Check Taker (Immediate Fill)
            if order.quantity > 0:
                if price_int >= ask_price:
                    self._fill_order(order, ask_price / self.PRICE_SCALAR, is_taker=True)
                    continue
            else:
                if price_int <= bid_price:
                    self._fill_order(order, bid_price / self.PRICE_SCALAR, is_taker=True)
                    continue
            
            # 4.2 Maker (Add to Book)
            self._add_order_to_book(order)
            
            # 推送 Order Entered 事件
            self.event_engine.put(order.derive())