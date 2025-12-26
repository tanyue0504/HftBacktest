from typing import Iterator, Any
from hft_backtest.event import Event
from hft_backtest.dataset import Dataset

class MergedDataset(Iterator[Event]):
    """
    高性能多路归并数据集 (Cython 版)。
    
    接收多个已经按时间顺序排列的数据集 (Dataset)，
    使用最小堆算法将它们合并为一个按时间顺序排列的事件流。
    """
    
    def __init__(self, datasets: list[Dataset]) -> None:
        """
        Args:
            *datasets: 变长参数，每个参数都应是一个实现了 __iter__ 并产生 Event 的 Dataset 对象。
        """
        ...
        
    def __iter__(self) -> "MergedDataset": ...
    
    def __next__(self) -> Event:
        """
        返回下一个时间戳最小的 Event。
        如果所有数据源都耗尽，抛出 StopIteration。
        """
        ...