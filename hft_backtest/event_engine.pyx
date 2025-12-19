# hft_backtest/event_engine.pyx
# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False

from collections import deque
from hft_backtest.event cimport Event

# --- Component 类 ---
# 属性和方法已经在 .pxd 中声明，这里只写实现
# 如果没有特殊逻辑，其实 pass 也可以，但通常会有默认实现
cdef class Component:
    """组件基类"""
    cpdef start(self, EventEngine engine):
        pass

    cpdef stop(self):
        pass

# --- EventEngine 类 ---
cdef class EventEngine:
    """
    高性能事件引擎 (Cython 版)
    """
    # ❌ 这里的成员变量声明必须删除！
    # 因为它们已经在 .pxd 文件里声明过了。
    
    def __init__(self):
        self.timestamp = 0
        self.senior_global_listeners = []
        self.junior_global_listeners = []
        self.listener_dict = {}
        self._queue = deque()
        self._dispatching = False
        self._current_listener_id = 0
        self._id = id(self)

    cpdef register(self, object event_type, object listener, bint ignore_self=True):
        """
        注册监听器
        """
        if self._dispatching:
            raise RuntimeError("Cannot register listener during dispatching")
            
        if event_type not in self.listener_dict:
            self.listener_dict[event_type] = []
            
        cdef list lst = self.listener_dict[event_type]
        for l, _ in lst:
            if l == listener:
                raise ValueError("Listener already registered")
                
        lst.append((listener, ignore_self))

    cpdef global_register(self, object listener, bint ignore_self=False, bint is_senior=False):
        if self._dispatching:
            raise RuntimeError("Cannot register listener during dispatching")
            
        cdef list lst = self.senior_global_listeners if is_senior else self.junior_global_listeners
        
        if listener in lst:
             raise ValueError("Listener already registered")
             
        lst.append((listener, ignore_self))

    cpdef put(self, Event event):
        """
        推送事件。
        """
        if event.source == 0:
            event.source = self._id
            
        cdef long ts = event.timestamp
        if ts <= 0:
            event.timestamp = self.timestamp
        elif ts > self.timestamp:
            self.timestamp = ts
            
        if self._current_listener_id != 0:
            event.producer = self._current_listener_id
        else:
            event.producer = 0
            
        self._queue.append(event)
        
        if not self._dispatching:
            self._drain()

    cdef void _drain(self):
        """
        核心事件循环。
        """
        self._dispatching = True
        
        cdef object queue = self._queue
        cdef dict listener_dict = self.listener_dict
        cdef Event event
        cdef list handlers
        cdef list senior_lst = self.senior_global_listeners
        cdef list junior_lst = self.junior_global_listeners

        try:
            while queue:
                event = queue.popleft()
                
                # 1. Senior Global
                for listener, ignore_self in senior_lst:
                    self._call_listener(listener, ignore_self, event)

                # 2. Specific Listeners
                handlers = listener_dict.get(type(event))
                if handlers is not None:
                    for listener, ignore_self in handlers:
                        self._call_listener(listener, ignore_self, event)

                # 3. Junior Global
                for listener, ignore_self in junior_lst:
                    self._call_listener(listener, ignore_self, event)
                    
                self._current_listener_id = 0
                
        finally:
            self._dispatching = False
            self._current_listener_id = 0

    cdef inline void _call_listener(self, object listener, bint ignore_self, Event event):
        """内联辅助函数"""
        cdef unsigned long lid = id(listener)
        
        if ignore_self and event.producer == lid:
            return
            
        self._current_listener_id = lid
        listener(event)
        self._current_listener_id = 0