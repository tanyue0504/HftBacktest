from hft_backtest import *

from my_dataset import Bookticker4, Trades

from datetime import datetime

class Demo(Strategy):
    """
    简单演示策略
    """
    def __init__(
        self,
        event_engine: EventEngine,
    ):
        super().__init__(event_engine)
        event_engine.register(Data, self.on_data)
    
    def on_data(self, data: Data):
        """
        收到数据时打印一下
        """
        pass
        # print(f"[{data.timestamp}] {data.name} data received: {data.data}")

if __name__ == "__main__":
    # 定义数据集
    bookticker_ds = Bookticker4("./test/bookTicker_truncated.parquet")
    trades_ds = Trades("./test/trades_truncated.parquet")
    
    # 构建回测引擎
    engine = BacktestEngine(
        delay_ms=100,
        datasets=[bookticker_ds, trades_ds],
        match_engine_cls=BinanceHftMatcher,
        settlement_engine_cls=SettlementEngine,
        recorder_dir="./test/",
        snapshot_interval=1000 * 60,
        strategy_cls=Demo,
    )
    
    # 运行回测
    dt1 = datetime.now()
    engine.run()
    dt2 = datetime.now()
    print(f"Backtest completed in {(dt2 - dt1).total_seconds()} seconds.")