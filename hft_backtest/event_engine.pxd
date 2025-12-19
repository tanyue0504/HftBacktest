# cython: language_level=3
from hft_backtest.event cimport Event

cdef class EventEngine:
    # 只声明 cdef/cpdef 的属性和方法，供其他模块调用
    cdef public long timestamp
    cdef public long _id
    cdef list senior_global_listeners
    cdef list junior_global_listeners
    cdef dict listener_dict
    cdef object _queue
    cdef bint _dispatching
    cdef unsigned long _current_listener_id

    cpdef register(self, object event_type, object listener, bint ignore_self=*)
    cpdef global_register(self, object listener, bint ignore_self=*, bint is_senior=*)
    cpdef put(self, Event event)
    cdef void _drain(self)
    cdef void _call_listener(self, object listener, bint ignore_self, Event event)

cdef class Component:
    cpdef start(self, EventEngine engine)
    cpdef stop(self)