from typing import Callable, Type, Optional
from collections import deque

class Event:
    """
    任何一个事件都需要包含
    1. 事件发生事件
    2. 事件来源
    事件类型可以通过继承来实现
    事件来源是事件首次被推入事件引擎时由事件引擎标注
    标注的内容是事件引擎的内存地址
    """

    # 极致的性能和内存优化
    __slots__ = ("timestamp", "source", "producer")

    def __init__(
        self,
        timestamp: Optional[int] = None,
        source: Optional[int] = None,
        producer: Optional[Callable] = None,  # 监听器对象；None 表示外部产生
    ):
        self.timestamp = timestamp
        self.source = source
        self.producer = producer

    def __repr__(self) -> str:
        return f"Event(timestamp={self.timestamp}, source={self.source})"

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
    # 不要使用__slots__, 否则无法动态注入接口
    # 极致的性能和内存优化
    # __slots__ = (
    #     "timestamp",
    #     "listener_dict",
    #     "_queue",
    #     "_dispatching",
    #     "_current_listener",
    #     "_id",
    # )

    def __init__(self):
        self.timestamp = 0
        self.listener_dict: dict[Type[Event], list[tuple[Callable[[Event], None], bool]]] = {}
        self._queue: deque[Event] = deque()
        self._dispatching: bool = False
        self._current_listener: Optional[Callable[[Event], None]] = None
        self._id: int = id(self)  # 缓存引擎id，避免每次put计算

    def register(
        self,
        event_type: Type[Event],
        listener: Callable[[Event], None],
        ignore_self: bool = False,
    ):
        assert issubclass(event_type, Event)
        assert not self._dispatching
        lst = self.listener_dict.get(event_type)
        if lst is None:
            self.listener_dict[event_type] = [(listener, bool(ignore_self))]
            return
        # 重复注册属于错误，不允许通过重复注册修改 ignore_self
        assert listener not in [l[0] for l in lst]
        lst.append((listener, bool(ignore_self)))

    def put(self, event: Event):
        assert isinstance(event, Event)
        # 标注来源
        if event.source is None:
            event.source = self._id
        # 自动标注时间戳或更新引擎时间戳，局部变量提升性能
        ts = event.timestamp
        if ts is None:
            event.timestamp = self.timestamp
        elif ts > self.timestamp:
            self.timestamp = ts
        # 覆盖 producer（None=外部，非None=当前回调监听器）
        event.producer = self._current_listener
        # 入队，统一顺序派发
        self._queue.append(event)
        if not self._dispatching:
            self._drain()

    def _drain(self):
        # _dispatching和_current_listener不采用try-finally以提升性能
        self._dispatching = True
        q = self._queue
        listener_dict = self.listener_dict
        while q:
            ev = q.popleft()
            lst = listener_dict.get(type(ev))
            if not lst:
                continue
            # 已经禁止派发期修改监听器集合，因此不拷贝
            for listener, ignore_self in lst:
                if ignore_self and ev.producer is listener:
                    continue
                self._current_listener = listener
                listener(ev)
                # 回调完成后清空当前生产者
                self._current_listener = None
        self._dispatching = False