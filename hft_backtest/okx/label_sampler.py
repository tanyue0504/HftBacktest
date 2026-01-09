from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional

from hft_backtest.event_engine import Component, EventEngine
from hft_backtest.timer import Timer
from hft_backtest.okx.event import OKXBookticker


@dataclass
class _LastMarket:
    mid: float = 0.0
    ts: int = 0


class OKXLabelSampler(Component):
    """OKX label sampler driven by Timer.

    Listens to:
    - `OKXBookticker` to maintain last mid per symbol
    - `Timer` to snapshot price at timer timestamps

    On each timer tick at time t_k:
    - Take p_k = last known mid
    - If previous timer snapshot p_{k-1} exists, emit label for ts=t_{k-1}:
        y_{k-1} = (p_k - p_{k-1}) / p_{k-1}

    This ensures labels align with factor rows emitted by core `FactorSampler`
    that uses the same Timer timestamp.
    """

    def __init__(self, *, max_records: int = 20000, enable_store: bool = True, store_prices: bool = False) -> None:
        if max_records < 0:
            raise ValueError("max_records must be >= 0")
        self.max_records = int(max_records)
        self.enable_store = bool(enable_store)
        self.store_prices = bool(store_prices)

        self.event_engine: Optional[EventEngine] = None

        self._last_market: Dict[str, _LastMarket] = defaultdict(_LastMarket)
        self._last_timer_price: Dict[str, tuple[int, float]] = {}  # {symbol: (ts, price)}

        self._records: Deque[dict[str, Any]] = deque()
        self._new_records: Deque[dict[str, Any]] = deque()

    def start(self, engine: EventEngine) -> None:
        self.event_engine = engine
        engine.register(OKXBookticker, self.on_bookticker)
        engine.register(Timer, self.on_timer)

    def stop(self) -> None:
        pass

    def reset(self) -> None:
        self._last_market.clear()
        self._last_timer_price.clear()
        self._records.clear()
        self._new_records.clear()

    def on_bookticker(self, event: OKXBookticker) -> None:
        mid = self._mid_from_bookticker(event)
        if mid <= 0.0:
            return
        lm = self._last_market[event.symbol]
        lm.mid = mid
        lm.ts = int(event.timestamp)

    def on_timer(self, timer: Timer) -> None:
        ts = int(timer.timestamp)
        if ts <= 0:
            return

        for sym, lm in self._last_market.items():
            if lm.mid <= 0.0:
                continue

            prev = self._last_timer_price.get(sym)
            self._last_timer_price[sym] = (ts, lm.mid)

            if prev is None:
                continue
            prev_ts, prev_p = prev
            if prev_p <= 0.0:
                continue

            y = (lm.mid - prev_p) / prev_p
            rec: dict[str, Any] = {"timestamp": prev_ts, "symbol": sym, "y": float(y)}
            if self.store_prices:
                rec.update({"p0": float(prev_p), "p1": float(lm.mid), "p0_ts": int(prev_ts), "p1_ts": int(ts)})

            self._new_records.append(rec)
            if not self.enable_store:
                continue
            self._records.append(rec)
            if self.max_records > 0:
                while len(self._records) > self.max_records:
                    self._records.popleft()

    def get_records(self, *, symbol: str | None = None, start_ts: int | None = None, end_ts: int | None = None) -> List[dict[str, Any]]:
        out: List[dict[str, Any]] = []
        for r in self._records:
            if symbol is not None and r["symbol"] != symbol:
                continue
            rts = int(r["timestamp"])
            if start_ts is not None and rts < start_ts:
                continue
            if end_ts is not None and rts > end_ts:
                continue
            out.append(r)
        out.sort(key=lambda d: (d["timestamp"], d["symbol"]))
        return out

    def pop_new_records(self, max_items: int | None = None) -> List[dict[str, Any]]:
        n = len(self._new_records) if max_items is None else min(len(self._new_records), int(max_items))
        out: List[dict[str, Any]] = []
        for _ in range(n):
            out.append(self._new_records.popleft())
        return out

    def to_dataframe(self, *, symbol: str | None = None, start_ts: int | None = None, end_ts: int | None = None) -> Any:
        import pandas as pd

        records = self.get_records(symbol=symbol, start_ts=start_ts, end_ts=end_ts)
        if not records:
            cols = ["timestamp", "symbol", "y"]
            if self.store_prices:
                cols += ["p0", "p1", "p0_ts", "p1_ts"]
            return pd.DataFrame(columns=cols)
        return pd.DataFrame.from_records(records)

    @staticmethod
    def _mid_from_bookticker(event: OKXBookticker) -> float:
        bid = float(event.bid_price_1)
        ask = float(event.ask_price_1)
        if bid <= 0.0 or ask <= 0.0:
            return 0.0
        return 0.5 * (bid + ask)
