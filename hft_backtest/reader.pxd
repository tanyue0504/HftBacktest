# hft_backtest/reader.pxd
# cython: language_level=3
from hft_backtest.event cimport Event

# 基础读取器接口 (C类型)
cdef class DataReader:
    # 纯 C 接口，极速调用
    cdef Event fetch_next(self)

# 包装器：把 Python 的 Dataset 包装成 C 的 DataReader
cdef class PyDatasetWrapper(DataReader):
    cdef object _iter