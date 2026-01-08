# hft_backtest/factor.pyi

from hft_backtest.event import Event

class FactorSignal(Event):
    symbol: str
    value: float
    
    def __init__(self, symbol: str, value: float) -> None: ...
    def derive(self) -> Event: ...