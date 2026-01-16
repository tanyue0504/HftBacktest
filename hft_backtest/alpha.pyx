# hft_backtest/alpha.pyx
# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False

from hft_backtest.event cimport Event


cdef class AlphaSignal(Event):
    """Alpha prediction event.

    Emitted by an alpha/factor fusion component, representing the estimated
    future short-term return for a symbol over a given horizon.

    - value: expected return (unit: return, e.g. 0.001 = 10 bps)
    - horizon: prediction window length (unit: same as Event.timestamp, usually us)
    """

    def __init__(self, str symbol, double value, str name, long long horizon):
        # timestamp defaults to 0; EventEngine/DelayBus will assign/override on put.
        super().__init__(0)
        self.name = name
        self.symbol = symbol
        self.horizon = horizon
        self.value = value

    def __repr__(self):
        return (
            f"AlphaSignal(name='{self.name}', symbol='{self.symbol}', "
            f"value={self.value:.6f}, horizon={self.horizon}, ts={self.timestamp})"
        )

    cpdef Event derive(self):
        cdef AlphaSignal evt = AlphaSignal.__new__(AlphaSignal)
        evt.timestamp = 0
        evt.source = 0
        evt.producer = 0
        evt.name = self.name
        evt.symbol = self.symbol
        evt.horizon = self.horizon
        evt.value = self.value
        return evt
