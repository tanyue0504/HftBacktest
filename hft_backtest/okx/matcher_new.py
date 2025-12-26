from collections import deque, defaultdict, OrderedDict
from itertools import chain
import math
import operator
from hft_backtest import MatchEngine, Order, EventEngine
from .event import OKXBookticker, OKXTrades, OKXDelivery

class OKXMatcherNew(MatchEngine):
    
    PRICE_SCALAR = Order.SCALER
    INIT_RANK = 10**9

    def __init__(
        self,
        symbol:str,
        taker_fee: float = 2e-4,
        maker_fee: float = 1.1e-4,
    ):
        self.symbol = symbol
        self.taker_fee = taker_fee
        self.maker_fee = maker_fee

        self.best_bid_price_int = 0
        self.best_ask_price_int = math.inf

        self.buy_book = []
        self.sell_book = []

        depth_level = 5
        ask_price_cols = [f"ask_price_{i}" for i in range(1, depth_level + 1)]
        ask_qty_cols   = [f"ask_amount_{i}"   for i in range(1, depth_level + 1)]
        bid_price_cols = [f"bid_price_{i}" for i in range(1, depth_level + 1)]
        bid_qty_cols   = [f"bid_amount_{i}"   for i in range(1, depth_level + 1)]

        self.get_ask_prices = operator.attrgetter(*ask_price_cols)
        self.get_ask_qtys   = operator.attrgetter(*ask_qty_cols)
        self.get_bid_prices = operator.attrgetter(*bid_price_cols)
        self.get_bid_qtys   = operator.attrgetter(*bid_qty_cols)

    def start(self, engine: EventEngine):
        self.event_engine = engine
        engine.register(Order, self.on_order)
        engine.register(OKXBookticker, self.on_bookticker)
        engine.register(OKXTrades, self.on_trade)
        engine.register(OKXDelivery, self.on_delivery)

    def to_int_price(self, price: float) -> int:
        return int(round(price * self.PRICE_SCALAR))

    def _add_order(self, order: Order):
        if order.quantity > 0:
            self.buy_book.append(order)
        else:
            self.sell_book.append(order)

    def _remove_order(self, order: Order) -> bool:
        if order.quantity > 0:
            for o in self.buy_book:
                if o.order_id == order.order_id:
                    self.buy_book.remove(o)
                    return True
        else:
            for o in self.sell_book:
                if o.order_id == order.order_id:
                    self.sell_book.remove(o)
                    return True
        return False

    def fill_order(self, order: Order, filled_price: float, is_taker: bool):
        # 务必衍生，否则可能导致account错乱
        new_order = order.derive()
        # 更新状态为已成交
        new_order.state = Order.ORDER_STATE_FILLED
        # 填写成交价格和计算手续费
        new_order.filled_price = filled_price
        amount = abs(filled_price * new_order.quantity)
        new_order.commission_fee = amount * self.taker_fee if is_taker else amount * self.maker_fee
        # 从账本中移除订单并推送订单成交事件
        self._remove_order(order)
        self.event_engine.put(new_order)

    def cancel_order(self, order: Order):
        # 务必衍生，否则可能导致account错乱
        new_order = order.derive()
        # 更新状态为已撤单
        if self._remove_order(order):
            new_order.state = Order.ORDER_STATE_CANCELED
        else:
            new_order.state = Order.ORDER_STATE_REJECTED
        self.event_engine.put(new_order)

    def on_order(self, order: Order):
        # 只处理本品种的订单
        if order.symbol != self.symbol:
            return
        # 只处理 SUBMITTED 状态的订单或撤单指令
        if not (order.is_submitted or order.is_cancel_order):
            return
        
        # 撤单指令立即处理
        if order.is_cancel_order:
            self.cancel_order(order)
            return
        
        # 衍生事件并推送回报
        new_order = order.derive()
        new_order.state = Order.ORDER_STATE_RECEIVED
        self.event_engine.put(new_order)
        
        # 检查是否立即成交
        # 1. 确定买卖方向和对应的对手盘价格 (买单撞Ask, 卖单撞Bid)
        is_buy = order.quantity > 0
        match_price_int = self.best_ask_price_int if is_buy else self.best_bid_price_int
        
        # 2. 判断是否满足立即成交条件
        should_fill = False
        if order.is_market_order:
            should_fill = True  # 市价单假设一定能成交 (需确保盘口有量)
        elif order.is_limit_order:
            # 买单 >= 卖一价，或 卖单 <= 买一价
            should_fill = (order.price_int >= match_price_int) if is_buy else (order.price_int <= match_price_int)

        # 3. 统一执行成交
        if should_fill:
            self.fill_order(order, match_price_int / self.PRICE_SCALAR, is_taker=True)
            return
        
        # 4. 否则，加入待处理队列
        order.rank = self.INIT_RANK
        self._add_order(order)

    def on_delivery(self, event: OKXDelivery):
        """
        处理交割/强平事件
        当收到交割事件时，意味着该合约已停止交易。
        撮合引擎应清除该品种的所有订单
        """
        # 非本品种不处理
        if event.symbol != self.symbol:
            return
        # 调用终止逻辑
        self.stop()

    def on_bookticker(self, event: OKXBookticker):
        # 只处理本品种的盘口更新
        if event.symbol != self.symbol:
            return
        # 更新最佳买卖价
        self.best_bid_price_int = self.to_int_price(event.best_bid_price)
        self.best_ask_price_int = self.to_int_price(event.best_ask_price)
        # 生成price -> quantity映射
        ask_prices = self.get_ask_prices(event)
        ask_qtys = self.get_ask_qtys(event)
        bid_prices = self.get_bid_prices(event)
        bid_qtys = self.get_bid_qtys(event)
        asks = {self.to_int_price(p): q for p, q in zip(ask_prices, ask_qtys)}
        bids = {self.to_int_price(p): q for p, q in zip(bid_prices, bid_qtys)}
        # 检查订单是否穿价成交、更新排位
        for order in list(self.buy_book):
            order:Order
            if order.price_int >= self.best_ask_price_int:
                self.fill_order(order, self.best_ask_price_int / self.PRICE_SCALAR, is_taker=False)
                continue
            qty = bids.get(order.price_int, math.inf)
            front_cancel = max(0, order.rank - order.traded - qty)
            order.rank = order.rank - order.traded - front_cancel
            order.traded = 0
            if order.rank <= -order.quantity:
                self.fill_order(order, order.price, is_taker=False)
        for order in list(self.sell_book):
            order:Order
            if order.price_int <= self.best_bid_price_int:
                self.fill_order(order, self.best_bid_price_int / self.PRICE_SCALAR, is_taker=False)
                continue
            qty = asks.get(order.price_int, math.inf)
            front_cancel = max(0, order.rank - order.traded - qty)
            order.rank = order.rank - order.traded - front_cancel
            order.traded = 0
            if order.rank <= -order.quantity:
                self.fill_order(order, order.price, is_taker=False)

    def on_trade(self, event: OKXTrades):
        # 只处理本品种的成交更新
        if event.symbol != self.symbol:
            return
        # 更新一侧bbo
        if event.side == 'buy':
            self.best_ask_price_int = self.to_int_price(event.price)
            for order in list(self.sell_book):
                order:Order
                if order.price_int < self.best_ask_price_int:
                    self.fill_order(order, order.price, is_taker=False)
                if order.price_int == event.price_int:
                    order.traded += event.size
                if (order.rank - order.traded) <= -order.quantity:
                    self.fill_order(order, order.price, is_taker=False)
            for order in list(self.buy_book):
                order:Order
                if order.price_int >= self.best_ask_price_int:
                    self.fill_order(order, self.best_ask_price_int / self.PRICE_SCALAR, is_taker=False)
        else:
            self.best_bid_price_int = self.to_int_price(event.price)
            for order in list(self.sell_book):
                order:Order
                if order.price_int <= self.best_bid_price_int:
                    self.fill_order(order, self.best_bid_price_int / self.PRICE_SCALAR, is_taker=False)
            for order in list(self.buy_book):
                order:Order
                if order.price_int > self.best_bid_price_int:
                    self.fill_order(order, order.price, is_taker=False)
                    continue
                if order.price_int == event.price_int:
                    order.traded += event.size
                if (order.rank - order.traded) <= -order.quantity:
                    self.fill_order(order, order.price, is_taker=False)
                
    