from typing import List, Optional, Union
from .dataset import Dataset
from .reader import DataReader
from .delaybus import DelayBus
from .event_engine import EventEngine, Component

class BacktestEngine:
    """
    全 Cython 版回测引擎
    """
    # cdef public 定义的属性在 Python 中是可见的
    server_engine: EventEngine
    client_engine: EventEngine
    
    server_components: List[Component]
    client_components: List[Component]
    
    dataset: DataReader
    
    server2client_bus: DelayBus
    client2server_bus: DelayBus

    def __init__(
        self, 
        dataset: Union[Dataset, DataReader], 
        server2client_delaybus: DelayBus, 
        client2server_delaybus: DelayBus, 
        timer_interval: Optional[int] = ...
    ) -> None: ...

    def add_component(self, component: Component, is_server: bool) -> None: ...
    
    def run(self) -> None: ...