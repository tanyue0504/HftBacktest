# cython: language_level=3
import copy

cdef class Event:
    def __init__(self, long long timestamp):
        self.timestamp = timestamp
        self.source = 0
        self.producer = 0

    def __lt__(self, Event other):
        return self.timestamp < other.timestamp

    # 暴露给 Python 和 Cython 的 derive 接口
    cpdef Event derive(self):
        """
        Clones the event and resets header info.
        WARNING: This uses raw memory copy. Python-level attributes (in __dict__) 
        of subclasses are NOT safely handled.
        """
        # 1. 调用通用拷贝
        cdef Event new_event = copy.copy(self)
        
        # 2. 重置 Event 头部信息
        new_event.timestamp = 0
        new_event.source = 0
        new_event.producer = 0
        
        return new_event