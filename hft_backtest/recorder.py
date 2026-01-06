from abc import ABC
from hft_backtest import Component, EventEngine, Order, Event, Account, Timer

class Recorder(Component, ABC):
    """
    记录器基类
    负责记录交易流水(Trades)和定期快照(Snapshots)
    """
    def __init__(self, path: str, account: Account):
        self.path = path
        self.account = account

class TradeRecorder(Recorder):
    """
    交易记录器基类
    负责记录交易流水信息
    """
    def __init__(self, path: str, account: Account, buffer_size:int = 1000):
        super().__init__(path, account)
        self.buffer_size = buffer_size
        self.buffer = []

    def start(self, event_engine: EventEngine):
        self.engine = event_engine
        # 注册Order事件监听
        event_engine.register(Order, self.on_order)
        # 初始化文件并打开
        self.file = open(self.path, "w", encoding="utf-8-sig")
        # 写入表头
        self.buffer.append("timestamp,order_id,symbol,price,quantity,commission\n")

    def stop(self):
        self.flush(flush_to_disk=True)
        self.file.close()

    def on_order(self, order: Order):
        if not order.is_filled:
            return
        # 记录订单信息到缓冲区
        line = f"{order.timestamp},{order.order_id},{order.symbol},{order.filled_price},{order.quantity},{order.commission_fee}\n"
        self.buffer.append(line)
        # 如果缓冲区满了，写入文件
        if len(self.buffer) >= self.buffer_size:
            self.flush()

    def flush(self, flush_to_disk: bool = False):
        # 强制写入缓冲区到文件
        if not self.buffer:
            return
        if not self.file or self.file.closed:
            return
        self.file.writelines(self.buffer)
        if flush_to_disk:
            self.file.flush()
        self.buffer.clear()

class AccountRecorder(Recorder):
    """
    账户记录器基类
    负责记录账户信息:
    1. equity: 瞬时总权益
    2. balance: 瞬时账户现金
    3. flow_commission: 两次快照间的手续费
    4. flow_funding: 两次快照间的资金费
    5. flow_pnl: 两次快照间的盈亏, 不含手续费和资金费, 含未实现盈亏
    6. trade_count: 两次快照间的成交次数
    7. trade_amount: 两次快照间的成交金额
    """
    def __init__(self, path: str, account: Account, interval: int, buffer_size: int = 1000):
        super().__init__(path, account)
        self.interval = interval
        self.current_timestamp = 0
        self.last_timestamp = -interval
        self.buffer = []
        self.buffer_size = buffer_size
        self.last_state_dict = {
            "total_commission_fee": 0.0,
            "total_funding_fee": 0.0,
            "total_pnl": 0.0,
            "total_trade_count": 0,
            "total_trade_amount": 0.0,
        }

    def start(self, engine: EventEngine):
        # 注册账户相关事件监听
        engine.register(Timer, self.on_timer)
        # 打开文件
        self.file = open(self.path, "w", encoding="utf-8-sig")
        # 写入表头
        self.buffer.append("timestamp,equity,balance,commission,funding,pnl,trade_count,trade_amount\n")

    def stop(self):
        self.record(force=True)
        self.flush(flush_to_disk=True)
        self.file.close()

    def flush(self, flush_to_disk: bool = False):
        if not self.buffer:
            return
        if not self.file or self.file.closed:
            return
        self.file.writelines(self.buffer)
        if flush_to_disk:
            self.file.flush()
        self.buffer.clear()

    def on_timer(self, event: Timer):
        self.current_timestamp = event.timestamp
        self.record()

    def record(self, force: bool = False):
        # 判断是否达到记录间隔
        if not force and self.current_timestamp - self.last_timestamp < self.interval:
            return
        self.last_timestamp = self.current_timestamp

        # 指标计算
        equity = self.account.get_equity()
        balance = self.account.get_balance()

        total_commission_fee = self.account.get_total_commission()
        commission = total_commission_fee - self.last_state_dict.get("total_commission_fee", 0)
        self.last_state_dict["total_commission_fee"] = total_commission_fee

        total_funding_fee = self.account.get_total_funding_fee()
        funding = total_funding_fee - self.last_state_dict.get("total_funding_fee", 0)
        self.last_state_dict["total_funding_fee"] = total_funding_fee

        total_pnl = self.account.get_total_trade_pnl()
        pnl = total_pnl - self.last_state_dict.get("total_pnl", 0)
        self.last_state_dict["total_pnl"] = total_pnl

        total_trade_count = self.account.get_total_trade_count()
        trade_count = total_trade_count - self.last_state_dict.get("total_trade_count", 0)
        self.last_state_dict["total_trade_count"] = total_trade_count

        total_trade_amount = self.account.get_total_turnover()
        trade_amount = total_trade_amount - self.last_state_dict.get("total_trade_amount", 0)
        self.last_state_dict["total_trade_amount"] = total_trade_amount

        # 记录到缓冲区
        line = f"{self.current_timestamp},{equity},{balance},{commission},{funding},{pnl},{trade_count},{trade_amount}\n"
        self.buffer.append(line)

        # 如果缓冲区满了，写入文件
        if len(self.buffer) >= self.buffer_size:
            self.flush()

class OrderRecorder(Recorder):
    """
    订单记录器
    负责记录所有订单的全生命周期状态变化，用于 Debug
    """
    def __init__(self, path: str, account: Account, buffer_size: int = 1000):
        super().__init__(path, account)
        self.buffer_size = buffer_size
        self.buffer = []

    def start(self, event_engine: EventEngine):
        # 注册 Order 事件监听
        event_engine.register(Order, self.on_order)
        # 初始化文件并打开
        self.file = open(self.path, "w", encoding="utf-8-sig")
        # 写入表头：增加了 type 和 state
        self.buffer.append("timestamp,order_id,symbol,type,state,price,quantity,filled_price,commission\n")

    def stop(self):
        self.flush(flush_to_disk=True)
        self.file.close()

    def on_order(self, order: Order):
        # 不做任何过滤，记录所有收到的 Order 事件
        # 注意：order.order_type 和 order.state 通常是整数枚举值，直接记录即可
        line = (
            f"{order.timestamp},"
            f"{order.order_id},"
            f"{order.symbol},"
            f"{order.order_type},"
            f"{order.state},"
            f"{order.price},"
            f"{order.quantity},"
            f"{order.filled_price},"
            f"{order.commission_fee}\n"
        )
        self.buffer.append(line)

        # 如果缓冲区满了，写入文件
        if len(self.buffer) >= self.buffer_size:
            self.flush()

    def flush(self, flush_to_disk: bool = False):
        # 强制写入缓冲区到文件
        if not self.buffer:
            return
        if not self.file or self.file.closed:
            return
        self.file.writelines(self.buffer)
        if flush_to_disk:
            self.file.flush()
        self.buffer.clear()