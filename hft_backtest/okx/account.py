from collections import defaultdict
from hft_backtest import Component, Order, OrderState, EventEngine
from .event import OKXTrades, OKXFundingRate, OKXDelivery

class OKXAccount(Component):
    """
    OKX 专用账户类 (服务端视角)
    
    职责：
    1. 维护账户状态：持仓(Position), 余额(Balance), 挂单(Orders)
    2. 维护市场状态：最新成交价(Price)
    3. 执行结算逻辑：处理资金费率(Funding), 交割强平(Delivery)
    4. 统计累计数据：为 Recorder 提供历史累计的费用和盈亏数据
    """
    
    def __init__(self, initial_balance: float = 0.0):
        super().__init__()
        
        # --- 核心状态 ---
        self.cash_balance = initial_balance          # 账户现金余额 (USDT/USDC)
        self.position_dict = defaultdict(int)   # symbol -> quantity_int (带 SCALER 的整数)
        self.order_dict: dict[int, Order] = {}  # order_id -> Order 对象
        self.price_dict = defaultdict(float)    # symbol -> last_price (最新成交价)

        # --- 累计统计 (用于 Recorder 差分计算) ---
        self.total_commission = defaultdict(float)  # symbol -> 累计手续费
        self.total_funding_fee = defaultdict(float) # symbol -> 累计资金费
        self.total_trade_pnl = defaultdict(float)   # symbol -> 累计已实现交易盈亏(现金流)
        self.total_trade_count = defaultdict(int)   # symbol -> 累计成交次数

    def start(self, engine: EventEngine):
        # 注册监听特定类型的事件
        engine.register(Order, self.on_order)
        engine.register(OKXTrades, self.on_trade_data)
        engine.register(OKXFundingRate, self.on_funding_data)
        engine.register(OKXDelivery, self.on_delivery_data)
        
        # 注入查询接口 (供策略和Recorder使用)
        engine.get_orders = self.get_orders
        engine.get_positions = self.get_positions
        engine.get_prices = self.get_prices
        engine.get_position_cashvalue = self.get_position_cashvalue
        engine.get_cumulative_commision = self.get_cumulative_commission
        engine.get_cumulative_funding_fee = self.get_cumulative_funding_fee
        engine.get_cumulative_trade_pnl = self.get_cumulative_trade_pnl
        engine.get_equity = self.get_equity

    def stop(self):
        pass

    # ==========================
    # 核心事件处理
    # ==========================

    def on_order(self, order: Order):
        """处理订单状态变化"""
        # 1. 过滤撤单指令
        if order.is_cancel:
            return

        # 2. 维护活跃订单字典
        if order.state in (OrderState.SUBMITTED, OrderState.RECEIVED):
            self.order_dict[order.order_id] = order
            return
        
        # 3. 处理成交
        if order.state == OrderState.FILLED:
            symbol = order.symbol
            
            # A. 累计统计更新
            self.total_commission[symbol] += order.commission_fee
            self.total_trade_count[symbol] += 1
            
            # B. 计算现金流 (Realized PnL of this trade)
            # 买入(qty>0)消耗现金，卖出(qty<0)获得现金
            # cash_flow = -1 * quantity * price
            cash_flow = -1 * order.quantity * order.filled_price
            self.total_trade_pnl[symbol] += cash_flow
            self.cash_balance += cash_flow # 更新余额
            self.cash_balance -= order.commission_fee # 扣除手续费

            # C. 更新持仓 (使用整数维护避免精度问题)
            self.position_dict[symbol] += order.quantity_int
            if self.position_dict[symbol] == 0:
                del self.position_dict[symbol]

        # 4. 清理活跃订单 (FILLED 或 CANCELED)
        if order.order_id in self.order_dict:
            del self.order_dict[order.order_id]

    def on_trade_data(self, event: OKXTrades):
        """处理最新成交数据，维护市价"""
        row = event.data
        # 假设 row 包含 symbol 和 price 字段
        self.price_dict[row.symbol] = row.price

    def on_funding_data(self, event: OKXFundingRate):
        """处理资金费率结算"""
        row = event.data
        symbol = row.symbol
        
        # 1. 获取持仓
        pos_int = self.position_dict.get(symbol, 0)
        if pos_int == 0:
            return
            
        # 2. 计算资金费
        # 公式: 持仓量 * 标记价格 * 资金费率
        # 注意: 需要将整数持仓转回浮点数
        pos_float = pos_int / Order.SCALER
        
        # 使用事件中的 price (通常是标记价格)
        funding_fee = pos_float * row.price * row.funding_rate
        
        # 3. 结算
        self.cash_balance -= funding_fee
        self.total_funding_fee[symbol] += funding_fee

    def on_delivery_data(self, event: OKXDelivery):
        """处理交割/强平数据"""
        row = event.data
        symbol = row.symbol
        delivery_price = row.price
        
        pos_int = self.position_dict.get(symbol, 0)
        if pos_int == 0:
            return

        pos_float = pos_int / Order.SCALER
        
        # 1. 强制按交割价平仓的现金流
        # 平仓相当于做一笔反向交易: qty = -pos_float
        cash_flow = -1 * (-pos_float) * delivery_price
        
        # 2. 结算
        self.cash_balance += cash_flow
        self.total_trade_pnl[symbol] += cash_flow
        
        # 3. 清空持仓
        del self.position_dict[symbol]

        # 4.撤销该品种所有活跃挂单
        for order_id, order in list(self.order_dict.items()):
            if order.symbol == symbol:
                del self.order_dict[order_id]


    # ==========================
    # 查询接口 (供 Recorder/Strategy 使用)
    # ==========================

    def get_orders(self):
        return self.order_dict.copy()
    
    def get_positions(self):
        """返回浮点数格式的持仓"""
        return {k: v / Order.SCALER for k, v in self.position_dict.items()}

    def get_prices(self):
        return self.price_dict.copy()
    
    def get_position_cashvalue(self, symbol: str = None) -> float:
        "获取某品种平仓的现金流, 如果 symbol=None 则返回所有品种汇总"
        if symbol is None:
            total_cashvalue = 0.0
            for symbol in self.position_dict:
                total_cashvalue += self.get_position_cashvalue(symbol)
            return total_cashvalue
        else:
            pos_int = self.position_dict.get(symbol, 0)
            if pos_int == 0:
                return 0.0
            price = self.price_dict.get(symbol, 0.0)
            return (pos_int / Order.SCALER) * price

    def get_cumulative_commission(self, symbol: str = None) -> float:
        "获取累计手续费，如果 symbol=None 则返回所有品种汇总"
        if symbol is None:
            return sum(self.total_commission.values())
        else:
            return self.total_commission.get(symbol, 0.0)
        
    def get_cumulative_funding_fee(self, symbol: str = None) -> float:
        "获取累计资金费，如果 symbol=None 则返回所有品种汇总"
        if symbol is None:
            return sum(self.total_funding_fee.values())
        else:
            return self.total_funding_fee.get(symbol, 0.0)
        
    def get_cumulative_trade_pnl(self, symbol: str = None) -> float:
        "获取累计已实现交易盈亏，如果 symbol=None 则返回所有品种汇总"
        if symbol is None:
            return sum(self.total_trade_pnl.values()) + self.get_position_cashvalue()
        else:
            return self.total_trade_pnl.get(symbol, 0.0) + self.get_position_cashvalue(symbol)
        
    def get_equity(self) -> float:
        "获取账户动态权益 = 余额 + 未实现盈亏"
        equity = self.cash_balance
        # 加上持仓的浮动盈亏 (市值)
        # 注意: 这里的 balance 已经包含了开仓时的现金流出(-qty*price)
        # 所以 Equity = Balance + sum(qty * current_price)
        # 例子: 100U, 买1个BTC(价格10), Balance=90. Equity = 90 + 1*10 = 100.
        # 涨到11: Equity = 90 + 1*11 = 101. 正确。
        for symbol, pos_int in self.position_dict.items():
            if pos_int == 0: continue
            price = self.price_dict.get(symbol, 0.0)
            equity += (pos_int / Order.SCALER) * price
            
        return equity