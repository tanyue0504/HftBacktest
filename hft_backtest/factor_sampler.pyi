from __future__ import annotations

from typing import Any, Iterable

from hft_backtest.event_engine import Component, EventEngine
from hft_backtest.factor import FactorSignal
from hft_backtest.timer import Timer


class FactorSampler(Component):
    """Core factor sampler.

    - Caches latest factor values per (symbol, factor_name).
    - On every `Timer`, emits one row per symbol:
        {"timestamp": timer_ts, "symbol": sym, "factors": {factor_name: value, ...}}
      where factor snapshot uses the latest factor with `factor_ts <= timer_ts`.

    This produces a factor table that can be merged with a label table on
    (timestamp, symbol) for rankIC/OLS and other downstream analysis.
    """

    event_engine: Any
    max_records: int
    enable_store: bool
    emit_empty: bool

    def __init__(
        self,
        max_records: int = 20000,
        enable_store: bool = True,
        emit_empty: bool = False,
    ) -> None: ...

    def start(self, engine: EventEngine) -> None: ...
    def stop(self) -> None: ...
    def reset(self) -> None: ...

    def on_factor(self, signal: FactorSignal) -> None: ...
    def on_timer(self, timer: Timer) -> None: ...

    def symbols(self) -> list[str]: ...
    def factors(self) -> list[str]: ...

    def get_records(
        self,
        symbol: str | None = None,
        start_ts: int | None = None,
        end_ts: int | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]: ...

    def get_dense_records(
        self,
        factors: Iterable[str] | None = None,
        fill_nan: bool = True,
        limit: int | None = None,
    ) -> list[dict[str, Any]]: ...

    def to_dataframe(
        self,
        factors: Iterable[str] | None = None,
        fill_nan: bool = True,
        limit: int | None = None,
    ) -> Any: ...

    def pop_new_records(self, max_items: int | None = None) -> list[dict[str, Any]]: ...

    def get_row(self, ts: int, symbol: str) -> dict[str, Any]:
        """Return the latest row matching (ts, symbol), or {}."""
        ...
