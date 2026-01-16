from hft_backtest.event import Event


class AlphaSignal(Event):
    name: str
    symbol: str
    horizon: int
    value: float

    def __init__(self, symbol: str, value: float, name: str, horizon: int) -> None: ...
    def derive(self) -> Event: ...
