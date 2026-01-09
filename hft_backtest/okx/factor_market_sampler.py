from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, Iterable, List, Optional, Tuple

from hft_backtest.event_engine import Component, EventEngine
from hft_backtest.factor import FactorSignal
from hft_backtest.okx.event import OKXBookticker


@dataclass
class _FactorPoint:
    ts: int
    x: float


@dataclass
class _BoundaryPoint:
    ts: int
    mid: float


class FactorMarketSampler(Component):
    """Align per-(symbol,factor) signals with next-interval market target.

    This component is OKX-specific because it relies on OKX market data events.

    Alignment rule (fixed interval):
    - Maintain a grid of boundary timestamps $t_k = k * interval$.
    - For each symbol, record boundary price `p(t_k)` as the *last* known mid-price
      strictly before crossing `t_k` (i.e., from the previous bookticker).
    - When both `p(t_k)` and `p(t_{k+1})` are available, compute
        y_k = (p(t_{k+1}) - p(t_k)) / p(t_k)
      and align it with factor snapshot x_k which is the latest factor value with
      timestamp <= t_k.

    Notes:
    - The first boundary cannot be formed until we have at least two booktickers.
    - If there is no factor value available at or before t_k, the sample is skipped.
    """

    def __init__(
        self,
        interval_ms: int,
        *,
        max_samples_per_series: int = 20000,
        store_prices: bool = False,
    ) -> None:
        if interval_ms <= 0:
            raise ValueError("interval_ms must be > 0")
        if max_samples_per_series < 0:
            raise ValueError("max_samples_per_series must be >= 0")

        self.interval_ms = int(interval_ms)
        self.max_samples_per_series = int(max_samples_per_series)
        self.store_prices = bool(store_prices)

        self.event_engine: Optional[EventEngine] = None

        # Latest factor per (symbol, factor_name)
        self._latest_factor: Dict[Tuple[str, str], _FactorPoint] = {}

        # Per-symbol market state
        self._last_mid: Dict[str, float] = {}
        self._last_mid_ts: Dict[str, int] = {}
        self._next_boundary: Dict[str, int] = {}

        # Per-symbol boundary prices (ts -> mid) stored as a short deque in time order
        self._boundaries: Dict[str, Deque[_BoundaryPoint]] = defaultdict(deque)

        # Samples per (symbol, factor_name)
        # Each sample is a dict for easy downstream use (rankIC/OLS, etc)
        self._samples: Dict[Tuple[str, str], Deque[dict[str, Any]]] = defaultdict(deque)

        # A queue of newly created samples for streaming access
        self._new_samples: Deque[dict[str, Any]] = deque()

    def start(self, engine: EventEngine) -> None:
        self.event_engine = engine
        engine.register(FactorSignal, self.on_factor)
        engine.register(OKXBookticker, self.on_bookticker)

    def stop(self) -> None:
        pass

    def reset(self) -> None:
        self._latest_factor.clear()
        self._last_mid.clear()
        self._last_mid_ts.clear()
        self._next_boundary.clear()
        self._boundaries.clear()
        self._samples.clear()
        self._new_samples.clear()

    # ---------- Event handlers ----------

    def on_factor(self, signal: FactorSignal) -> None:
        key = (signal.symbol, signal.name)
        self._latest_factor[key] = _FactorPoint(int(signal.timestamp), float(signal.value))

    def on_bookticker(self, event: OKXBookticker) -> None:
        sym = event.symbol
        ts = int(event.timestamp)
        mid = self._mid_from_bookticker(event)
        if mid <= 0.0:
            return

        # First tick: initialize state and wait for next bookticker to create boundaries.
        if sym not in self._last_mid_ts:
            self._last_mid[sym] = mid
            self._last_mid_ts[sym] = ts
            # Start at the next boundary after the first observed timestamp.
            self._next_boundary[sym] = ((ts // self.interval_ms) + 1) * self.interval_ms
            return

        # Record any boundaries crossed by this tick, using the previous mid (no lookahead).
        next_b = self._next_boundary.get(sym)
        if next_b is None:
            next_b = ((ts // self.interval_ms) + 1) * self.interval_ms

        prev_mid = self._last_mid[sym]
        while next_b <= ts:
            self._append_boundary(sym, next_b, prev_mid)
            # Each new boundary potentially enables one interval return sample
            self._try_emit_interval(sym)
            next_b += self.interval_ms

        self._next_boundary[sym] = next_b

        # Update last mid after processing boundaries
        self._last_mid[sym] = mid
        self._last_mid_ts[sym] = ts

    # ---------- Public accessors ----------

    def factors(self, symbol: str | None = None) -> List[str]:
        names = set()
        for sym, fname in self._latest_factor.keys():
            if symbol is None or sym == symbol:
                names.add(fname)
        return sorted(names)

    def symbols(self) -> List[str]:
        syms = set(self._last_mid.keys())
        for sym, _ in self._latest_factor.keys():
            syms.add(sym)
        return sorted(syms)

    def get_samples(
        self,
        *,
        symbol: str | None = None,
        factor: str | None = None,
        start_ts: int | None = None,
        end_ts: int | None = None,
        limit: int | None = None,
    ) -> List[dict[str, Any]]:
        """Return stored samples filtered by symbol/factor and time range."""
        out: List[dict[str, Any]] = []
        for (sym, fname), dq in self._samples.items():
            if symbol is not None and sym != symbol:
                continue
            if factor is not None and fname != factor:
                continue
            for s in dq:
                ts = int(s["ts"])
                if start_ts is not None and ts < start_ts:
                    continue
                if end_ts is not None and ts > end_ts:
                    continue
                out.append(s)

        out.sort(key=lambda d: (d["ts"], d["symbol"], d["factor"]))
        if limit is not None:
            return out[-int(limit) :]
        return out

    def pop_new_samples(self, max_items: int | None = None) -> List[dict[str, Any]]:
        """Pop newly created samples (FIFO) for incremental processing."""
        n = len(self._new_samples) if max_items is None else min(len(self._new_samples), int(max_items))
        out = []
        for _ in range(n):
            out.append(self._new_samples.popleft())
        return out

    def get_cross_section(self, ts: int, factor: str) -> Dict[str, dict[str, Any]]:
        """Return {symbol -> sample} for a given (ts, factor)."""
        target_ts = int(ts)
        out: Dict[str, dict[str, Any]] = {}
        for (sym, fname), dq in self._samples.items():
            if fname != factor:
                continue
            # Most deques are append-only in time order; scan from the end.
            for s in reversed(dq):
                if int(s["ts"]) == target_ts:
                    out[sym] = s
                    break
                if int(s["ts"]) < target_ts:
                    break
        return out

    # ---------- Internals ----------

    @staticmethod
    def _mid_from_bookticker(event: OKXBookticker) -> float:
        bid = float(event.bid_price_1)
        ask = float(event.ask_price_1)
        if bid <= 0.0 or ask <= 0.0:
            return 0.0
        return 0.5 * (bid + ask)

    def _append_boundary(self, symbol: str, boundary_ts: int, mid: float) -> None:
        dq = self._boundaries[symbol]
        dq.append(_BoundaryPoint(int(boundary_ts), float(mid)))
        # Keep only last 3 boundaries; enough to compute next interval and avoid memory growth.
        while len(dq) > 3:
            dq.popleft()

    def _try_emit_interval(self, symbol: str) -> None:
        dq = self._boundaries.get(symbol)
        if not dq or len(dq) < 2:
            return

        b0 = dq[-2]
        b1 = dq[-1]
        if b0.mid <= 0.0:
            return

        y = (b1.mid - b0.mid) / b0.mid
        sample_ts = int(b0.ts)

        # For each factor series on this symbol, emit a sample if we have x snapshot at/before sample_ts.
        for (sym, fname), fp in list(self._latest_factor.items()):
            if sym != symbol:
                continue
            if fp.ts > sample_ts:
                continue

            sample: dict[str, Any] = {
                "symbol": sym,
                "factor": fname,
                "ts": sample_ts,
                "x": fp.x,
                "x_ts": fp.ts,
                "y": float(y),
            }
            if self.store_prices:
                sample["p0"] = float(b0.mid)
                sample["p1"] = float(b1.mid)
                sample["p0_ts"] = int(b0.ts)
                sample["p1_ts"] = int(b1.ts)

            series = self._samples[(sym, fname)]
            series.append(sample)
            self._new_samples.append(sample)

            if self.max_samples_per_series > 0:
                while len(series) > self.max_samples_per_series:
                    series.popleft()

