from typing import Type
from hft_backtest.event_engine import Event
from abc import ABC, abstractmethod
import heapq
from pyarrow import parquet as pq
import pandas as pd

class Data(Event):
    """
    数据事件类
    timestamp: 数据时间戳 (int)
    data: 数据内容 (pd.DataFrame或其他格式)
    name: 数据源名称 (str)
    """
    __slots__ = (
        "data",
        "name",
    )
    
    def __init__(
        self,
        timestamp:int,
        name:str,
        data,
    ):
        super().__init__(timestamp=timestamp)
        self.data = data
        self.name = name

    def __repr__(self) -> str:
        return f"Data(name={self.name}, timestamp={self.timestamp})"

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

class MergedDataset(Dataset):
    """
    合并多个数据源的数据集类，按照时间顺序迭代
    每次迭代返回一个“原始”的 Data（直接来自某个数据源）：
      - 在所有当前可用数据中选择 timestamp 最小的 Data
      - 若存在相同最小时间戳，则按传入顺序选择靠前的数据源

    性能优化（偏置归并）：
      - 维护一个“当前胜者”（最近一次被选中的数据源）
      - 其它数据源放入最小堆，按 (timestamp, index) 比较
      - 若当前胜者下一个元素仍不大于堆顶，仅 O(1) 比较即可继续输出
      - 当需要切换数据源时才进行堆操作，单步 O(log k)
    """
    
    def __init__(self, *datasets: Dataset, name: str = "merged"):
        assert all([isinstance(ds, Dataset) for ds in datasets])
        super().__init__(name)
        self.datasets = datasets
        self.iterators = [iter(ds) for ds in datasets]

        # 初始化：取各数据源的首元素，选出初始胜者，其余入堆
        heads = [next(it, None) for it in self.iterators]
        available = [(i, d) for i, d in enumerate(heads) if d is not None]
        if available:
            self._cur_idx, self._cur_data = min(
                available,
                key=lambda t: (t[1].timestamp, t[0])
            )
            # 堆中仅保存“非当前胜者”的候选项：(timestamp, index, data)
            self._heap = [(d.timestamp, i, d) for i, d in available if i != self._cur_idx]
            heapq.heapify(self._heap)
        else:
            self._cur_idx = None
            self._cur_data = None
            self._heap = []

    def __iter__(self):
        if self._cur_data is None: return

        heap = self._heap
        iters = self.iterators
        cur_idx, cur_data = self._cur_idx, self._cur_data

        while True:
            yield cur_data

            # 推进当前胜者迭代器
            nxt = next(iters[cur_idx], None)

            if nxt is None:  # 当前数据源耗尽
                if not heap: 
                    self._cur_data = None  # 标记结束
                    break
                _, cur_idx, cur_data = heapq.heappop(heap)
                continue

            # 快路径：仅比较时间戳
            if not heap or nxt.timestamp <= heap[0][0]:
                cur_data = nxt
                continue

            # 慢路径：切换数据源
            _, new_idx, new_data = heapq.heapreplace(
                heap, (nxt.timestamp, cur_idx, nxt)
            )
            cur_idx, cur_data = new_idx, new_data

class ParquetDataset(Dataset):
    """
    parquet格式df数据集
    要求无索引，自带类型，包含时间列
    分批读取，逐行推送
    """

    def __init__(
        self,
        path: str,
        event_type: Type[Data],
        columns: list, # 按这个顺序读取列传递给event_type
        chunksize: int = 10**6,
        tag_dict: dict = None, # 会覆盖dataframe中的同名列
    ):
        self.path = path
        self.event_type = event_type
        self.columns = columns
        self.chunksize = chunksize
        self.tag_dict = tag_dict

    def __iter__(self):
        pq_file = pq.ParquetFile(self.path)
        for batch in pq_file.iter_batches(batch_size=self.chunksize):
            df = batch.to_pandas()
            if self.tag_dict is not None:
                for k, v in self.tag_dict.items():
                    df[k] = v
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
        name:str,
        path: str,
        timecol: str,
        event_type: Type[Data],
        columns: list,  # 按这个顺序读取列传递给event_type
        chunksize: int = 10**6,
        tag_dict: dict = None, # 会覆盖dataframe中的同名列
        compression: str = None,
    
    ):
        super().__init__(name)
        self.path = path
        self.timecol = timecol
        self.chunksize = chunksize
        assert issubclass(event_type, Data)
        self.event_type = event_type
        self.columns = columns
        self.compression = compression
        self.tag_dict = tag_dict

    def __iter__(self):
        for df in pd.read_csv(self.path, chunksize=self.chunksize, compression=self.compression):
            if self.tag_dict is not None:
                for k, v in self.tag_dict.items():
                    df[k] = v
            for row in zip(*[df[col].values for col in self.columns]):
                yield self.event_type(*row)