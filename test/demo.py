from hft_backtest import *

from hft_backtest import EventEngine
from my_dataset import Bookticker4, Trades
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
        self.flag = False

    def on_data(self, data: Data):
        if self.flag:
            return
        print(f"Received data: {data}")
        self.flag = True

if __name__ == "__main__":
    # test_dataset()
    
    bookticker = BinanceData('bookTicker', "./data/bookTicker_truncated.parquet", symbol="BTCUSDT", timecol="transaction_time")
    trades = BinanceData('trades', "./data/trades_truncated.parquet", symbol="BTCUSDT", timecol="time")
    
    demo = DemoStrategy()
    engine = BacktestEngine(
        datasets=[bookticker, trades],
    )
    engine.add_component(demo, is_server=False)
    engine.run()