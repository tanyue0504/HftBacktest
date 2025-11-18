import pandas as pd

from hft_backtest import EventEngine, MatchEngine, Order, OrderState, OrderType, Data

class BinanceHftMatcher(MatchEngine):
    """
    高频交易撮合引擎实现
    支持限价单和跟踪委托的撮合逻辑
    维护订单簿和持仓信息
    推送订单状态更新事件到事件引擎
    """
    def __init__(
        self,
        event_engine: EventEngine,
        taker_fee: float = 2e-4,
        maker_fee: float = 1.1e-4,
    ):
        super().__init__(event_engine)
        self.taker_fee = taker_fee
        self.maker_fee = maker_fee
        # 订单维护：按 symbol -> {order_id: Order}
        self.order_dict: dict[str, dict[int, Order]] = {}
        # 辅助索引：order_id -> symbol
        self.order_index: dict[int, str] = {}
        # 不同order的分发渠道
        self.order_processors = {
            OrderType.LIMIT_ORDER: self.process_limit_order,
            OrderType.TRACKING_ORDER: self.process_tracking_order,
            OrderType.MARKET_ORDER: self.process_market_order,
            OrderType.CANCEL_ORDER: self.process_cancel_order
        }
        # 不同data的分发渠道
        self.data_processors = {
            "booktick": self.process_booktick_data,
            "trades": self.process_trades_data,
        }
        # booktick数据各列的dict缓存, symbol: value
        self.best_bid_price_dict = {}
        self.best_ask_price_dict = {}
        self.best_bid_qty_dict = {}
        self.best_ask_qty_dict = {}

    def on_order(self, order: Order):
        # 虽然事件引擎保证on_order推送的订单不会被重复推送给on_order
        # 但是on_data更新订单可能被on_order再次处理
        # 但on_data只会将状态更新为FILLED或CANCELED的订单推送给event_engine
        # 因此这里忽略非撤单类型且状态不为SUBMITTED的订单
        if not order.is_cancel and order.state != OrderState.SUBMITTED:
            return
        # 提交到撮合引擎的订单一定是新创建然后被提交的
        assert order.order_id not in self.order_index
        # 分发不同类型的订单到对应的处理方法
        assert order.order_type in self.order_processors
        # 收到订单后, 更新订单状态
        order.state = OrderState.RECEIVED
        self.order_processors[order.order_type](order)

    def on_data(self, data: Data):
        # 分发处理数据事件的具体实现
        assert data.name in self.data_processors
        self.data_processors[data.name](data)

    def fill_order(self, order: Order, filled_price: float, is_taker: bool):
        """
        订单被完全撮合成交
        更新订单状态为FILLED，计算成交价和手续费
        推送订单状态更新事件到事件引擎
        """
        order.state = OrderState.FILLED
        order.filled_price = filled_price
        if is_taker:
            order.commission_fee = abs(filled_price * order.quantity) * self.taker_fee
        else:
            order.commission_fee = abs(filled_price * order.quantity) * self.maker_fee
        if order.order_id in self.order_index:
            del self.order_index[order.order_id]
        if order.symbol in self.order_dict and order.order_id in self.order_dict[order.symbol]:
            del self.order_dict[order.symbol][order.order_id]
        if order.symbol in self.order_dict and not self.order_dict[order.symbol]:
            del self.order_dict[order.symbol]
        self.event_engine.put(order)

    def process_limit_order(self, order: Order):
        # 必须有盘口数据才行
        assert order.symbol in self.best_bid_price_dict and order.symbol in self.best_ask_price_dict

        if order.quantity > 0:
            # 买单撮合逻辑
            best_ask_price = self.best_ask_price_dict[order.symbol]
            best_bid_price = self.best_bid_price_dict[order.symbol]
            if order.price >= best_ask_price:
                # taker buy 成交，直接成交，无需进入维护队列
                self.fill_order(order, best_ask_price, is_taker=True)
                return
            elif order.price == best_bid_price:
                # 恰好是本方最优价，写入维护字段
                order.rank = self.best_bid_qty_dict[order.symbol]
                order.traded = 0
        elif order.quantity < 0:
            # 卖单撮合逻辑
            best_ask_price = self.best_ask_price_dict[order.symbol]
            best_bid_price = self.best_bid_price_dict[order.symbol]
            if order.price <= best_bid_price:
                # taker sell 成交
                self.fill_order(order, best_bid_price, is_taker=True)
                return
            elif order.price == best_ask_price:
                # 进入维护列表
                order.rank = self.best_ask_qty_dict[order.symbol]
                order.traded = 0
        # 进入维护：按 symbol+order_id 存储，并建立 id 索引
        symbol = order.symbol
        bucket = self.order_dict.get(symbol)
        if bucket is None:
            bucket = self.order_dict[symbol] = {}
        bucket[order.order_id] = order
        self.order_index[order.order_id] = symbol
        self.event_engine.put(order)

    def process_tracking_order(self, order: Order):
        # 跟踪委托的处理逻辑
        # 修改OrderType为LIMIT_ORDER后复用限价单逻辑
        order.order_type = OrderType.LIMIT_ORDER
        if order.quantity > 0:
            order.price = self.best_ask_price_dict[order.symbol]
        else:
            order.price = self.best_bid_price_dict[order.symbol]
        self.process_limit_order(order)
    
    def process_market_order(self, order: Order):
        if order.quantity > 0:
            self.fill_order(order, self.best_ask_price_dict[order.symbol], is_taker=True)
        elif order.quantity < 0:
            self.fill_order(order, self.best_bid_price_dict[order.symbol], is_taker=True)
    
    def process_cancel_order(self, order: Order):
        # 撤单逻辑
        cancel_id = order.cancel_target_id
        if cancel_id not in self.order_index:
            # 目标订单不存在，可能已经被成交或撤单，忽略
            return
        # 必然存在
        symbol = self.order_index[cancel_id]
        bucket = self.order_dict[symbol]
        target_order = bucket[cancel_id]
        # 无需检查订单状态，因为如果订单已经被成交或撤销就不会在order_dict里了
        # 更新目标订单状态为已撤销并推送事件然后不再维护
        target_order.state = OrderState.CANCELED
        del bucket[cancel_id]
        del self.order_index[cancel_id]
        if not bucket:
            del self.order_dict[symbol]
        self.event_engine.put(target_order)

    def process_booktick_data(self, data: Data):
        """
        数据 booktick
        字段
        symbol: 品种
        transaction_time: 订单簿变化时间戳
        best_bid_price: 最优买价
        best_ask_price: 最优卖价
        best_bid_qty: 最优买量
        best_ask_qty: 最优卖量

        注意
        订单簿还有一个字段是event_time, 表示撮合引擎事件被打包通过socket向外推送的时间
        触发booktick推送的事件有
        1. best bid ask price变动
        2. best bid ask qty变动
        3. 某个价位上的挂单被完全成交或取消
        4. 新的挂单进入best bid ask价位
        换言之, best bid ask之外订单的报撤不影响booktick
        而任何影响best bid ask price or qty的变化都会触发booktick

        订单排位维护逻辑，仅考虑挂单档位
        rank1 = rank0 - trade - front_cancel
        trade是完全知晓的，只需要估算front_cancel即可
        注意此处的逻辑适用于任意两个时间点之间

        但是下面qty的逻辑仅适用于前后两笔booktick之间，这要求上面的rank逻辑也必须在booktick之间使用
        qty1 = qty0 - trade - front_cancel - behind_cancel + new_order
        变形得到
        front_cancel = qty0 - trade - behind_cancel + new_order - qty1
        由于
        1. qty0, trade, qty1已知
        2. behind_cancel <= qty0 - rank0
        3. new_order >= 0
        注意这里暗含的假设是撤单不含新增的订单
        得到
        front_cancel >= qty0 - trade - (qty0 - rank0) + 0 - qty1
        = rank0 - trade - qty1
        因此front_cancel的保守估计是max(0, rank0 - trade - qty1)

        处理逻辑
        每次trade数据累加到订单的traded字段
        每次booktick数据来时，先创建缓存但暂不同步到self.best_xxx_dict
        然后对维护的订单进行迭代
        计算front_cancel = max(0, rank - traded - new_qty)
        注意若档位已经远离本方最优价则看不见qty, 此时必然不可能被撮合，也无法估算front_cancel, 因此跳过该订单的rank更新
        否则更新rank = rank - traded - front_cancel
        重置traded = 0
        全部订单处理完毕后更新self.best_xxx_dict缓存
        """
        assert data.name == "booktick"
        df: pd.DataFrame = data.data
        
        new_best_bid_price_dict = df['best_bid_price'].to_dict()
        new_best_ask_price_dict = df['best_ask_price'].to_dict()
        new_best_bid_qty_dict = df['best_bid_qty'].to_dict()
        new_best_ask_qty_dict = df['best_ask_qty'].to_dict()

        # 仅处理当前维护的 symbol
        updated_symbols = set(df.index) & set(self.order_dict.keys())

        # 处理涉及到的 symbol
        for symbol in updated_symbols:
            bucket = self.order_dict.get(symbol)

            new_best_bid_price = new_best_bid_price_dict[symbol]
            new_best_ask_price = new_best_ask_price_dict[symbol]
            new_best_bid_qty = new_best_bid_qty_dict[symbol]
            new_best_ask_qty = new_best_ask_qty_dict[symbol]

            for order_id, order in list(bucket.items()): # 复制bucket，避免撮合成交时修改字典报错
                if order.quantity > 0:
                    # 新ask被触碰/穿越 -> maker 成交, 因为维护队列只有限价单
                    if order.price >= new_best_ask_price:
                        self.fill_order(order, order.price, is_taker=False)
                        continue
                    # 在新best bid 档位 -> 维护 rank/traded
                    elif order.price == new_best_bid_price:
                        if order.rank is not None:
                            # front_cancel = max(0, rank - traded - new_qty)
                            front_cancel = max(0, order.rank - order.traded - new_best_bid_qty)
                            order.rank = order.rank - order.traded - front_cancel
                            order.traded = 0
                            if order.rank < 0:
                                self.fill_order(order, order.price, is_taker=False)
                                continue
                        else:
                            # 初次进入档位写入维护字段
                            order.rank = new_best_bid_qty
                            order.traded = 0
                    # 价位落在新bid-ask之间 -> 置 rank/traded 为0
                    elif new_best_bid_price < order.price < new_best_ask_price:
                        order.rank = 0
                        order.traded = 0

                # 卖单
                elif order.quantity < 0:
                    if order.price <= new_best_bid_price:
                        self.fill_order(order, order.price, is_taker=False)
                        continue
                    elif order.price == new_best_ask_price:
                        if order.rank is not None:
                            front_cancel = max(0, order.rank - order.traded - new_best_ask_qty)
                            order.rank = order.rank - order.traded - front_cancel
                            order.traded = 0
                            if order.rank < 0:
                                self.fill_order(order, order.price, is_taker=False)
                                continue
                        else:
                            order.rank = new_best_ask_qty
                            order.traded = 0
                    elif new_best_bid_price < order.price < new_best_ask_price:
                        order.rank = 0
                        order.traded = 0

        # 统一写回 best_* 缓存
        self.best_bid_price_dict.update(new_best_bid_price_dict)
        self.best_ask_price_dict.update(new_best_ask_price_dict)
        self.best_bid_qty_dict.update(new_best_bid_qty_dict)
        self.best_ask_qty_dict.update(new_best_ask_qty_dict)
    
    def process_trades_data(self, data: Data):
        """
        数据 aggTrades
        字段
        symbol: 品种
        transac_time: 成交时间戳
        price: 成交价格
        qty: 成交数量
        is_buyer_maker: 买方是否为被动方

        直接撮合逻辑
        1. 成交价越过限价单价格，立即撮合成交
        2. 存在价位与限价买单相同, 但是主动买成交, 这说明那一瞬间盘口清空了, 撮合成交
        3. 同理卖单
        4. 若未直接撮合, 则更新存在rank字段的订单的traded字段

        处理逻辑
        先将数据按symbol分组
        对订单维护队列中的symbol进行迭代，只需要处理这部分的数据
        计算buyer_taker_price_min, seller_taker_price_max, price_max, price_min直接用于cross撮合判断
        迭代每个订单
        若限价买单价格>=buyer_taker_price_min, 则直接撮合
        若限价卖单价格<=seller_taker_price_max, 则直接撮合
        若price_min<限价买单价格, 直接撮合
        若price_max>限价卖单价格, 直接撮合
        """
        assert data.name == "trades"
        df: pd.DataFrame = data.data

        if not self.order_dict:
            return
        # 仅处理当前维护的 symbol
        updated_symbols = set(df['symbol'].unique()) & set(self.order_dict.keys())
        df = df[df['symbol'].isin(updated_symbols)]

        # 价格区间统计（每 symbol）
        grp = df.groupby('symbol', sort=False)
        price_stats = grp['price'].agg(price_min='min', price_max='max')

        # 买方为taker（打ask）：is_buyer_maker == False
        buyer_taker_min = df.loc[~df['is_buyer_maker']].groupby('symbol')['price'].min()
        # 卖方为taker（打bid）：is_buyer_maker == True
        seller_taker_max = df.loc[df['is_buyer_maker']].groupby('symbol')['price'].max()

        # 每(symbol, price)累计成交量，用于更新 traded
        qty_by_symbol = df.groupby(['symbol', 'price'])['qty'].sum()

        # 遍历维护队列订单
        for symbol in updated_symbols:
            bucket = self.order_dict.get(symbol)
            pmin = price_stats.at[symbol, 'price_min']
            pmax = price_stats.at[symbol, 'price_max']
            btk_min = float(buyer_taker_min.get(symbol, float('inf')))
            stk_max = float(seller_taker_max.get(symbol, float('-inf')))

            for order_id, order in list(bucket.items()):
                # 直接撮合判断（遵循注释四条规则）
                if order.quantity > 0:
                    if (btk_min <= order.price) or (pmin < order.price):
                        self.fill_order(order, order.price, is_taker=False)
                        continue
                elif order.quantity < 0:
                    if (stk_max >= order.price) or (pmax > order.price):
                        self.fill_order(order, order.price, is_taker=False)
                        continue
                # 没有rank的跳过
                if order.rank is None:
                    continue
                # 未直接撮合：累计该(symbol, price)上的成交量
                traded = float(qty_by_symbol.get((symbol, order.price), 0.0))
                order.traded += traded

                # 若有 rank，检查是否可按maker撮合完成
                if order.traded > order.rank:
                    self.fill_order(order, order.price, is_taker=False)