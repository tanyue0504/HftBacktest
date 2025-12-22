# cython: language_level=3
from libcpp.vector cimport vector
from cpython.ref cimport PyObject
from hft_backtest.event cimport Event
# 这一行之前报错是因为没有 event_engine.pxd，现在有了就没问题了
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
    
    # --- 必须声明所有 cdef 方法 ---
    cdef void _push(self, long trigger_time, Event event)
    cdef void _pop_and_process(self)
    
    # 漏掉的两个方法补上：
    cdef void _sift_up(self, size_t idx)
    cdef void _sift_down(self, size_t idx)
    
    # cpdef 方法在 .pxd 里声明（可选，但推荐声明）
    cpdef on_event(self, Event event)
    cpdef process_until(self, long timestamp)

    cpdef set_target_engine(self, EventEngine engine)