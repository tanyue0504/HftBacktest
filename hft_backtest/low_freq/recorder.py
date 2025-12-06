import time
from pathlib import Path
from hft_backtest import Recorder, Order, OrderState, Data

class BarRecorder(Recorder):
    """
    低频/K线专用记录器
    特点：
    1. 默认每收到一条Bar数据就进行一次快照（对齐K线）
    2. 保留了详细的 PnL 分解逻辑
    """
    
    BUFFER_LINES = 1000 

    def __init__(
        self,
        dir_path: str,
        snapshot_interval: int = 0, # 0 表示每条 Bar 都记录
    ):
        # 基础初始化逻辑保持不变
        timestamp = int(time.time())
        self.dir_path = Path(dir_path)
        self.dir_path.mkdir(parents=True, exist_ok=True)
        self.snapshot_interval = snapshot_interval
        
        self.trade_file_path = self.dir_path / f"{timestamp}_trades.csv"
        self.snapshot_file_path = self.dir_path / f"{timestamp}_snapshots.csv"
        
        self.trade_file = open(self.trade_file_path, "w", encoding="utf-8-sig")
        self.snapshot_file = open(self.snapshot_file_path, "w", encoding="utf-8-sig")
        
        self.trade_file.write("time,symbol,quantity,price,commission\n")
        self.snapshot_file.write("time,symbol,position_cash,margin,funding_fee,commission_fee,pnl,count\n")
        
        self.engine_timestamp = 0
        self.last_snapshot_time = 0
        
        self.funding_fee_dict = {}    
        self.commission_fee_dict = {} 
        self.pnl_dict = {}             
        self.count_dict = {}           
        self.last_position_cash_dict = {} 

        self.trade_buffer = []
        self.snapshot_buffer = []

    def stop(self):
        self.snapshot(forced=True)
        self.trade_file.writelines(self.trade_buffer)
        self.snapshot_file.writelines(self.snapshot_buffer)
        self.trade_file.flush()
        self.snapshot_file.flush()
        self.trade_file.close()
        self.snapshot_file.close()

    def snapshot(self, forced: bool = False):
        # 修改点：如果 snapshot_interval 为 0，则仅由外部强制调用（如 on_data）触发
        if not forced and self.snapshot_interval > 0:
            if self.engine_timestamp - self.last_snapshot_time < self.snapshot_interval:
                return
        
        timestamp = self.engine_timestamp
        self.last_snapshot_time = timestamp
        
        # 获取状态
        positions = self.event_engine.get_positions()
        prices = self.event_engine.get_prices() # 注意：这里依赖 Account 更新 Price
        
        # 计算逻辑保持原样，非常严谨
        all_symbols = set().union(
            self.commission_fee_dict.keys(),
            self.pnl_dict.keys(),
            self.count_dict.keys(),
            self.last_position_cash_dict.keys(),
            positions.keys()
        )

        for symbol in all_symbols:
            # PnL = 市值变化 + 现金流(已实现盈亏) - 费用
            # 注意：低频回测经常忽略资金费，funding_fee_dict 可能为空
            price = prices.get(symbol, 0.0)
            qty = positions.get(symbol, 0.0)
            
            position_cash = qty * price
            margin = abs(position_cash) # 简化保证金计算
            
            funding_fee = self.funding_fee_dict.get(symbol, 0.0)
            commission_fee = self.commission_fee_dict.get(symbol, 0.0)
            
            # 核心公式：当前市值 - 上次市值 + 期间已实现现金流
            pnl = position_cash - self.last_position_cash_dict.get(symbol, 0.0) + self.pnl_dict.get(symbol, 0.0)
            
            self.last_position_cash_dict[symbol] = position_cash
            count = self.count_dict.get(symbol, 0)
            
            self.snapshot_buffer.append(f"{timestamp},{symbol},{position_cash},{margin},{funding_fee},{commission_fee},{pnl},{count}\n")
        
        if len(self.snapshot_buffer) >= self.BUFFER_LINES:
            self.snapshot_file.writelines(self.snapshot_buffer)
            self.snapshot_buffer = []

        # 重置期间累计字段
        self.funding_fee_dict.clear()
        self.commission_fee_dict.clear()
        self.pnl_dict.clear()
        self.count_dict.clear()

    def on_order(self, order: Order):
        self.engine_timestamp = self.event_engine.timestamp
        if order.state != OrderState.FILLED:
            return
            
        # 累计已实现盈亏（Cash Flow）
        self.commission_fee_dict[order.symbol] = self.commission_fee_dict.get(order.symbol, 0.0) + order.commission_fee
        # 现金流 = 卖出得钱(正) - 买入花钱(负) = -1 * qty * price
        self.pnl_dict[order.symbol] = self.pnl_dict.get(order.symbol, 0.0) - order.quantity * order.filled_price
        self.count_dict[order.symbol] = self.count_dict.get(order.symbol, 0) + 1
        
        # 记录成交明细
        line = f"{self.engine_timestamp},{order.symbol},{order.quantity},{order.filled_price},{order.commission_fee}\n"
        self.trade_buffer.append(line)
        if len(self.trade_buffer) >= self.BUFFER_LINES:
            self.trade_file.writelines(self.trade_buffer)
            self.trade_buffer = []

    def on_data(self, data: Data):
        self.engine_timestamp = data.timestamp
        
        # 修改点：收到 Bar 数据后，强制记录一次快照
        # 这样能保证每根 K 线都有记录，且记录的是该 K 线收盘后的状态
        if data.name in ["bars", "candles"]:
            self.snapshot(forced=True)