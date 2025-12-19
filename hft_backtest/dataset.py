from typing import Type
from hft_backtest import Event
from abc import ABC, abstractmethod
import heapq
from pyarrow import parquet as pq
import pandas as pd

class Dataset(ABC):
    """
    数据集抽象基类
    __iter__方法需要被子类实现
    每次迭代返回Data对象
    """
    
    @abstractmethod
    def __iter__(self):
        """return Data"""
        pass

class ParquetDataset(Dataset):
    """
    parquet格式df数据集
    要求无索引，自带类型，包含时间列
    分批读取，逐行推送
    """

    def __init__(
        self,
        path: str,
        event_type: Type[Event],
        columns: list, # 按这个顺序读取列传递给event_type
        chunksize: int = 10**6,
        tag_dict: dict = None, # 会覆盖dataframe中的同名列
        transform: callable = None,
    ):
        self.path = path
        self.event_type = event_type
        self.columns = columns
        self.chunksize = chunksize
        self.tag_dict = tag_dict
        self.transform = transform

    def __iter__(self):
        pq_file = pq.ParquetFile(self.path)
        for batch in pq_file.iter_batches(batch_size=self.chunksize):
            df = batch.to_pandas()
            if self.tag_dict is not None:
                for k, v in self.tag_dict.items():
                    df[k] = v
            if self.transform is not None:
                df = self.transform(df)
            cols = [df[col].values for col in self.columns]
            yield from map(self.event_type, *cols)

class CsvDataset(Dataset):
    """
    CSV格式df数据集
    要求无索引，包含时间列
    分批读取，逐行推送
    """

    def __init__(
        self,
        path: str,
        event_type: Type[Event],
        columns: list,  # 按这个顺序读取列传递给event_type
        chunksize: int = 10**6,
        tag_dict: dict = None, # 会覆盖dataframe中的同名列
        compression: str = None,
        transform: callable = None,
    ):
        self.path = path
        self.chunksize = chunksize
        self.event_type = event_type
        self.columns = columns
        self.compression = compression
        self.tag_dict = tag_dict
        self.transform = transform

    def __iter__(self):
        for df in pd.read_csv(self.path, chunksize=self.chunksize, compression=self.compression):
            if self.tag_dict is not None:
                for k, v in self.tag_dict.items():
                    df[k] = v
            if self.transform is not None:
                df = self.transform(df)
            for row in zip(*[df[col].values for col in self.columns]):
                yield self.event_type(*row)