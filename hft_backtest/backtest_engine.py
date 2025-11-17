"""
回测引擎
组装server / client event engine
构建双向delay bus
收取多个数据源 组装MergedDataset
server端创建match engine settlement engine recorder
创建双端Account
迭代数据源 推送数据事件到事件引擎 推进时间轴
"""
from hft_backtest.event_engine import EventEngine
from hft_backtest.delay_bus import DelayBus
from hft_backtest.dataset import Dataset, MergedDataset
from hft_backtest.match_engine import MatchEngine
from hft_backtest.settlement_engine import SettlementEngine
from hft_backtest.recorder import Recorder
from hft_backtest.account import Account
from hft_backtest.strategy import Strategy

class BacktestEngine:
    def __init__(
        self,
        delay_ms: int,
        datasets: list[Dataset],
        match_engine_cls: type[MatchEngine],
        settlement_engine_cls: type[SettlementEngine],
        recorder_dir: str,
        snapshot_interval: int,
        strategy_cls: type[Strategy],
    ):
        # 构建server和client事件引擎
        self.server_engine = EventEngine()
        self.client_engine = EventEngine()

        # 构建双向延迟总线
        self.delaybus_server_to_client = DelayBus(
            source_engine=self.server_engine,
            target_engine=self.client_engine,
            delay=delay_ms,
        )
        self.delaybus_client_to_server = DelayBus(
            source_engine=self.client_engine,
            target_engine=self.server_engine,
            delay=delay_ms,
        )
        
        # 构建合并数据集
        self.merged_dataset = MergedDataset(*datasets)
        
        # 构建match engine
        self.match_engine = match_engine_cls(
            event_engine=self.server_engine
        )
        
        # 构建settlement engine
        self.settlement_engine = settlement_engine_cls(
            event_engine=self.server_engine
        )
        
        # 构建recorder
        self.recorder = Recorder(
            event_engine=self.server_engine,
            dir_path=recorder_dir,
            snapshot_interval=snapshot_interval,
        )
        
        # 构建双端Account
        self.server_account = Account(self.server_engine)
        self.client_account = Account(self.client_engine)

        # 策略
        self.strategy = strategy_cls(
            event_engine=self.client_engine,
        )

    def run(self):
        """启动回测引擎"""
        with self:
            for data_event in self.merged_dataset:
                self.client_engine.put(data_event)

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.recorder.close()
        return False