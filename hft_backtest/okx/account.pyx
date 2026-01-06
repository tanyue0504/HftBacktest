# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False

from collections import defaultdict
from hft_backtest.event_engine cimport EventEngine
from hft_backtest.order cimport Order
from hft_backtest.okx.event cimport OKXTrades, OKXFundingRate, OKXDelivery
from hft_backtest.account cimport Account

cdef class OKXAccount(Account):
    def __init__(self, double initial_balance = 0.0):
        super().__init__()
        
        # --- 核心状态 ---
        self.cash_balance = initial_balance
        self.position_dict = defaultdict(int)
        self.order_dict = {}
        
        # 【新增】已终结订单集合 (防止乱序事件导致僵尸单复活)
        # 存储 order_id
        self.finished_order_ids = set()

        self.price_dict = {}

        # --- 累计统计 ---
        self.total_turnover = defaultdict(float)
        self.total_commission = defaultdict(float)
        self.total_funding_fee = defaultdict(float)
        self.net_cash_flow = defaultdict(float)
        self.total_trade_count = defaultdict(int)

    cpdef start(self, EventEngine engine):
        engine.register(Order, self.on_order)
        engine.register(OKXTrades, self.on_trade_data)
        engine.register(OKXFundingRate, self.on_funding_data)
        engine.register(OKXDelivery, self.on_delivery_data)
        
    cpdef stop(self):
        pass

    # ==========================
    # 核心事件处理
    # ==========================

    cpdef void on_order(self, Order order):
        cdef double cash_flow
        cdef str symbol

        # 1. 过滤掉单纯的撤单请求 (Type=CANCEL, State=None/Created)
        # 注意：如果你修改了 Matcher 发送 LIMIT 类型的 CANCELED 回报，这里不会拦截回报
        if order.is_cancel_order:
            return

        # 2. 【核心修复】如果订单已知已终结，忽略任何后续消息 (如迟到的 RECEIVED)
        if order.order_id in self.finished_order_ids:
            return

        # 3. 处理终结状态 (FILLED / CANCELED / REJECTED)
        if order.is_filled or order.is_canceled or order.is_rejected:
            # 标记为已终结
            self.finished_order_ids.add(order.order_id)
            
            # 从活跃列表移除
            if order.order_id in self.order_dict:
                del self.order_dict[order.order_id]

            # 如果是成交，处理资金
            if order.is_filled:
                symbol = order.symbol
                self.total_turnover[symbol] += abs(order.quantity * order.filled_price)
                self.total_commission[symbol] += order.commission_fee
                self.total_trade_count[symbol] += 1
                
                cash_flow = -1 * order.quantity * order.filled_price
                self.net_cash_flow[symbol] += cash_flow
                self.cash_balance += cash_flow
                self.cash_balance -= order.commission_fee

                self.position_dict[symbol] += order.quantity_int
                if self.position_dict[symbol] == 0:
                    del self.position_dict[symbol]
            return

        # 4. 处理活跃状态 (SUBMITTED / RECEIVED)
        if order.is_submitted or order.is_received:
            # 只有不在终结集合里才添加 (上面已检查)
            self.order_dict[order.order_id] = order
            return

    cpdef void on_trade_data(self, OKXTrades event):
        self.price_dict[event.symbol] = event.price

    cpdef void on_funding_data(self, OKXFundingRate event):
        cdef long pos_int = self.position_dict.get(event.symbol, 0)
        if pos_int == 0:
            return
            
        cdef double pos_float = pos_int / <double>Order.SCALER
        cdef double funding_fee = pos_float * event.price * event.funding_rate
        
        self.cash_balance -= funding_fee
        self.total_funding_fee[event.symbol] += funding_fee

    cpdef void on_delivery_data(self, OKXDelivery event):
        cdef long pos_int = self.position_dict.get(event.symbol, 0)
        if pos_int == 0:
            return

        cdef double pos_float = pos_int / <double>Order.SCALER
        cdef double cash_flow = pos_float * event.price
        
        self.cash_balance += cash_flow
        self.net_cash_flow[event.symbol] += cash_flow
        
        del self.position_dict[event.symbol]

        # 清理相关订单
        cdef list keys = list(self.order_dict.keys())
        cdef Order order
        for oid in keys:
            order = self.order_dict[oid]
            if order.symbol == event.symbol:
                del self.order_dict[oid]
                # 也要加入终结集合，防止后续诈尸
                self.finished_order_ids.add(oid)

    # ==========================
    # 查询接口 (保持不变)
    # ==========================

    cpdef dict get_orders(self):
        return self.order_dict.copy()
    
    cpdef dict get_positions(self):
        return {k: v / <double>Order.SCALER for k, v in self.position_dict.items()}
    
    cpdef dict get_prices(self):
        return self.price_dict.copy()
    
    cpdef double get_balance(self):
        return self.cash_balance

    cdef double _get_position_cashvalue(self):
        cdef double total = 0.0
        cdef str sym
        cdef long qty_int
        cdef double price
        
        for sym, qty_int in self.position_dict.items():
            price = self.price_dict.get(sym, 0.0)
            total += (qty_int / <double>Order.SCALER) * price
        return total

    cpdef double get_position_cashvalue(self):
        return self._get_position_cashvalue()

    cpdef double get_equity(self):
        return self.cash_balance + self._get_position_cashvalue()
    
    cpdef double get_total_margin(self):
        cdef double total = 0.0
        cdef str sym
        cdef long qty_int
        
        for sym, qty_int in self.position_dict.items():
            total += (abs(qty_int) / <double>Order.SCALER) * self.price_dict.get(sym, 0.0)
        return total
    
    def get_leverage(self):
        cdef double equity = self.get_equity()
        if equity == 0:
            return 1
        return self.get_total_margin() / equity
    
    cpdef double get_total_turnover(self):
        return sum(self.total_turnover.values())
    
    cpdef int get_total_trade_count(self):
        return sum(self.total_trade_count.values())
    
    cpdef double get_total_commission(self):
        return sum(self.total_commission.values())
    
    cpdef double get_total_funding_fee(self):
        return sum(self.total_funding_fee.values())
        
    cpdef double get_total_trade_pnl(self):
        return sum(self.net_cash_flow.values()) + self._get_position_cashvalue()