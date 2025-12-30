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
    分批读取
    """

    def __init__(
        self,
        path: str,
        event_type: Type[Event] = None, # batch 模式下可选
        columns: list = None, # batch 模式下可选，如果为 None 则由 Reader 自己挑
        chunksize: int = 10**6,
        tag_dict: dict = None, # 会覆盖dataframe中的同名列
        transform: callable = None,
        mode: str = 'event' # 【新增】'event' 或 'batch', 默认 'event'
    ):
        self.path = path
        self.event_type = event_type
        self.columns = columns
        self.chunksize = chunksize
        self.tag_dict = tag_dict
        self.transform = transform
        self.mode = mode

    def __iter__(self):
        pq_file = pq.ParquetFile(self.path)
        for batch in pq_file.iter_batches(batch_size=self.chunksize):
            df = batch.to_pandas()
            
            # 1. 预处理 (Tag & Transform)
            if self.tag_dict is not None:
                for k, v in self.tag_dict.items():
                    df[k] = v
            if self.transform is not None:
                df = self.transform(df)
            
            # 2. 分发逻辑
            if self.mode == 'batch':
                # 【新路径】直接把“原材料”交出去，不做任何拆解
                yield df
            else:
                # 【旧路径】逐个生成 Event 对象
                if self.columns is None or self.event_type is None:
                    raise ValueError("In 'event' mode, 'columns' and 'event_type' must be provided.")
                cols = [df[col].values for col in self.columns]
                yield from map(self.event_type, *cols)

class CsvDataset(Dataset):
    """
    CSV格式df数据集
    """
    def __init__(
        self,
        path: str,
        event_type: Type[Event] = None,
        columns: list = None,
        chunksize: int = 10**6,
        tag_dict: dict = None, 
        compression: str = None,
        transform: callable = None,
        mode: str = 'event' # 【新增】'event' 或 'batch', 默认 'event'
    ):
        self.path = path
        self.chunksize = chunksize
        self.event_type = event_type
        self.columns = columns
        self.compression = compression
        self.tag_dict = tag_dict
        self.transform = transform
        self.mode = mode

    def __iter__(self):
        for df in pd.read_csv(self.path, chunksize=self.chunksize, compression=self.compression):
            if self.tag_dict is not None:
                for k, v in self.tag_dict.items():
                    df[k] = v
            if self.transform is not None:
                df = self.transform(df)
            
            if self.mode == 'batch':
                yield df
            else:
                if self.columns is None or self.event_type is None:
                    raise ValueError("In 'event' mode, 'columns' and 'event_type' must be provided.")
                for row in zip(*[df[col].values for col in self.columns]):
                    yield self.event_type(*row)