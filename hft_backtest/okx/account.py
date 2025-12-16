from collections import defaultdict
from hft_backtest import EventEngine, Order, OrderState
from hft_backtest.account import Account
from .event import OKXTrades, OKXFundingRate, OKXDelivery

class OKXAccount(Account):

    """
    账户的会计核算逻辑
    发生一笔交易时:
    1. 如果是多单, cashflow 负值, 余额减少; 如果是空单, cashflow 正值, 余额增加
    2. 计算手续费, 余额减少
    3. 更新持仓 (使用整数避免精度问题)

    cash_balance = initial_balance + sum(cash_flows) - sum(commission_fees) - sum(funding_fees)
    equity = cash_balance + sum(position_cashvalue)
    position_cashvalue = sum( quantity * last_price )
    total_trade_pnl = sum(cash_flows) + sum(position_cashvalue)
    
    """
    
    
    
    def __init__(self, initial_balance: float = 0.0):
        super().__init__()
        
        # --- 核心状态 ---
        self.cash_balance = initial_balance     # 账户现金余额 (USDT)
        self.position_dict = defaultdict(int)   # symbol -> quantity_int (带 SCALER)
        self.order_dict: dict[int, Order] = {}  # order_id -> Order 对象
        self.price_dict = defaultdict(float)    # symbol -> last_price (最新成交价)

        # --- 累计统计 (用于 Recorder 差分计算) ---
        self.total_turnover = defaultdict(float)  # symbol -> 累计成交金额
        self.total_commission = defaultdict(float)  # symbol -> 累计手续费
        self.total_funding_fee = defaultdict(float) # symbol -> 累计资金费
        self.net_cash_flow = defaultdict(float)     # symbol -> 累计交易净现金流 (用于计算余额变化)
        self.total_trade_count = defaultdict(int)   # symbol -> 累计成交次数

    def start(self, engine: EventEngine):
        # 注册监听
        engine.register(Order, self.on_order)
        engine.register(OKXTrades, self.on_trade_data)
        engine.register(OKXFundingRate, self.on_funding_data)
        engine.register(OKXDelivery, self.on_delivery_data)
        
    def stop(self):
        pass

    # ==========================
    # 核心事件处理
    # ==========================

    def on_order(self, order: Order):
        """处理订单状态变化"""
        # 1. 过滤撤单
        if order.is_cancel:
            return

        # 2. 维护活跃订单
        if order.state in (OrderState.SUBMITTED, OrderState.RECEIVED):
            self.order_dict[order.order_id] = order
            return
        
        # 3. 处理成交
        if order.state == OrderState.FILLED:
            symbol = order.symbol
            
            # A. 累计统计更新
            self.total_turnover[symbol] += abs(order.quantity * order.filled_price)
            self.total_commission[symbol] += order.commission_fee
            self.total_trade_count[symbol] += 1
            
            # B. 计算现金流 (Cash Flow)
            # 买入(qty>0): 现金减少; 卖出(qty<0): 现金增加
            # 这是一个会计恒等式: Balance_new = Balance_old - Qty * Price - Fee
            cash_flow = -1 * order.quantity * order.filled_price
            
            self.net_cash_flow[symbol] += cash_flow
            self.cash_balance += cash_flow            # 更新余额
            self.cash_balance -= order.commission_fee # 扣除手续费

            # C. 更新持仓 (使用整数维护避免精度问题)
            self.position_dict[symbol] += order.quantity_int
            if self.position_dict[symbol] == 0:
                del self.position_dict[symbol]

        # 4. 清理活跃订单 (FILLED 或 CANCELED)
        if order.order_id in self.order_dict:
            del self.order_dict[order.order_id]

    def on_trade_data(self, event: OKXTrades):
        """维护最新市价，用于计算浮动盈亏"""
        self.price_dict[event.symbol] = event.price

    def on_funding_data(self, event: OKXFundingRate):
        """处理资金费率结算"""
        
        pos_int = self.position_dict.get(event.symbol, 0)
        if pos_int == 0:
            return
            
        # 还原浮点数持仓
        pos_float = pos_int / Order.SCALER
        
        # 计算资金费 (通常: Long 付钱给 Short, 若 rate > 0)
        # 费用 = 持仓 * 价格 * 费率
        funding_fee = pos_float * self.price_dict[event.symbol] * event.funding_rate
        
        self.cash_balance -= funding_fee
        self.total_funding_fee[event.symbol] += funding_fee

    def on_delivery_data(self, event: OKXDelivery):
        """处理交割/强平"""
        
        pos_int = self.position_dict.get(event.symbol, 0)
        if pos_int == 0:
            return

        pos_float = pos_int / Order.SCALER
        
        # 强制平仓的现金流 (相当于以交割价进行一笔反向交易)
        # CashFlow = -1 * (TradeQty) * Price
        # TradeQty = -PosFloat (平仓)
        # CashFlow = -1 * (-PosFloat) * Price = PosFloat * Price
        cash_flow = pos_float * event.price
        
        self.cash_balance += cash_flow
        self.net_cash_flow[event.symbol] += cash_flow
        
        # 清空持仓
        del self.position_dict[event.symbol]

        # 撤销该品种所有活跃挂单
        for order_id, order in list(self.order_dict.items()):
            if order.symbol == event.symbol:
                del self.order_dict[order_id]

    # ==========================
    # 查询接口 (实现 Account 基类抽象方法)
    # ==========================

    def get_orders(self):
        return self.order_dict.copy()
    
    def get_positions(self) -> dict[str, float]:
        return {k: v / Order.SCALER for k, v in self.position_dict.items()}
    
    def get_prices(self):
        return self.price_dict.copy()
    
    def get_balance(self) -> float:
        return self.cash_balance

    def get_equity(self) -> float:
        """
        实现基类接口: 获取账户动态权益
        Equity = Cash Balance + Unrealized PnL (Position Market Value)
        
        注意：self.cash_balance 已经扣除了开仓成本 (entry_price * qty)，
        所以加上 (current_price * qty) 就等于归还了市值。
        Equity = (Init + CashFlow) + (CurrentPrice * Qty)
        这对于线性合约是准确的。
        """
        return self.cash_balance + self.get_position_cashvalue()
    
    def get_total_margin(self):
        return sum(
            (abs(qty_int) / Order.SCALER) * self.price_dict.get(sym, 0.0)
            for sym, qty_int in self.position_dict.items()
        )
    
    def get_leverage(self):
        equity = self.get_equity()
        total_margin = self.get_total_margin()
        if equity == 0:
            return None
        return total_margin / equity

    def get_total_turnover(self) -> float:
        return sum(self.total_turnover.values())
    
    def get_total_trade_count(self) -> int:
        return sum(self.total_trade_count.values())
    
    def get_total_commission(self) -> float:
        return sum(self.total_commission.values())
    
    def get_total_funding_fee(self) -> float:
        return sum(self.total_funding_fee.values())
    
    def get_total_trade_pnl(self) -> float:
        # 计算总交易盈亏，不含手续费和资金费，含未平仓盈亏
        return sum(self.net_cash_flow.values()) + self.get_position_cashvalue()
    
    def get_position_cashvalue(self) -> float:
        # 计算持仓现金流
        return sum(
            (qty_int / Order.SCALER) * self.price_dict.get(sym, 0.0)
            for sym, qty_int in self.position_dict.items()
        )