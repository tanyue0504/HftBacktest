# hft_backtest/factor.pyi

from hft_backtest.event import Event

class FactorSignal(Event):
    name: str
    symbol: str
    value: float
    
    def __init__(self, symbol: str, value: float, name: str) -> None: ...
    def derive(self) -> Event: ...