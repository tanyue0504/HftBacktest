# hft_backtest/delaybus.pxd
# cython: language_level=3
from libcpp.vector cimport vector
from cpython.ref cimport PyObject
from hft_backtest.event cimport Event
from hft_backtest.event_engine cimport EventEngine, Component

# 16字节对齐的紧凑结构体
cdef struct BusItem:
    long trigger_time
    PyObject* event

cdef class LatencyModel:
    cpdef long get_delay(self, Event event)

cdef class FixedDelayModel(LatencyModel):
    cdef long delay

cdef class DelayBus(Component):
    cdef public EventEngine target_engine
    cdef LatencyModel model
    
    cdef unsigned long _source_id
    
    # 核心数据结构：最小堆
    cdef vector[BusItem] _queue
    
    # --- 内部方法 ---
    cdef void _push(self, long trigger_time, Event event)
    cdef void _pop_and_process(self)
    cdef void _sift_up(self, size_t idx)
    cdef void _sift_down(self, size_t idx)
    
    # --- 【新增】解耦接口 (C-API) ---
    # 返回队列是否为空
    cdef bint is_empty(self)
    # 返回堆顶触发时间，如果为空则返回 LLONG_MAX
    cdef long peek_trigger_time(self)
    
    # --- cpdef 方法 ---
    cpdef on_event(self, Event event)
    cpdef process_until(self, long timestamp)
    cpdef set_target_engine(self, EventEngine engine)