# hft_backtest/event_engine.pyx
# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False

from collections import deque
from hft_backtest.event cimport Event

# Component 需要被 Matcher 继承，定义为 cdef class 可以让子类也是 cdef class
cdef class Component:
    """组件基类"""
    cpdef start(self, EventEngine engine):
        pass

    cpdef stop(self):
        pass

cdef class EventEngine:
    """
    高性能事件引擎 (Cython 版)
    """
    # --- C 级别成员变量声明 ---
    cdef public long timestamp
    cdef public long _id
    
    # 监听器列表：存储 Python Callable 对象
    cdef list senior_global_listeners
    cdef list junior_global_listeners
    cdef dict listener_dict
    
    # 事件队列：使用 Python deque (Cython 对其有优化)
    cdef object _queue
    
    # 状态标志
    cdef bint _dispatching
    cdef unsigned long _current_listener_id  # 当前正在执行的回调
    
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
        :param event_type: Event 的子类
        :param listener: 回调函数
        :param ignore_self: 是否忽略自己产生的事件
        """
        if self._dispatching:
            raise RuntimeError("Cannot register listener during dispatching")
            
        if event_type not in self.listener_dict:
            self.listener_dict[event_type] = []
            
        cdef list lst = self.listener_dict[event_type]
        # 检查重复 (虽然会有 O(N) 开销，但注册通常只在初始化时发生)
        for l, _ in lst:
            if l == listener:
                raise ValueError("Listener already registered")
                
        lst.append((listener, ignore_self))

    cpdef global_register(self, object listener, bint ignore_self=False, bint is_senior=False):
        if self._dispatching:
            raise RuntimeError("Cannot register listener during dispatching")
            
        cdef list lst = self.senior_global_listeners if is_senior else self.junior_global_listeners
        
        if listener in lst: # 简单检查
             raise ValueError("Listener already registered")
             
        # 全局监听存储格式统一为 (listener, ignore_self)
        lst.append((listener, ignore_self))

    cpdef put(self, Event event):
        """
        推送事件。
        由于 Event 已经是 cdef class，这里访问属性极快。
        """
        # 1. 标注来源
        if event.source == 0:
            event.source = self._id
            
        # 2. 时间戳维护
        cdef long ts = event.timestamp
        if ts <= 0:
            event.timestamp = self.timestamp
        elif ts > self.timestamp:
            self.timestamp = ts
            
        # 3. 标注生产者
        event.producer = self._current_listener_id
            
        # 4. 入队
        self._queue.append(event)
        
        # 5. 触发处理
        if not self._dispatching:
            self._drain()

    cdef void _drain(self):
        """
        核心事件循环。
        使用 cdef void 减少调用开销，仅供内部 put 调用。
        """
        self._dispatching = True
        
        cdef object queue = self._queue
        cdef dict listener_dict = self.listener_dict
        cdef Event event
        cdef list handlers
        cdef object listener
        cdef bint ignore_self
        cdef long listener_id
        
        # 缓存列表引用以加速
        cdef list senior_lst = self.senior_global_listeners
        cdef list junior_lst = self.junior_global_listeners

        while queue:
            # 极速弹出
            event = queue.popleft()
            
            # 1. Senior Global Listeners
            # 展开循环比 itertools.chain 快
            for listener, ignore_self in senior_lst:
                self._call_listener(listener, ignore_self, event)

            # 2. Specific Listeners
            # type(event) 在 Cython 中稍微慢一点点，但对于动态事件分发无法避免
            handlers = listener_dict.get(type(event))
            if handlers is not None:
                for listener, ignore_self in handlers:
                    self._call_listener(listener, ignore_self, event)

            # 3. Junior Global Listeners
            for listener, ignore_self in junior_lst:
                self._call_listener(listener, ignore_self, event)
            
        self._dispatching = False

    cdef inline void _call_listener(self, object listener, bint ignore_self, Event event):
        """内联辅助函数，处理回调逻辑"""
        if ignore_self and event.producer == id(listener):
                return
        self._current_listener_id = id(listener)
        listener(event) # 执行回调 (回到 Python 世界)
        self._current_listener_id = 0