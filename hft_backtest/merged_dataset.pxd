# hft_backtest/merged_dataset.pxd
# cython: language_level=3
from libcpp.vector cimport vector
from cpython.ref cimport PyObject
from hft_backtest.event cimport Event
# 引入我们刚才定义的 Reader
from hft_backtest.reader cimport DataReader

# 堆里的元素结构
cdef struct MergeItem:
    long timestamp
    int source_idx
    PyObject* event  # 堆里还是得存裸指针，这是没办法的，但我们会小心处理

cdef class MergedDataset(DataReader):
    # 【改动】使用 Python list 存储数据源，绝对安全，自动 GC
    cdef list _sources 
    
    # 堆结构
    cdef vector[MergeItem] _heap
    
    # 当前状态
    cdef Event _cur_event
    cdef int _cur_idx
    cdef bint _initialized
    
    # 内部 C 方法
    cdef void _push(self, long timestamp, int source_idx, Event event)
    cdef void _sift_up(self, size_t idx)
    cdef void _sift_down(self, size_t idx)
    cdef bint _less(self, size_t i, size_t j)
    
    cdef void _init_heap(self)
    cdef void _pop_heap_to_current(self)
    
    # 覆盖基类方法
    cdef Event fetch_next(self)