# hft_backtest/okx/reader.pxd
# cython: language_level=3

from hft_backtest.reader cimport DataReader

# OKXTrades 专用数组读取器
cdef class OKXTradesArrayReader(DataReader):
    cdef long[:] created_times
    cdef object[:] instrument_names
    cdef long[:] trade_ids
    cdef double[:] prices
    cdef double[:] sizes
    cdef object[:] sides
    
    cdef Py_ssize_t idx
    cdef Py_ssize_t length

# OKXBookticker 专用数组读取器
cdef class OKXBooktickerArrayReader(DataReader):
    cdef long[:] timestamps
    cdef object[:] symbols
    cdef long[:] local_timestamps
    
    # 指针数组，存储100列深度数据
    cdef double* data_ptrs[100]
    # 保持对 numpy 对象的引用防止 GC
    cdef object _keep_alive_refs
    
    cdef Py_ssize_t idx
    cdef Py_ssize_t length