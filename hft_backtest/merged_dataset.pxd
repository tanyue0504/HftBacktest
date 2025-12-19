# cython: language_level=3
from libcpp.vector cimport vector
from cpython.ref cimport PyObject
from hft_backtest.event cimport Event

# 堆中的元素结构体
cdef struct MergeItem:
    long timestamp
    int source_idx
    PyObject* event 

cdef class MergedDataset:
    # 成员变量
    cdef list _iters           
    cdef vector[MergeItem] _heap
    
    # 当前胜者缓存
    cdef Event _cur_event
    cdef int _cur_idx
    cdef object _cur_iter      
    
    # 状态标记
    cdef bint _initialized
    
    # --- C 内部方法声明 (必须与 pyx 实现一致) ---
    
    # 堆操作基础
    cdef void _push(self, long timestamp, int source_idx, Event event)
    cdef void _sift_up(self, size_t idx)
    cdef void _sift_down(self, size_t idx)
    cdef bint _less(self, size_t i, size_t j)  # [新增] 声明比较函数
    
    # 业务逻辑
    cdef void _init_heap(self)                 # [新增] 声明初始化
    cdef void _pop_heap_to_current(self)       # [新增] 声明弹出逻辑
    
    # [删除] _fetch_next_from_source (pyx 中未使用，删掉)