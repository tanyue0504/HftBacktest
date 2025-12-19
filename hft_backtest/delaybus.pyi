from typing import Union
from hft_backtest.event import Event
from hft_backtest.event_engine import EventEngine, Component

class LatencyModel:
    """
    延迟模型基类。
    用于计算每个事件的传输延迟。
    """
    def get_delay(self, event: Event) -> int: ...

class FixedDelayModel(LatencyModel):
    """
    固定延迟模型。
    所有事件的延迟都是固定的常数。
    """
    def __init__(self, delay: int) -> None: ...
    def get_delay(self, event: Event) -> int: ...

class DelayBus(Component):
    """
    高性能延迟总线组件。
    使用最小堆维护事件队列，模拟网络传输延迟。
    """
    def __init__(
        self,
        target_engine: EventEngine,
        delay_model: LatencyModel
    ) -> None: ...

    def start(self, engine: EventEngine) -> None:
        """
        启动组件，注册到源引擎并开始监听事件。
        """
        ...

    def stop(self) -> None: ...

    def on_event(self, event: Event) -> None:
        """
        事件回调函数。计算延迟并将事件放入内部堆队列。
        """
        ...

    def process_until(self, timestamp: int) -> None:
        """
        处理所有触发时间 <= 指定时间戳的事件，并推送到目标引擎。
        """
        ...

    @property
    def next_timestamp(self) -> Union[int, float]:
        """
        获取队列中最早待处理事件的触发时间。
        如果队列为空，返回 float('inf')。
        """
        ...