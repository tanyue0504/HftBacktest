# hft_backtest/okx/reader.pxd
# cython: language_level=3

from hft_backtest.reader cimport DataReader

# OKXTrades 专用 Batch 读取器
cdef class OKXTradesArrayReader(DataReader):
    # 迭代器状态
    cdef object batch_iterator
    cdef object current_df # 保持引用，防止 MemoryView 失效
    
    # 当前 Batch 的内存视图
    cdef long[:] created_times
    cdef object[:] instrument_names
    cdef long[:] trade_ids
    cdef double[:] prices
    cdef double[:] sizes
    cdef object[:] sides
    
    # 游标
    cdef Py_ssize_t idx
    cdef Py_ssize_t length
    
    # 内部方法
    cdef void load_next_batch(self)

# OKXBookticker 专用 Batch 读取器
cdef class OKXBooktickerArrayReader(DataReader):
    cdef object batch_iterator
    cdef object current_df
    
    cdef long[:] timestamps
    cdef object[:] symbols
    cdef long[:] local_timestamps
    
    # 指针数组，存储100列深度数据
    cdef double* data_ptrs[100]
    # 保持对 numpy 对象的引用
    cdef object _keep_alive_refs
    
    cdef Py_ssize_t idx
    cdef Py_ssize_t length
    
    cdef void load_next_batch(self)