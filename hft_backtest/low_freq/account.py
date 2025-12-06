from hft_backtest import Order, OrderState, Data, Account

class BarAccount(Account):
    """
    低频账户类
    """
    def __init__(self):
        self.order_dict: dict[int, Order] = {}
        self.position_dict: dict[str, int] = {} # Modify: 类型标注改为 int，更准确
        self.price_dict: dict[str, float] = {}

    def on_order(self, order: Order):
        # ... (前面的逻辑保持不变) ...
        assert isinstance(order, Order)
        if order.is_cancel:
            return
            
        state = order.state
        assert state != OrderState.CREATED
        
        if state in (OrderState.SUBMITTED, OrderState.RECEIVED):
            self.order_dict[order.order_id] = order
            return
        elif state == OrderState.FILLED:
            # 更新持仓 (逻辑完全正确，保持不变)
            pos = self.position_dict[order.symbol] = self.position_dict.get(order.symbol, 0) + order.quantity_int
            if pos == 0:
                del self.position_dict[order.symbol]
        
        # Modify: 安全删除，防止 KeyError
        if order.order_id in self.order_dict:
            del self.order_dict[order.order_id]

    def on_data(self, data: Data):
        # Modify: 稍微放宽一点名字检查，兼容性更好
        # 如果你的 Dataset 名字叫 "candles" 或 "bars"，这里都能通过
        if data.name not in ["bar", "bars", "candle", "candles"]:
            return
            
        line = data.data
        
        # Modify: 兼容 close 和 c (Parquet 常见缩写)
        symbol = getattr(line, 'symbol', None)
        close_px = getattr(line, 'close', getattr(line, 'c', None))

        if symbol is not None and close_px is not None:
            self.price_dict[symbol] = close_px

    def get_orders(self):
        return self.order_dict.copy()
    
    def get_positions(self):
        # 你的这个逻辑是完美的，适配了框架的 SCALER
        return {k: v / Order.SCALER for k, v in self.position_dict.items()}

    def get_prices(self):
        return self.price_dict.copy()