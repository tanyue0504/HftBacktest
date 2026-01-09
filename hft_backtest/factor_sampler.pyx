# hft_backtest/factor_sampler.pyx
# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False

from __future__ import annotations

from collections import deque

from hft_backtest.event_engine cimport Component, EventEngine
from hft_backtest.factor cimport FactorSignal
from hft_backtest.timer cimport Timer


cdef inline object _nan():
    return float('nan')


cdef class FactorSampler(Component):
    """Core factor sampler driven by Timer."""

    def __init__(self, int max_records=20000, bint enable_store=True, bint emit_empty=False):
        if max_records < 0:
            raise ValueError("max_records must be >= 0")
        self.event_engine = None
        self.max_records = max_records
        self.enable_store = enable_store
        self.emit_empty = emit_empty

        self._latest_by_symbol = {}   # {symbol: {factor_name: (factor_ts, value)}}
        self._symbols_set = {}        # {symbol: True}
        self._factors_set = {}        # {factor_name: True}

        self._records = deque()       # deque[dict]
        self._new_records = deque()   # deque[dict]

    cpdef start(self, EventEngine engine):
        self.event_engine = engine
        engine.register(FactorSignal, self.on_factor)
        engine.register(Timer, self.on_timer)

    cpdef stop(self):
        pass

    cpdef reset(self):
        self._latest_by_symbol = {}
        self._symbols_set = {}
        self._factors_set = {}
        self._records = deque()
        self._new_records = deque()

    cpdef on_factor(self, FactorSignal signal):
        cdef str sym = signal.symbol
        cdef str fname = signal.name
        cdef long long fts = signal.timestamp
        cdef double x = signal.value

        self._symbols_set[sym] = True
        self._factors_set[fname] = True

        d = self._latest_by_symbol.get(sym)
        if d is None:
            d = {}
            self._latest_by_symbol[sym] = d
        d[fname] = (fts, x)

    cpdef on_timer(self, Timer timer):
        cdef long long ts = timer.timestamp
        if ts <= 0:
            return

        # Emit one row per symbol.
        for sym in self._symbols_set.keys():
            d = self._latest_by_symbol.get(sym)
            if d is None:
                if self.emit_empty:
                    self._append_record({"timestamp": ts, "symbol": sym, "factors": {}})
                continue

            factors_out = {}
            for fname, pair in d.items():
                # pair: (factor_ts, value)
                if pair[0] <= ts:
                    factors_out[fname] = pair[1]

            if (not factors_out) and (not self.emit_empty):
                continue

            self._append_record({"timestamp": ts, "symbol": sym, "factors": factors_out})

    cdef void _append_record(self, dict rec):
        self._new_records.append(rec)
        if not self.enable_store:
            return
        self._records.append(rec)
        if self.max_records > 0:
            while len(self._records) > self.max_records:
                self._records.popleft()

    cpdef list symbols(self):
        return sorted(self._symbols_set.keys())

    cpdef list factors(self):
        return sorted(self._factors_set.keys())

    cpdef list get_records(self, str symbol=None, long long start_ts=0, long long end_ts=0, int limit=-1):
        out = []
        for rec in self._records:
            if symbol is not None and rec["symbol"] != symbol:
                continue
            rts = rec["timestamp"]
            if start_ts and rts < start_ts:
                continue
            if end_ts and rts > end_ts:
                continue
            out.append(rec)
        if limit is not None and limit >= 0:
            return out[-limit:]
        return out

    cpdef list get_dense_records(self, object factors=None, bint fill_nan=True, int limit=-1):
        """Flatten records into {timestamp, symbol, f1, f2, ...} dicts.

        - `factors=None` uses all seen factors (sorted).
        - `fill_nan=True` fills missing factor values with NaN.
        """
        if factors is None:
            factor_list = self.factors()
        else:
            factor_list = list(factors)

        out = []
        for rec in self._records:
            row = {"timestamp": rec["timestamp"], "symbol": rec["symbol"]}
            fdict = rec["factors"]
            for fname in factor_list:
                if fname in fdict:
                    row[fname] = fdict[fname]
                elif fill_nan:
                    row[fname] = _nan()
            out.append(row)

        if limit is not None and limit >= 0:
            return out[-limit:]
        return out

    cpdef object to_dataframe(self, object factors=None, bint fill_nan=True, int limit=-1):
        """Return a pandas.DataFrame with columns: timestamp, symbol, <factors...>."""
        import pandas as pd

        records = self.get_dense_records(factors=factors, fill_nan=fill_nan, limit=limit)
        if not records:
            # Keep a stable schema even when empty.
            if factors is None:
                factor_list = self.factors()
            else:
                factor_list = list(factors)
            cols = ["timestamp", "symbol"] + factor_list
            return pd.DataFrame(columns=cols)
        return pd.DataFrame.from_records(records)

    cpdef list pop_new_records(self, int max_items=-1):
        cdef int n
        if max_items is None or max_items < 0:
            n = len(self._new_records)
        else:
            n = max_items if max_items < len(self._new_records) else len(self._new_records)
        out = []
        for _ in range(n):
            out.append(self._new_records.popleft())
        return out

    cpdef dict get_row(self, long long ts, str symbol):
        # Scan from tail; records are append-only in time order.
        for rec in reversed(self._records):
            if rec["symbol"] != symbol:
                continue
            rts = rec["timestamp"]
            if rts == ts:
                return rec
            if rts < ts:
                break
        return {}
