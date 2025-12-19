# cython: language_level=3

cdef class Event:
    # 核心字段 (使用 C 类型 long long)
    cdef public long long timestamp
    cdef public unsigned long source
    cdef public unsigned long producer

    # 声明 C 方法 (必须在此声明，否则 .pyx 无法实现)
    cdef Event _c_clone(self)
    cpdef Event derive(self)