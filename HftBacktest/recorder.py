import time
from pathlib import Path
from settlement_engine import CalcFundingRate
from event_engine import EventEngine
from order import Order, OrderState

class Recorder:
    """
    记录类

    关键公式
    期间盈亏 = 持仓价值 + 现金流入 - 现金流出 - 手续费 - 资金费率
    持仓价值 = 持仓按市价平仓可带来的现金流入
    若做空视作现金流入, 平仓时视作现金流出
    手续费 = 成交量 * 成交价 * 佣金费率
    资金费 = 持仓量 * 市价 * 资金费率
    return rate = diff pnl / margin
    margin = 持仓绝对数额 * 市价 * 保证金率

    快照记录内容:
    持仓价值、保证金占用、资金费、现金流入流出、手续费、pnl
    
    快照记录粒度：symbol + timestamp
    记录文件格式：CSV
    记录文件路径：dir_path/snapshots_dt.csv
    记录文件字段：
    索引字段
    timestamp(int, 毫秒), symbol(str),
    状态字段
    position_cash(float, 平仓的现金流入，负数表示现金流出),
    margin(float, 保证金占用),
    流量字段（含义为两次快照之间的变化量）
    funding_fee(float, 资金费),
    commission_fee(float, 手续费),
    pnl(float, 期间盈亏， 不含资金费和手续费)，
    count(int, 该快照期间内的成交次数)
    """
    def __init__(
        self,
        event_engine: EventEngine,
        dir_path: str,          # 记录文件夹路径
        snapshot_interval: int, # 快照间隔，单位毫秒
    ):
        # 生成当前秒级时间戳, 用于记录文件命名
        timestamp = int(time.time())
        self.event_engine = event_engine
        self.dir_path = Path(dir_path)
        self.dir_path.mkdir(parents=True, exist_ok=True)
        self.snapshot_interval = snapshot_interval
        
        # 初始化成交文件和快照文件路径
        self.trade_file_path = self.dir_path / f"{timestamp}_trades.csv"
        self.snapshot_file_path = self.dir_path / f"{timestamp}_snapshots.csv"
        
        # 打开文件
        self.trade_file = open(self.trade_file_path, "w", encoding="utf-8-sig")
        self.snapshot_file = open(self.snapshot_file_path, "w", encoding="utf-8-sig")
        
        # 写入表头
        self.trade_file.write("time,symbol,quantity,price,commission\n")
        self.snapshot_file.write("time,symbol,position_cash,margin,funding_fee,commission_fee,pnl,count\n")
        
        # 快照字段初始化
        self.engine_timestamp = None  # 事件引擎时间戳
        self.last_snapshot_time = None  # 上次快照时间戳
        
        # 状态字段触发快照时计算
        self.funding_fee_dict = {}    # symbol -> funding_fee 期间累计
        self.commission_fee_dict = {}  # symbol -> commission_fee 期间累计
        self.pnl_dict = {}             # symbol -> pnl 期间累计
        self.count_dict = {}           # symbol -> count 期间累计

        # 注册监听
        event_engine.register(Order, self.on_order)
        event_engine.register(CalcFundingRate, self.on_calc_funding_rate)

    def close(self):
        """关闭记录文件"""
        self.trade_file.close()
        self.snapshot_file.close()

    def snapshot(self, forced: bool = False):
        # 判断是否达到快照间隔
        if not forced and self.last_snapshot_time is not None:
            if self.engine_timestamp - self.last_snapshot_time < self.snapshot_interval:
                return
        # 记录快照时间
        timestamp = self.engine_timestamp
        self.last_snapshot_time = timestamp
        # 提取数据
        positions = self.event_engine.get_positions()
        prices = self.event_engine.get_prices()
        # 计算并写入每个symbol的快照
        lines = []
        for symbol in set(self.commission_fee_dict.keys()).union(self.pnl_dict.keys()).union(self.count_dict.keys()):
            position_cash = - positions.get(symbol, 0.0) * prices.get(symbol, 0.0)
            margin = abs(position_cash)
            funding_fee = self.funding_fee_dict.get(symbol, 0.0)
            commission_fee = self.commission_fee_dict.get(symbol, 0.0)
            pnl = self.pnl_dict.get(symbol, 0.0) + position_cash
            count = self.count_dict.get(symbol, 0)
            lines.append(f"{timestamp},{symbol},{position_cash},{margin},{funding_fee},{commission_fee},{pnl},{count}\n")
        # 写入快照文件
        self.snapshot_file.writelines(lines)
        self.snapshot_file.flush()
        # 重置累计字段
        self.funding_fee_dict.clear()
        self.commission_fee_dict.clear()
        self.pnl_dict.clear()
        self.count_dict.clear()

    def on_order(self, order: Order):
        # 更新引擎时间戳
        self.engine_timestamp = self.event_engine.timestamp
        # 仅在成交时累计
        if order.state != OrderState.FILLED:
            return
        # 更新流量变量
        # 更新pnl时只要记录成交的现金流入流出即可，平仓价值在快照时计算
        self.commission_fee_dict[order.symbol] = self.commission_fee_dict.get(order.symbol, 0.0) + order.commission_fee
        self.pnl_dict[order.symbol] = self.pnl_dict.get(order.symbol, 0.0) - order.quantity * order.filled_price
        self.count_dict[order.symbol] = self.count_dict.get(order.symbol, 0) + 1
        # 调用快照（不强制）
        self.snapshot(forced=False)

    def on_calc_funding_rate(self, event: CalcFundingRate):
        # 更新引擎时间戳
        self.engine_timestamp = self.event_engine.timestamp
        # 解析资金费
        self.funding_fee_dict = event.funding_rate_dict
        # 强制快照
        self.snapshot(forced=True)