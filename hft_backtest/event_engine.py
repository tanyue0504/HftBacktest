from abc import ABC, abstractmethod

from typing import Callable, Type, Optional
from collections import deque
from itertools import chain

import pyximport
pyximport.install()
from hft_backtest.event import Event

class EventEngine:
    """
    事件引擎
    负责接受事件并推送给注册的监听器
    监听器通过register方法注册
    事件通过put方法推送
    事件引擎会自动标注事件的时间戳和来源
    若事件已经有时间戳则更新引擎的时间戳为该时间戳
    事件的来源是事件引擎的内存地址
    监听器只严格监听注册的事件类型, 不含其父类或子类
    """

    def __init__(self):
        self.timestamp = 0
        self.senior_global_listeners: list[Callable[[Event], None]] = []
        self.junior_global_listeners: list[Callable[[Event], None]] = []
        self.listener_dict: dict[Type[Event], list[tuple[Callable[[Event], None], bool]]] = {}
        self._queue: deque[Event] = deque()
        self._dispatching: bool = False
        self._current_listener: Optional[Callable[[Event], None]] = None
        self._id: int = id(self)  # 缓存引擎id，避免每次put计算

    def register(
        self,
        event_type: Type[Event],
        listener: Callable[[Event], None],
        ignore_self: bool = True,
    ):
        assert issubclass(event_type, Event)
        assert not self._dispatching
        if event_type not in self.listener_dict:
            self.listener_dict[event_type] = []
        lst = self.listener_dict[event_type]
        # 重复注册属于错误，不允许通过重复注册修改 ignore_self
        assert listener not in [l[0] for l in lst]
        lst.append((listener, ignore_self))

    def global_register(
        self,
        listener: Callable[[Event], None],
        ignore_self: bool = False,
        is_senior: bool = False,
    ):
        """注册全局监听器，监听所有事件类型"""
        assert not self._dispatching
        # 重复注册属于错误，不允许通过重复注册修改 ignore_self
        if is_senior:
            lst = self.senior_global_listeners
        else:
            lst = self.junior_global_listeners
        assert listener not in [l[0] for l in lst]
        lst.append((listener, ignore_self))

    def put(self, event: Event):
        assert isinstance(event, Event)
        # 标注来源
        if event.source == 0:
            event.source = self._id
        # 自动标注时间戳或更新引擎时间戳
        ts = event.timestamp
        if ts <= 0:
            event.timestamp = self.timestamp
        elif ts > self.timestamp:
            self.timestamp = ts
        # 覆盖 producer（None=外部，非None=当前回调监听器）
        event.producer = id(self._current_listener) if self._current_listener is not None else 0
        # 入队，统一顺序派发
        self._queue.append(event)
        if not self._dispatching:
            self._drain()

    def _drain(self):
        # _dispatching和_current_listener不采用try-finally以提升性能
        self._dispatching = True
        event_queue = self._queue
        listener_dict = self.listener_dict
        while event_queue:
            event = event_queue.popleft()
            senior_global_lst = self.senior_global_listeners
            junior_global_lst = self.junior_global_listeners
            # 已经禁止派发期修改监听器集合，因此不拷贝
            lst_local = listener_dict.get(type(event)) or ()
            # 已经禁止派发期修改监听器集合，因此不拷贝
            for listener, ignore_self in chain(senior_global_lst, lst_local, junior_global_lst):
                if ignore_self and event.producer == id(listener):
                    continue
                self._current_listener = id(listener)
                listener(event)
                self._current_listener = 0
        self._dispatching = False

class Component(ABC):
    """
    组件抽象基类
    
    添加组件的生命周期管理接口
    init阶段只传递配置参数
    组件需要在start方法中绑定事件引擎
    组件需要在stop方法中释放资源
    """

    @abstractmethod
    def start(self, engine: EventEngine):
        pass

    @abstractmethod
    def stop(self):
        pass

if __name__ == "__main__":
    # 简单测试事件引擎
    engine = EventEngine()

    class TestEvent(Event):
        pass

    def listener_a(event: Event):
        print(f"Listener A received: {event}")

    def listener_b(event: Event):
        print(f"Listener B received: {event}")
        # 在监听器中产生新事件
        new_event = TestEvent(timestamp=event.timestamp + 1)
        engine.put(new_event)

    def global_listener(event: Event):
        print(f"Global Listener received: {event}")

    engine.register(TestEvent, listener_a)
    engine.register(TestEvent, listener_b)
    # engine.register(TestEvent, listener_b, ignore_self=False)
    # engine.global_register(global_listener)

    # 推送初始事件
    initial_event = TestEvent(timestamp=1)
    engine.put(initial_event)