from collections import defaultdict
from hft_backtest import MatchEngine, Order, OrderState, OrderType, Data

class BarMatcher(MatchEngine):
    """
    低频/K线撮合引擎 (优化版)
    适用场景：分钟线/小时线/日线回测
    """

    def __init__(
        self,
        taker_fee: float = 2e-4,
        maker_fee: float = 1.1e-4,
    ):
        self.taker_fee = taker_fee
        self.maker_fee = maker_fee
        
        # 优化 1: 按 symbol 分组存储订单
        # 结构: symbol -> {order_id: Order}
        self.active_orders: dict[str, dict[int, Order]] = defaultdict(dict)
        
        # 辅助索引: order_id -> symbol (用于快速撤单)
        self.order_id_map: dict[int, str] = {}
        
        self.data_processors = {
            "bars": self.process_bar_data,
        }

    def _fill_order(self, order: Order, filled_price: float, is_taker: bool):
        """内部撮合辅助函数"""
        new_order = order.derive()
        new_order.state = OrderState.FILLED
        new_order.filled_price = filled_price
        
        # 计算手续费
        raw_fee = abs(filled_price * new_order.quantity)
        new_order.commission_fee = raw_fee * self.taker_fee if is_taker else raw_fee * self.maker_fee
        
        # 从活跃列表移除
        self._remove_order(order.order_id, order.symbol)
            
        self.event_engine.put(new_order)

    def _cancel_order(self, order_id: int):
        """内部撤单辅助函数"""
        symbol = self.order_id_map.get(order_id)
        if symbol is None:
            return

        orders_map = self.active_orders[symbol]
        if order_id not in orders_map:
            return
            
        order = orders_map[order_id]
        new_order = order.derive()
        new_order.state = OrderState.CANCELED
        
        # 移除
        self._remove_order(order_id, symbol)
        
        self.event_engine.put(new_order)

    def _remove_order(self, order_id: int, symbol: str):
        """统一移除逻辑"""
        if symbol in self.active_orders:
            if order_id in self.active_orders[symbol]:
                del self.active_orders[symbol][order_id]
        
        if order_id in self.order_id_map:
            del self.order_id_map[order_id]

    def on_order(self, order: Order):
        # 1. 处理撤单
        if order.is_cancel:
            self._cancel_order(order.cancel_target_id)
            return

        # 2. 仅处理 SUBMITTED
        if order.state != OrderState.SUBMITTED:
            return

        # 3. 接收订单
        new_order = order.derive()
        new_order.state = OrderState.RECEIVED
        
        # 存入对应 symbol 的桶中
        self.active_orders[new_order.symbol][new_order.order_id] = new_order
        self.order_id_map[new_order.order_id] = new_order.symbol
        
        self.event_engine.put(new_order)

    def on_data(self, data: Data):
        if data.name in self.data_processors:
            self.data_processors[data.name](data)

    def process_bar_data(self, data: Data):
        line = data.data
        
        # 优化 2: 鲁棒的字段获取
        symbol = getattr(line, 'symbol', None)
        high = getattr(line, 'high', getattr(line, 'h', None))
        low = getattr(line, 'low', getattr(line, 'l', None))
        open_px = getattr(line, 'open', getattr(line, 'o', None))
        # close_px = getattr(line, 'close', getattr(line, 'c', None)) # 暂时没用到 Close

        if symbol is None or high is None or low is None:
            return 
        
        # 优化 3: 快速查找该品种的订单
        # 如果该品种没有订单，直接跳过，不用遍历所有订单
        orders_map = self.active_orders.get(symbol)
        if not orders_map:
            return

        # 遍历该品种下的活跃订单
        # 使用 list(items) 避免在循环中删除报错，且避免二次查找
        for order_id, order in list(orders_map.items()):
            
            # 市价单
            if order.order_type == OrderType.MARKET_ORDER:
                self._fill_order(order, open_px, is_taker=True)
                continue

            # 限价单
            if order.order_type == OrderType.LIMIT_ORDER:
                if order.quantity > 0: # Buy
                    # 只要最低价 <= 限价，即可成交
                    if low <= order.price:
                        # 撮合价优化：如果开盘即低于限价，按更优的开盘价成交, 但变为了taker
                        if open_px < order.price:
                            self._fill_order(order, open_px, is_taker=True)
                        else:
                            self._fill_order(order, order.price, is_taker=False)
                
                else: # Sell
                    # 只要最高价 >= 限价，即可成交
                    if high >= order.price:
                        # 撮合价优化：如果开盘即高于限价，按更优的开盘价成交 (Gap up)
                        if open_px > order.price:
                            self._fill_order(order, open_px, is_taker=True)
                        else:
                            self._fill_order(order, order.price, is_taker=False)