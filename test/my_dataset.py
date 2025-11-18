"""
demo.py
既是框架测试，也是使用示例

核心使用流程
1. 自定义数据集合，有多少数据源就定义多少个 Dataset 子类
2. 定义策略 Strategy 子类
3. 构建 BacktestEngine，传入数据集列表和策略类
4. 运行 BacktestEngine.run() 开始回测

请注意
最核心的是撮合引擎
而撮合引擎与数据息息相关
目前实现了一个基于binance bookticker & aggTrades/Trades数据的撮合引擎
"""

from hft_backtest.dataset import Data, Dataset

import pandas as pd
from loguru import logger
from datetime import datetime
from pyarrow import parquet as pq

class Bookticker1(Dataset):
    """
    zip csv 全量读 排序 分组推
    """
    def __init__(
        self,
        path: str,
        name: str = "bookTicker",
    ):
        super().__init__(name)
        self.path = path
        dt0 = datetime.now()
        self.data = pd.read_csv(
            path,
            compression="zip",
            usecols=[
            "best_bid_price",
            "best_bid_qty",
            "best_ask_price",
            "best_ask_qty",
            "transaction_time"
            ],
            dtype={
                "best_bid_price": float,
                "best_bid_qty": float,
                "best_ask_price": float,
                "best_ask_qty": float,
                "transaction_time": int,
            },
        )
        dt1 = datetime.now()
        logger.info(f"Loaded Bookticker data from {path}, {len(self.data)} rows.")
        logger.info(f"Read Bookticker CSV in {(dt1 - dt0).total_seconds()} seconds.")
        self.data.sort_values('transaction_time', inplace=True)
        dt2 = datetime.now()
        logger.info(f"Sorted Bookticker data in {(dt2 - dt1).total_seconds()} seconds.")
    
    def __iter__(self):
        for timestamp, df in self.data.groupby('transaction_time'):
            # yield None
            yield Data(
                timestamp=timestamp,
                data=df,
                name=self.name
            )

class Bookticker2(Dataset):
    """
    zipped csv
    chunksize groupby push
    dont check split timestamps between chunks
    """
    def __init__(
        self,
        path: str,
        name: str = "bookTicker",
    ):
        super().__init__(name)
        self.path = path
        
    def __iter__(self):
        for chunk in pd.read_csv(
            self.path,
            compression="zip",
            usecols=[
            "best_bid_price",
            "best_bid_qty",
            "best_ask_price",
            "best_ask_qty",
            "transaction_time"
            ],
            dtype={
                "best_bid_price": float,
                "best_bid_qty": float,
                "best_ask_price": float,
                "best_ask_qty": float,
                "transaction_time": int,
            },
            chunksize=10**6,
        ):
            for timestamp, df in chunk.groupby('transaction_time'):
                yield Data(
                    timestamp=timestamp,
                    data=df,
                    name=self.name
                )

class Bookticker3(Dataset):
    """
    zipped csv
    chunksize groupby push
    check split timestamps between chunks
    """
    def __init__(
        self,
        path: str,
        name: str = "bookTicker",
    ):
        super().__init__(name)
        self.path = path
        
    def __iter__(self):
        # 缓存-合并同timestamp的数据解决chunksize割裂问题
        cache_timestamp = None
        cache_data = None
        for chunk in pd.read_csv(
            self.path,
            compression="zip",
            usecols=[
            "best_bid_price",
            "best_bid_qty",
            "best_ask_price",
            "best_ask_qty",
            "transaction_time"
            ],
            dtype={
                "best_bid_price": float,
                "best_bid_qty": float,
                "best_ask_price": float,
                "best_ask_qty": float,
                "transaction_time": int,
            },
            chunksize=10**6,
        ):
            for timestamp, df in chunk.groupby('transaction_time'):
                if cache_timestamp is None:
                    cache_timestamp = timestamp
                    cache_data = df
                elif cache_timestamp == timestamp:
                    cache_data = pd.concat([cache_data, df], axis=0)
                else:
                    yield Data(
                        timestamp=cache_timestamp,
                        data=cache_data,
                        name=self.name
                    )
                    cache_timestamp = timestamp
                    cache_data = df

class Bookticker4(Dataset):
    """
    parquet
    chunksize groupby push
    check split timestamps between chunks
    """
    def __init__(
        self,
        path: str,
        chunksize: int = 10**6,
        name: str = "bookTicker",
    ):
        super().__init__(name)
        self.path = path
        self.chunksize = chunksize

    def __iter__(self):
        pq_file = pq.ParquetFile(self.path)
        chunk_size = self.chunksize
        # 缓存-合并同timestamp的数据解决chunksize割裂问题
        cache_timestamp = None
        cache_data = None
        for batch in pq_file.iter_batches(batch_size=chunk_size):
            df = batch.to_pandas()
            for timestamp, df in df.groupby('transaction_time'):
                if cache_timestamp is None:
                    cache_timestamp = timestamp
                    cache_data = df
                elif cache_timestamp == timestamp:
                    cache_data = pd.concat([cache_data, df], axis=0)
                else:
                    yield Data(
                        timestamp=cache_timestamp,
                        data=cache_data,
                        name=self.name
                    )
                    cache_timestamp = timestamp
                    cache_data = df
        if cache_timestamp is not None:
            yield Data(
                timestamp=cache_timestamp,
                data=cache_data,
                name=self.name
            )

class Bookticker5(Dataset):
    """
    parquet
    iter tuples
    """
    def __init__(
        self,
        path: str,
        chunksize: int = 10**6,
        name: str = "bookTicker",
    ):
        super().__init__(name)
        self.path = path
        self.chunksize = chunksize

    def __iter__(self):
        pq_file = pq.ParquetFile(self.path)
        chunk_size = self.chunksize
        for batch in pq_file.iter_batches(batch_size=chunk_size):
            df = batch.to_pandas()
            for tp in df.itertuples():
                yield Data(
                    timestamp=tp.transaction_time,
                    data=tp,
                    name=self.name
                )

class Trades(Dataset):
    """
    parquet trades数据集示例
    """
    def __init__(
        self,
        path: str,
        name: str = "trades",
        chunksize: int = 10**6,
    ):
        super().__init__(name)
        self.path = path
        self.chunksize = chunksize

    def __iter__(self):
        pq_file = pq.ParquetFile(self.path)
        chunk_size = self.chunksize
        for batch in pq_file.iter_batches(batch_size=chunk_size):
            df = batch.to_pandas()
            for timestamp, df in df.groupby('time'):
                yield Data(
                    timestamp=timestamp,
                    data=df,
                    name=self.name
                )

def test_push_data(dataset: Dataset):
    start = datetime.now()
    for i, data in enumerate(dataset):
        pass
    end = datetime.now()
    logger.info(f"Elapsed time: {(end - start).total_seconds()} seconds.")
    logger.info(f"Total data points: {i+1}")

def main():
    dataset1 = Bookticker1(
        path="./test/bookTicker_truncated.zip",
    )
    test_push_data(dataset1)
    dataset2 = Bookticker2(
        path="./test/bookTicker_truncated.zip",
    )
    test_push_data(dataset2)
    dataset3 = Bookticker3(
        path="./test/bookTicker_truncated.zip",
    )
    test_push_data(dataset3)
    dataset4 = Bookticker4(
        path="./test/bookTicker_truncated.parquet",
        chunksize=10**6,
    )
    test_push_data(dataset4)
    dataset5 = Bookticker4(
        path="./test/bookTicker_truncated.parquet",
        chunksize=10**5,
    )
    test_push_data(dataset5)
    dataset6 = Bookticker4(
        path="./test/bookTicker_truncated.parquet",
        chunksize=10**4,
    )
    test_push_data(dataset6)
    dataset7 = Bookticker4(
        path="./test/bookTicker_truncated.parquet",
        chunksize=10**3,
    )
    test_push_data(dataset7)
    dataset8 = Bookticker5(
        path="./test/bookTicker_truncated.parquet",
        chunksize=10**6,
    )
    test_push_data(dataset8)

if __name__ == "__main__":
    dataset8 = Bookticker5(
        path="./test/bookTicker_truncated.parquet",
        chunksize=10**6,
    )
    test_push_data(dataset8)
    # main()