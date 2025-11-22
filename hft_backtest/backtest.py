from hft_backtest import Dataset, MergedDataset, Component, EventEngine, DelayBus

from itertools import chain

class BacktestEngine:
    """
    单事件引擎本质上是双事件引擎在delay=0时的特例
    """
    def __init__(
        self,
        datasets: list[Dataset],
        delay:int = 0, # unit: ms
    ):
        self.dataset = MergedDataset(*datasets)
        self.server_engine = EventEngine()
        self.client_engine = EventEngine()
        self.server_components: list[Component] = []
        self.client_components: list[Component] = []
        self.server2client_bus = DelayBus(
            self.server_engine,
            self.client_engine,
            delay
        )
        self.client2server_bus = DelayBus(
            self.client_engine,
            self.server_engine,
            delay
        )


    def add_component(self, component:Component, is_server: bool):
        if is_server:
            self.server_components.append(component)
        else:
            self.client_components.append(component)
        
    def run(self):
        with self:
            for data_event in self.dataset:
                self.server_engine.put(data_event, is_copy=False)

    def __enter__(self):
        for component in self.server_components:
            component.start(self.server_engine)
        for component in self.client_components:
            component.start(self.client_engine)
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        for component in chain(self.server_components, self.client_components):
            component.stop()
        return False