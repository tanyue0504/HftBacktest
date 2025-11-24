from hft_backtest import *
from hft_backtest.binance import BinanceAccount, BinanceMatcher, BinanceRecorder

import pyarrow.parquet as pq
from datetime import datetime

class BinanceData(Dataset):
    def __init__(
        self,
        name:str,
        path: str,
        timecol: str,
        chunksize: int = 10**6,
        symbol: str = None,
    ):
        super().__init__(name)
        self.path = path
        self.timecol = timecol
        self.chunksize = chunksize
        self.symbol = symbol

    def __iter__(self):
        pq_file = pq.ParquetFile(self.path)
        for batch in pq_file.iter_batches(batch_size=self.chunksize):
            df = batch.to_pandas()
            if self.symbol is not None:
                df['symbol'] = self.symbol
            for line in df.itertuples(index=False):
                yield Data(
                    timestamp=getattr(line, self.timecol),
                    name=self.name,
                    data=line,
                )

def test_dataset():
    bookticker = BinanceData('bookTicker', "./data/bookTicker_truncated.parquet", symbol="BTCUSDT", timecol="transaction_time")
    trades = BinanceData('trades', "./data/trades_truncated.parquet", symbol="BTCUSDT", timecol="time")
    dt0 = datetime.now()
    for data in MergedDataset(bookticker, trades):
        # print(data)
        pass
    dt1 = datetime.now()
    print(f"Data iteration completed in {(dt1 - dt0).total_seconds()} seconds.")

class DemoStrategy(Strategy):
    def __init__(self):
        super().__init__()
        self.flag = 0

    def on_data(self, data: Data):
        if self.flag == 0:
            order = Order.tracking_order(
                symbol="BTCUSDT",
                quantity=0.001,
            )
            self.send_order(order)
            self.flag = 1
        elif self.flag == 1:
            positions = self.event_engine.get_positions()
            if positions:
                for symbol, quantity in positions.items():
                    order = Order.market_order(
                        symbol=symbol,
                        quantity=-quantity,
                    )
                    self.send_order(order)
                    self.flag = 2
        elif self.flag == 2:
            if self.event_engine.get_positions():
                pass
            else:
                exit()
        

if __name__ == "__main__":
    # test_dataset()
    
    bookticker = BinanceData('bookTicker', "./data/bookTicker_truncated.parquet", symbol="BTCUSDT", timecol="transaction_time")
    trades = BinanceData('trades', "./data/trades_truncated.parquet", symbol="BTCUSDT", timecol="time")
    
    demo = DemoStrategy()
    backtest_engine = BacktestEngine(datasets=[bookticker, trades], delay=100)
    matcher = BinanceMatcher()
    backtest_engine.add_component(matcher, is_server=True)
    real_account = BinanceAccount()
    backtest_engine.add_component(real_account, is_server=True)
    recorder = BinanceRecorder(
        dir_path="./record",
        snapshot_interval=60000,
    )
    backtest_engine.add_component(recorder, is_server=True)
    server_printer = EventPrinter("server:", event_types=[Order])
    backtest_engine.add_component(server_printer, is_server=True)
    client_printer = EventPrinter("client:", event_types=[Order])
    backtest_engine.add_component(client_printer, is_server=False)
    local_account = BinanceAccount()
    backtest_engine.add_component(local_account, is_server=False)
    backtest_engine.add_component(demo, is_server=False)
    backtest_engine.run()