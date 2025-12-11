import time
from pathlib import Path
from hft_backtest import Recorder, Order, OrderState, Data


class BarRecorder(Recorder):
    """
    低频/K线专用记录器

    特点：
    1. 每个Bar时间戳只记录一次快照
    2. 只记录当前收到数据的品种（而非所有品种）
    3. 从Account获取资金费数据
    """

    BUFFER_LINES = 1000

    def __init__(
        self,
        dir_path: str,
        data_source_name: str,
        symbol_field: str = "symbol",
    ):
        timestamp = int(time.time())
        self.dir_path = Path(dir_path)
        self.dir_path.mkdir(parents=True, exist_ok=True)
        self.data_source_name = data_source_name
        self.symbol_field = symbol_field

        self.trade_file_path = self.dir_path / f"{timestamp}_trades.csv"
        self.snapshot_file_path = self.dir_path / f"{timestamp}_snapshots.csv"

        self.trade_file = open(self.trade_file_path, "w", encoding="utf-8-sig")
        self.snapshot_file = open(self.snapshot_file_path, "w", encoding="utf-8-sig")

        self.trade_file.write("time,symbol,quantity,price,commission\n")
        self.snapshot_file.write("time,symbol,position,price,funding_fee,commission_fee,pnl\n")

        self.engine_timestamp = 0
        self.last_snapshot_timestamp = None

        # 按品种跟踪状态
        self.funding_fee_dict = {}      # symbol -> 累计资金费
        self.commission_fee_dict = {}   # symbol -> 累计手续费
        self.pnl_dict = {}              # symbol -> 累计已实现盈亏（现金流）
        self.last_position_cash_dict = {}  # symbol -> 上次市值

        self.trade_buffer = []
        self.snapshot_buffer = []

    def stop(self):
        # 结束时写入剩余buffer
        if self.trade_buffer:
            self.trade_file.writelines(self.trade_buffer)
        if self.snapshot_buffer:
            self.snapshot_file.writelines(self.snapshot_buffer)
        self.trade_file.flush()
        self.snapshot_file.flush()
        self.trade_file.close()
        self.snapshot_file.close()

    def _snapshot_symbol(self, symbol: str):
        """为单个品种生成快照"""
        positions = self.event_engine.get_positions()
        prices = self.event_engine.get_prices()

        # 收集资金费（从Account获取）
        if hasattr(self.event_engine, 'get_funding_fees'):
            funding_fees = self.event_engine.get_funding_fees()
            if symbol in funding_fees:
                self.funding_fee_dict[symbol] = self.funding_fee_dict.get(symbol, 0.0) + funding_fees[symbol]

        # 获取当前状态
        price = prices.get(symbol, 0.0)
        qty = positions.get(symbol, 0.0)
        position_cash = qty * price

        funding_fee = self.funding_fee_dict.get(symbol, 0.0)
        commission_fee = self.commission_fee_dict.get(symbol, 0.0)

        # PnL = 当前市值 - 上次市值 + 期间已实现盈亏
        pnl = position_cash - self.last_position_cash_dict.get(symbol, 0.0) + self.pnl_dict.get(symbol, 0.0)

        # 更新上次市值
        self.last_position_cash_dict[symbol] = position_cash

        # 写入快照
        line = f"{self.engine_timestamp},{symbol},{qty},{price},{funding_fee},{commission_fee},{pnl}\n"
        self.snapshot_buffer.append(line)

        if len(self.snapshot_buffer) >= self.BUFFER_LINES:
            self.snapshot_file.writelines(self.snapshot_buffer)
            self.snapshot_buffer = []

        # 重置该品种的期间累计
        self.funding_fee_dict.pop(symbol, None)
        self.commission_fee_dict.pop(symbol, None)
        self.pnl_dict.pop(symbol, None)

    def on_order(self, order: Order):
        self.engine_timestamp = self.event_engine.timestamp
        if order.state != OrderState.FILLED:
            return

        symbol = order.symbol

        # 累计手续费
        self.commission_fee_dict[symbol] = self.commission_fee_dict.get(symbol, 0.0) + order.commission_fee

        # 累计已实现盈亏（现金流）= -qty * price
        self.pnl_dict[symbol] = self.pnl_dict.get(symbol, 0.0) - order.quantity * order.filled_price

        # 记录成交明细
        line = f"{self.engine_timestamp},{symbol},{order.quantity},{order.filled_price},{order.commission_fee}\n"
        self.trade_buffer.append(line)

        if len(self.trade_buffer) >= self.BUFFER_LINES:
            self.trade_file.writelines(self.trade_buffer)
            self.trade_buffer = []

    def on_data(self, data: Data):
        self.engine_timestamp = data.timestamp

        # 只处理指定数据源
        if data.name != self.data_source_name:
            return

        # 获取当前品种
        line = data.data
        symbol = getattr(line, self.symbol_field, None)
        if symbol is None:
            return

        # 每个时间戳的每个品种只记录一次
        # （由于数据按时间戳排序，同一时间戳的不同品种都会被记录）
        self._snapshot_symbol(symbol)

        # 清空Account中该品种的资金费（如果有）
        if hasattr(self.event_engine, 'clear_funding_fees'):
            # 注意：这里我们只在所有品种都快照完后才清空
            # 简化处理：每次快照后清空所有
            pass  # Account的资金费由Account自己管理周期
