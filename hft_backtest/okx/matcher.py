from collections import deque, defaultdict, OrderedDict
from itertools import chain
import math
import operator
from hft_backtest import MatchEngine, Order, EventEngine
from .event import OKXBookticker, OKXTrades, OKXDelivery

class OKXMatcher(MatchEngine):
    
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
        # pending_order_dict: 刚刚收到但还没撮合的订单 (OrderState.RECEIVED)
        self.pending_order_dict = defaultdict(deque)
        
        # order_book: 撮合引擎的核心账本
        # Symbol -> Side -> Price(Int) -> OrderedDict[order_id, Order]
        self.order_book = defaultdict(lambda: {
            self.SIDE_BUY: defaultdict(OrderedDict),
            self.SIDE_SELL: defaultdict(OrderedDict)
        })
        
        # order_index: 快速查找订单位置
        # order_id -> (symbol, side, price_int)
        self.order_index = {}
        
        # 极值缓存: symbol -> max_buy / min_sell (Int)
        self.max_buy_int = {}
        self.min_sell_int = {}

        # BBO 缓存: symbol -> bid/ask price (Int)
        self.bid_price_int = {}
        self.ask_price_int = {}

        # --- 预编译数据提取器 (保持原有性能优化) ---
        DEPTH_LEVELS = 25 
        
        bid_price_cols = [f"bid_price_{i}" for i in range(1, DEPTH_LEVELS + 1)]
        bid_qty_cols   = [f"bid_amount_{i}"   for i in range(1, DEPTH_LEVELS + 1)]
        
        ask_price_cols = [f"ask_price_{i}" for i in range(1, DEPTH_LEVELS + 1)]
        ask_qty_cols   = [f"ask_amount_{i}"   for i in range(1, DEPTH_LEVELS + 1)]

        self.get_bid_prices = operator.attrgetter(*bid_price_cols)
        self.get_bid_qtys   = operator.attrgetter(*bid_qty_cols)
        self.get_ask_prices = operator.attrgetter(*ask_price_cols)
        self.get_ask_qtys   = operator.attrgetter(*ask_qty_cols)

    def start(self, engine: EventEngine):
        self.event_engine = engine
        # 1. 监听策略发来的订单
        engine.register(Order, self.on_order)
        
        # 2. 监听具体的市场数据事件
        engine.register(OKXBookticker, self.on_bookticker)
        engine.register(OKXTrades, self.on_trade)
        engine.register(OKXDelivery, self.on_delivery)

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
            # 极值更新
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

    def _cancel_order(self, order_id: int):
        # 1. 先尝试从活跃账本中撤单
        if order_id in self.order_index:
            symbol, side, price_int = self.order_index[order_id]
            order = self.order_book[symbol][side][price_int][order_id]
            
            new_order = order.derive()
            new_order.state = OrderState.CANCELED
            
            self._remove_order_from_book(order)
            self.event_engine.put(new_order)
            return

        # 2. [新增] 如果不在账本中，尝试从 Pending 队列中查找并移除
        # 这也是 O(N) 的操作，但 Pending 队列通常很短
        # 由于我们不知道 symbol，只能遍历所有 symbol 的 queue (或者让 CancelOrder 携带 symbol)
        # 假设 Order 对象如果能获取到 symbol 最好，但 cancel_order 工厂方法生成时 symbol=None。
        # 这是一个架构权衡，这里我们不得不暴力搜索 pending 字典。
        for symbol, queue in self.pending_order_dict.items():
            for i, order in enumerate(queue):
                if order.order_id == order_id:
                    # 找到了，移除
                    del queue[i]
                    
                    # 推送撤单成功事件
                    new_order = order.derive()
                    new_order.state = OrderState.CANCELED
                    self.event_engine.put(new_order)
                    return

        # 3. 既不在账本也不在 Pending，说明已成交或已撤销，忽略

    def _process_cancel_internal(self, order: Order):
        """处理 Pending 队列中的撤单指令"""
        self._cancel_order(order.cancel_target_id)

    # ==========================
    # Core Event Handlers
    # ==========================

    def on_order(self, order: Order):
        # 只处理 SUBMITTED 状态的订单或撤单指令
        if not (order.state == OrderState.SUBMITTED or order.is_cancel):
            return
        
        # 撤单指令立即处理
        if order.is_cancel:
            self._process_cancel_internal(order)
            return
        
        # 确保订单没有被重复处理
        assert order.order_id not in self.order_index
        
        new_order = order.derive()
        new_order.state = OrderState.RECEIVED
        
        # 放入待处理队列，等待下一个行情事件触发撮合
        self.pending_order_dict[order.symbol].append(new_order)
        self.event_engine.put(new_order)

    def on_delivery(self, event: OKXDelivery):
        """
        处理交割/强平事件
        当收到交割事件时，意味着该合约已停止交易。
        撮合引擎应清除该品种的所有订单，并通知 Account/Strategy。
        """
        symbol = event.symbol
        
        # 1. 清空 Pending 队列
        if symbol in self.pending_order_dict:
            # 可以选择推送 CANCELED 事件，或者直接丢弃
            # 这里简单清空，因为 Account 此时也收到了 Delivery 事件并清仓了
            self.pending_order_dict[symbol].clear()
            
        # 2. 清空 Order Book
        if symbol in self.order_book:
            
            # 彻底重置该 symbol 的数据结构
            del self.order_book[symbol]
            self.max_buy_int.pop(symbol, None)
            self.min_sell_int.pop(symbol, None)
            
            # 清理索引 (稍显低效，但交割很少发生)
            self.order_index = {oid: tup for oid, tup in self.order_index.items() if tup[0] != symbol}

    # ==========================
    # Data Processing Logic
    # ==========================

    def on_bookticker(self, event: OKXBookticker):
        symbol = event.symbol
        
        # --- 1. 解析数据 ---
        # 使用预编译的 attrgetter 批量提取
        raw_bid_prices = self.get_bid_prices(event)
        raw_bid_qtys   = self.get_bid_qtys(event)
        raw_ask_prices = self.get_ask_prices(event)
        raw_ask_qtys   = self.get_ask_qtys(event)
        
        current_bids_map = {
            self.to_int_price(p): q 
            for p, q in zip(raw_bid_prices, raw_bid_qtys)
        }
        current_asks_map = {
            self.to_int_price(p): q 
            for p, q in zip(raw_ask_prices, raw_ask_qtys)
        }

        # 这里的字段名取决于 dataset 中 rename 后的名字
        # 假设是 bid_price_1 等 (C结构体风格)
        best_bid_int = self.to_int_price(raw_bid_prices[0])
        best_ask_int = self.to_int_price(raw_ask_prices[0])
        worst_bid_int = self.to_int_price(raw_bid_prices[-1])
        worst_ask_int = self.to_int_price(raw_ask_prices[-1])

        # 更新缓存的 BBO 价格
        self.bid_price_int[symbol] = best_bid_int
        self.ask_price_int[symbol] = best_ask_int

        # --- 2. 维护阶段 (Maintenance Phase) ---
        # 遍历存量订单，处理穿价和更新 Rank
        
        # ... Buy Orders ...
        buy_book = self.order_book[symbol][self.SIDE_BUY]
        for price_int in sorted(buy_book.keys(), reverse=True):
            if self.max_buy_int.get(symbol, -math.inf) < worst_bid_int:
                break
            
            # 逻辑：Ask 砸穿 Limit Buy -> 成交
            if best_ask_int <= price_int:
                for order in list(buy_book[price_int].values()):
                    self._fill_order(order, order.price, is_taker=False)
            # 价格在 Spread 中间 -> 排位归零
            elif best_bid_int < price_int < best_ask_int:
                for order in list(buy_book[price_int].values()):
                    order.rank = 0
                    order.traded = 0
            # 价格在 Bids 队列中 -> 更新 Rank
            elif worst_bid_int <= price_int <= best_bid_int:
                qty = current_bids_map.get(price_int, 0)
                for order in list(buy_book[price_int].values()):
                    if order.rank is None:
                        order.rank = qty
                        order.traded = 0
                    else:
                        front_cancel = max(0, order.rank - order.traded - qty)
                        order.rank = order.rank - order.traded - front_cancel
                        order.traded = 0
                        if order.rank < 0:
                            self._fill_order(order, order.price, is_taker=False)

        # ... Sell Orders ...
        sell_book = self.order_book[symbol][self.SIDE_SELL]
        for price_int in sorted(sell_book.keys()):
            if self.min_sell_int.get(symbol, math.inf) > worst_ask_int:
                break
            
            # 逻辑：Bid 吃掉 Limit Sell -> 成交
            if price_int <= best_bid_int:
                for order in list(sell_book[price_int].values()):
                    self._fill_order(order, order.price, is_taker=False)
            elif best_bid_int < price_int < best_ask_int:
                for order in list(sell_book[price_int].values()):
                    order.rank = 0
                    order.traded = 0
            elif best_ask_int <= price_int <= worst_ask_int:
                qty = current_asks_map.get(price_int, 0)
                for order in list(sell_book[price_int].values()):
                    if order.rank is None:
                        order.rank = qty
                        order.traded = 0
                    else:
                        front_cancel = max(0, order.rank - order.traded - qty)
                        order.rank = order.rank - order.traded - front_cancel
                        order.traded = 0
                        if order.rank < 0:
                            self._fill_order(order, order.price, is_taker=False)

        # --- 3. 入场阶段 (Entry Phase) ---
        pending_queue = self.pending_order_dict[symbol]
        while pending_queue:
            order = pending_queue.popleft()

            if order.order_type == OrderType.MARKET_ORDER:
                if order.quantity > 0:
                    self._fill_order(order, event.ask_price_1, is_taker=True)
                else:
                    self._fill_order(order, event.bid_price_1, is_taker=True)
                continue

            if order.order_type == OrderType.TRACKING_ORDER:
                order = order.derive()
                order.order_type = OrderType.LIMIT_ORDER
                if order.quantity > 0:
                    order.price = event.bid_price_1
                else:
                    order.price = event.ask_price_1

            # Limit Order Logic
            price_int = order.price_int
            
            # Check Taker
            if order.quantity > 0:
                if price_int >= best_ask_int:
                    self._fill_order(order, event.ask_price_1, is_taker=True)
                    continue
            else:
                if price_int <= best_bid_int:
                    self._fill_order(order, event.bid_price_1, is_taker=True)
                    continue
            
            # Maker (Add to Book)
            self._add_order_to_book(order)
            
            # Init Rank
            if order.quantity > 0:
                if price_int >= worst_bid_int:
                    order.rank = current_bids_map.get(price_int, 0)
                    order.traded = 0
                elif best_bid_int < price_int < best_ask_int:
                    order.rank = 0
                    order.traded = 0
                else:
                    order.rank = None; order.traded = None
            else:
                if price_int <= worst_ask_int:
                    order.rank = current_asks_map.get(price_int, 0)
                    order.traded = 0
                elif best_bid_int < price_int < best_ask_int:
                    order.rank = 0
                    order.traded = 0
                else:
                    order.rank = None; order.traded = None
            
            self.event_engine.put(order.derive())

    def on_trade(self, event: OKXTrades):
        """
        基于成交数据 (Trades) 的撮合
        处理 'side' 字段映射：
        OKX Data: side='buy' (Aggressor Buy) -> is_buyer_maker=False
        OKX Data: side='sell' (Aggressor Sell) -> is_buyer_maker=True
        """
        symbol = event.symbol
        trade_price = event.price
        trade_price_int = self.to_int_price(trade_price)
        
        # 字段适配
        is_buyer_maker = (event.side == 'sell') 
        
        # === Step 1: 更新 BBO 推断 ===
        if is_buyer_maker: # Seller Taker (砸盘) -> 此价格大概率为 Bid
            self.bid_price_int[symbol] = trade_price_int
            if self.ask_price_int.get(symbol, math.inf) < trade_price_int:
                self.ask_price_int[symbol] = trade_price_int
        else: # Buyer Taker (拉盘) -> 此价格大概率为 Ask
            self.ask_price_int[symbol] = trade_price_int
            if self.bid_price_int.get(symbol, -math.inf) > trade_price_int:
                self.bid_price_int[symbol] = trade_price_int
        
        # === Step 2: 撮合存量订单 ===
        # --- Buy Orders ---
        max_buy_int = self.max_buy_int.get(symbol, -math.inf)
        while max_buy_int > trade_price_int:
            bucket = self.order_book[symbol][self.SIDE_BUY][max_buy_int]
            for order in list(bucket.values()):
                self._fill_order(order, order.price, is_taker=False)
            max_buy_int = self.max_buy_int.get(symbol, -math.inf)

        if max_buy_int == trade_price_int:
            bucket = self.order_book[symbol][self.SIDE_BUY][trade_price_int]
            # Buyer Taker (拉盘), 此时成交价是 Ask，Limit Buy 应该安然无恙
            if not is_buyer_maker:
                for order in list(bucket.values()):
                    self._fill_order(order, order.price, is_taker=False)
            # Seller Taker (砸盘), 消耗 Bid 队列
            else:
                for order in list(bucket.values()):
                    if order.rank is None: continue
                    order.traded += event.size # OKX use 'size' or 'qty'? event.py definition says 'size'
                    if order.traded > order.rank:
                        self._fill_order(order, order.price, is_taker=False)

        # --- Sell Orders ---
        min_sell_int = self.min_sell_int.get(symbol, math.inf)
        while trade_price_int > min_sell_int:
            bucket = self.order_book[symbol][self.SIDE_SELL][min_sell_int]
            for order in list(bucket.values()):
                self._fill_order(order, order.price, is_taker=False)
            min_sell_int = self.min_sell_int.get(symbol, math.inf)

        if min_sell_int == trade_price_int:
            bucket = self.order_book[symbol][self.SIDE_SELL][trade_price_int]
            if is_buyer_maker: # Seller Taker, 此时成交价是 Bid
                for order in list(bucket.values()):
                    self._fill_order(order, order.price, is_taker=False)
            else: # Buyer Taker, 消耗 Ask 队列
                for order in list(bucket.values()):
                    if order.rank is None: continue
                    order.traded += event.size
                    if order.traded > order.rank:
                        self._fill_order(order, order.price, is_taker=False)

        # === Step 3: Flush Pending Queue ===
        # 这里逻辑与 on_bookticker 类似，但只能使用推断出的 BBO
        # 为简化逻辑，我们在 Trade 事件中仅处理 Limit Order 穿价和 Market Order
        # 但通常 Pending Queue 最好等到 BookTicker 再细致处理，
        # 不过为了防止延迟过大，这里做简单的 Taker 撮合是合理的。
        
        pending_queue = self.pending_order_dict[symbol]
        if not pending_queue:
            return

        # 如果没有 BBO 缓存，我们无法准确处理 Pending，只能跳过
        if symbol not in self.bid_price_int or symbol not in self.ask_price_int:
            return

        bid_price_int = self.bid_price_int[symbol]
        ask_price_int = self.ask_price_int[symbol]
        
        # 还原回 float 价格供 _fill_order 使用
        bid_price_float = bid_price_int / self.PRICE_SCALAR
        ask_price_float = ask_price_int / self.PRICE_SCALAR

        while pending_queue:
            order = pending_queue.popleft()
            # order = pending_queue[0]
            
            # 只处理那些能立即成交的 (Taker)
            # 复杂的排队逻辑留给 BookTicker
            if order.order_type == OrderType.MARKET_ORDER:
                if order.quantity > 0:
                    self._fill_order(order, ask_price_float, is_taker=True)
                else:
                    self._fill_order(order, bid_price_float, is_taker=True)
                continue
            
            # --- 3. Tracking -> Limit ---
            if order.order_type == OrderType.TRACKING_ORDER:
                order = order.derive()
                order.order_type = OrderType.LIMIT_ORDER
                if order.quantity > 0:
                    order.price = bid_price_int / self.PRICE_SCALAR
                else:
                    order.price = ask_price_int / self.PRICE_SCALAR

            # --- 4. Limit Order ---
            price_int = order.price_int
            
            # 4.1 Check Taker (Immediate Fill)
            if order.quantity > 0:
                if price_int >= ask_price_int:
                    self._fill_order(order, ask_price_int / self.PRICE_SCALAR, is_taker=True)
                    continue
            else:
                if price_int <= bid_price_int:
                    self._fill_order(order, bid_price_int / self.PRICE_SCALAR, is_taker=True)
                    continue
            
            # 4.2 Maker (Add to Book)
            self._add_order_to_book(order)
            
            # 推送 Order Entered 事件
            # self.event_engine.put(order.derive())