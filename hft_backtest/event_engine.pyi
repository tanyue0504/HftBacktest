from typing import Callable, Type, List, Dict, Optional, Any, Union
from collections import deque
from hft_backtest.event import Event

# 定义监听器类型别名，方便阅读
Listener = Callable[[Event], None]

class Component:
    """
    组件基类 (Cython cdef class 映射)
    """
    def start(self, engine: "EventEngine") -> None: ...
    def stop(self) -> None: ...

class EventEngine:
    """
    高性能事件引擎 (Cython 版)
    负责接受事件并推送给注册的监听器。
    """
    
    # --- 公开属性 (对应 cdef public) ---
    timestamp: int
    _id: int
    
    # --- 内部属性 (对应 cdef 成员，通常 IDE 不需要提示，但为了完整性可以列出) ---
    # senior_global_listeners: List[tuple[Listener, bool]]
    # junior_global_listeners: List[tuple[Listener, bool]]
    # listener_dict: Dict[Type[Event], List[tuple[Listener, bool]]]
    # _queue: deque[Event]
    # _dispatching: bool
    # _current_listener_id: int

    def __init__(self) -> None: ...

    def register(
        self,
        event_type: Type[Event],
        listener: Listener,
        ignore_self: bool = True,
    ) -> None:
        """
        注册特定类型的事件监听器。
        
        Args:
            event_type: 要监听的 Event 子类
            listener: 回调函数，签名需为 (event: Event) -> None
            ignore_self: 是否忽略自己（当前组件）产生的事件，默认为 True
        """
        ...

    def global_register(
        self,
        listener: Listener,
        ignore_self: bool = False,
        is_senior: bool = False,
    ) -> None:
        """
        注册全局监听器，监听所有类型的事件。
        
        Args:
            listener: 回调函数
            ignore_self: 是否忽略自己产生的事件
            is_senior: 是否为高优先级（在普通监听器之前执行），默认为 False (低优先级，最后执行)
        """
        ...

    def put(self, event: Event) -> None:
        """
        推送事件到队列。
        如果当前没有在分发事件，会立即触发 _drain() 处理队列。
        
        Args:
            event: Event 对象实例
        """
        ...

    # _drain 和 _call_listener 是 cdef 方法，对 Python 不可见，
    # 因此不需要在 pyi 中暴露，除非你是用 cpdef 定义的。
    # 如果你在测试中需要调用 _drain (虽然它现在是 cdef void)，
    # 只有把它改成 cpdef void _drain(self) 才需要在 pyi 里写。
    # 目前保持不可见即可。