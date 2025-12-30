# cython: language_level=3

cdef class Event:
    # 核心字段 (使用 C 类型 long long)
    cdef public long long timestamp
    cdef public unsigned long source
    cdef public unsigned long producer

    cpdef Event derive(self)