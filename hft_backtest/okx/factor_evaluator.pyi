from __future__ import annotations

from typing import Any

from hft_backtest.event_engine import EventEngine, Component
from hft_backtest.factor import FactorSignal
from hft_backtest.okx.event import OKXBookticker, OKXTrades


class FactorEvaluator(Component):
    """Factor evaluation component for OKX.

    Listens to market data (bookticker/trades) and `FactorSignal`, computes
    evaluation statistics (distribution, forward-return relationship, hit rate,
    delay stats), and can print a detailed report to console.

        Notes
        - Forward return definition: $r = (p_t - p_0) / p_0$ where $p_0$ is the
            reference mid-price at factor time, and $p_t$ is the first mid-price
            observed at timestamp >= factor_ts + horizon.
        - Autocorr proxy: computes lag-1 autocorrelation of factor values per symbol
            (`x_autocorr1`). Lower values typically imply higher turnover.
    """

    event_engine: Any
    horizon: int
    max_store: int
    enable_store: bool

    def __init__(
        self,
        horizon: int = 0,
        enable_store: bool = True,
        max_store: int = 20000,
    ) -> None: ...

    def start(self, engine: EventEngine) -> None: ...
    def stop(self) -> None: ...

    def on_bookticker(self, event: OKXBookticker) -> None: ...
    def on_trades(self, event: OKXTrades) -> None: ...
    def on_factor(self, signal: FactorSignal) -> None: ...

    def reset(self) -> None: ...
    def symbols(self) -> list[str]: ...

    def get_symbol_stats(self, symbol: str) -> dict[str, Any]: ...

    def get_stats(self) -> dict[str, Any]:
        """Get overall stats including per-symbol aggregation."""
        ...

    def format_report(self, symbol: str | None = None, max_symbols: int = 20) -> str: ...
    def print_report(self, symbol: str | None = None, max_symbols: int = 20) -> None: ...
