# hft_backtest/reader.pyx
# cython: language_level=3

from hft_backtest.event cimport Event

cdef class DataReader:
    """所有 Cython 数据读取器的基类"""
    cdef Event fetch_next(self):
        # 基类默认抛出异常，子类必须实现
        raise NotImplementedError("Subclasses must implement fetch_next")

    def __iter__(self):
        return self

    def __next__(self):
        # 兼容 Python 层的 for 循环调用
        cdef Event evt = self.fetch_next()
        if evt is None:
            raise StopIteration
        return evt

cdef class PyDatasetWrapper(DataReader):
    """
    适配器：将普通的 Python Dataset（如 ParquetDataset）
    伪装成高性能的 DataReader
    """
    def __init__(self, py_dataset):
        self._iter = iter(py_dataset)

    cdef Event fetch_next(self):
        try:
            # 这里虽然会回调 Python，但这是兼容性必须的代价
            # 只有最底层读取会有这个开销，合并层不会有
            return <Event>next(self._iter)
        except StopIteration:
            return None
        except Exception as e:
            raise e