from event_engine import Event
from abc import ABC, abstractmethod

class Data(Event):
    """
    数据事件类
    timestamp: 数据时间戳 (int)
    data: 数据内容 (pd.DataFrame或其他格式)
    name: 数据源名称 (str)
    """
    
    def __init__(
        self,
        timestamp:int,
        data,
        name:str
    ):
        super().__init__(timestamp=timestamp)
        self.data = data
        self.name = name

class Dataset(ABC):
    """
    数据集抽象基类
    __iter__方法需要被子类实现
    每次迭代返回Data对象
    """

    def __init__(self, name:str):
        self.name = name
    
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
    """
    
    def __init__(self, *datasets: Dataset, name: str = "merged"):
        assert all([isinstance(ds, Dataset) for ds in datasets])
        super().__init__(name)
        self.datasets = datasets
        self.iterators = [iter(ds) for ds in datasets]
        self.latest_data = [next(it, None) for it in self.iterators]
    
    def __iter__(self):
        while any(self.latest_data):
            # 选择 (timestamp, index) 最小者，实现时间优先、索引次优先
            idx, d = min(
                ((i, d) for i, d in enumerate(self.latest_data) if d is not None),
                key=lambda t: (t[1].timestamp, t[0])
            )
            # 直接转发原始 Data
            yield d
            # 推进该数据源
            self.latest_data[idx] = next(self.iterators[idx], None)