# hft_backtest/okx/factor_evaluator.pyx
# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False
# cython: cdivision=True

from __future__ import annotations

import math
from collections import deque

from libc.math cimport sqrt, fabs

from hft_backtest.event_engine cimport EventEngine, Component
from hft_backtest.factor cimport FactorSignal
from hft_backtest.okx.event cimport OKXBookticker, OKXTrades


def _sort_by_evaluated(item):
    """Sort key for (symbol, _SymbolStats) tuples."""
    return item[1].n_xy


cdef inline double _nan():
    return float('nan')


cdef inline bint _isfinite(double x):
    # Avoid importing numpy; use math.isfinite via Python for portability.
    # In practice Cython will call Python anyway, so keep it simple.
    return math.isfinite(x)


cdef inline double _mid_from_bookticker(OKXBookticker e):
    cdef double bid = e.bid_price_1
    cdef double ask = e.ask_price_1
    if bid > 0.0 and ask > 0.0:
        return (bid + ask) * 0.5
    if bid > 0.0:
        return bid
    if ask > 0.0:
        return ask
    return 0.0


cdef inline double _safe_div(double a, double b):
    if b == 0.0:
        return _nan()
    return a / b


cdef class _RunningStats:
    cdef long long n
    cdef double sum
    cdef double sum2
    cdef double min_v
    cdef double max_v

    def __cinit__(self):
        self.n = 0
        self.sum = 0.0
        self.sum2 = 0.0
        self.min_v = _nan()
        self.max_v = _nan()

    cdef void update(self, double x):
        if not _isfinite(x):
            return
        self.n += 1
        self.sum += x
        self.sum2 += x * x
        if self.n == 1:
            self.min_v = x
            self.max_v = x
        else:
            if x < self.min_v:
                self.min_v = x
            if x > self.max_v:
                self.max_v = x

    cdef inline double mean(self):
        return _safe_div(self.sum, <double>self.n) if self.n > 0 else _nan()

    cdef inline double var(self):
        if self.n <= 1:
            return _nan()
        cdef double m = self.sum / <double>self.n
        cdef double v = self.sum2 / <double>self.n - m * m
        # numerical guard
        if v < 0.0 and v > -1e-18:
            v = 0.0
        return v

    cdef inline double std(self):
        cdef double v = self.var()
        if not _isfinite(v) or v < 0.0:
            return _nan()
        return sqrt(v)


cdef class _SymbolStats:
    cdef public str symbol

    # counters
    cdef public long long n_bookticker
    cdef public long long n_trades
    cdef public long long n_factor
    cdef public long long n_skipped_no_price
    cdef public long long n_skipped_bad_price

    # timestamps
    cdef public long long first_ts
    cdef public long long last_ts

    # last observed market state
    cdef public double last_mid
    cdef public long long last_mid_ts
    cdef public double last_trade
    cdef public long long last_trade_ts

    # pending factor samples awaiting horizon
    cdef public object pending  # deque[(factor_ts, factor_value, ref_mid)]

    # stats for evaluated samples
    cdef _RunningStats x_stats
    cdef _RunningStats y_stats
    cdef _RunningStats delay_stats

    # sums for correlation / regression
    cdef public long long n_xy
    cdef public double sum_x
    cdef public double sum_y
    cdef public double sum_x2
    cdef public double sum_y2
    cdef public double sum_xy

    # sign/hit stats
    cdef public long long n_x_pos
    cdef public long long n_x_neg
    cdef public long long n_x_zero
    cdef public long long n_y_pos
    cdef public long long n_y_neg
    cdef public long long n_y_zero
    cdef public long long n_hit
    cdef public long long n_miss

    # factor autocorrelation (lag-1) as turnover proxy
    cdef public bint has_last_x
    cdef public double last_x
    cdef public long long n_ac
    cdef public double sum_x_prev
    cdef public double sum_x_curr
    cdef public double sum_x_prev2
    cdef public double sum_x_curr2
    cdef public double sum_x_prev_curr

    def __cinit__(self):
        self.symbol = ""
        self.n_bookticker = 0
        self.n_trades = 0
        self.n_factor = 0
        self.n_skipped_no_price = 0
        self.n_skipped_bad_price = 0
        self.first_ts = 0
        self.last_ts = 0
        self.last_mid = 0.0
        self.last_mid_ts = 0
        self.last_trade = 0.0
        self.last_trade_ts = 0
        self.pending = deque()
        self.x_stats = _RunningStats()
        self.y_stats = _RunningStats()
        self.delay_stats = _RunningStats()
        self.n_xy = 0
        self.sum_x = 0.0
        self.sum_y = 0.0
        self.sum_x2 = 0.0
        self.sum_y2 = 0.0
        self.sum_xy = 0.0
        self.n_x_pos = 0
        self.n_x_neg = 0
        self.n_x_zero = 0
        self.n_y_pos = 0
        self.n_y_neg = 0
        self.n_y_zero = 0
        self.n_hit = 0
        self.n_miss = 0
        self.has_last_x = False
        self.last_x = 0.0
        self.n_ac = 0
        self.sum_x_prev = 0.0
        self.sum_x_curr = 0.0
        self.sum_x_prev2 = 0.0
        self.sum_x_curr2 = 0.0
        self.sum_x_prev_curr = 0.0


cdef class FactorEvaluator(Component):
    """OKX factor evaluation component.

    Listens to:
    - `OKXBookticker`: updates mid-price reference and realizes pending samples
    - `OKXTrades`: currently used for basic monitoring (last trade, counts)
    - `FactorSignal`: queues a factor sample awaiting forward return

    Forward return definition:
        r = (mid_t - mid_0) / mid_0
    where mid_0 is the latest known mid at factor time, and mid_t is the first
    mid observed at timestamp >= factor_ts + horizon.

    This implementation is intentionally self-contained (no numpy dependency in
    the core logic) and uses O(1) streaming statistics.
    """

    def __init__(self, long long horizon=0, bint enable_store=True, int max_store=20000):
        self.event_engine = None
        self.horizon = horizon
        self.enable_store = enable_store
        self.max_store = max_store
        self._sym = {}
        self._global_first_ts = 0
        self._global_last_ts = 0

    def _get_or_create(self, str symbol):
        cdef _SymbolStats st = self._sym.get(symbol)
        if st is None:
            st = _SymbolStats()
            st.symbol = symbol
            self._sym[symbol] = st
        return st

    def _touch_ts(self, _SymbolStats st, long long ts):
        if ts <= 0:
            return
        if st.first_ts == 0:
            st.first_ts = ts
        st.last_ts = ts
        if self._global_first_ts == 0:
            self._global_first_ts = ts
        if ts > self._global_last_ts:
            self._global_last_ts = ts

    def _update_x_autocorr(self, _SymbolStats st, double x):
        """Update lag-1 autocorrelation stats for factor values.

        This uses correlation between consecutive factor values (x_{t-1}, x_t).
        Lower autocorr usually implies higher turnover (more jitter).
        """
        if not _isfinite(x):
            return
        if st.has_last_x:
            st.n_ac += 1
            st.sum_x_prev += st.last_x
            st.sum_x_curr += x
            st.sum_x_prev2 += st.last_x * st.last_x
            st.sum_x_curr2 += x * x
            st.sum_x_prev_curr += st.last_x * x
        st.last_x = x
        st.has_last_x = True

    def _update_xy(self, _SymbolStats st, double x, double y):
        if not _isfinite(x) or not _isfinite(y):
            return
        st.n_xy += 1
        st.sum_x += x
        st.sum_y += y
        st.sum_x2 += x * x
        st.sum_y2 += y * y
        st.sum_xy += x * y

    def _update_sign_stats(self, _SymbolStats st, double x, double y):
        if x > 0.0:
            st.n_x_pos += 1
        elif x < 0.0:
            st.n_x_neg += 1
        else:
            st.n_x_zero += 1

        if y > 0.0:
            st.n_y_pos += 1
        elif y < 0.0:
            st.n_y_neg += 1
        else:
            st.n_y_zero += 1

        if y == 0.0 or x == 0.0:
            return
        if x * y > 0.0:
            st.n_hit += 1
        else:
            st.n_miss += 1

    def _flush_pending(self, _SymbolStats st, long long market_ts, double mid_now, long long horizon):
        cdef object pending = st.pending
        cdef tuple item
        cdef long long factor_ts
        cdef double x
        cdef double ref_mid
        cdef double y
        cdef double delay

        while pending:
            item = pending[0]
            factor_ts = <long long>item[0]
            if horizon > 0 and market_ts < factor_ts + horizon:
                break

            pending.popleft()
            x = <double>item[1]
            ref_mid = <double>item[2]

            if ref_mid <= 0.0 or not _isfinite(ref_mid):
                st.n_skipped_bad_price += 1
                continue
            if mid_now <= 0.0 or not _isfinite(mid_now):
                st.n_skipped_bad_price += 1
                continue

            y = (mid_now - ref_mid) / ref_mid
            delay = <double>(market_ts - factor_ts)

            st.x_stats.update(x)
            st.y_stats.update(y)
            st.delay_stats.update(delay)
            self._update_xy(st, x, y)
            self._update_sign_stats(st, x, y)

    cpdef start(self, EventEngine engine):
        self.event_engine = engine
        engine.register(OKXBookticker, self.on_bookticker)
        engine.register(OKXTrades, self.on_trades)
        engine.register(FactorSignal, self.on_factor)

    cpdef stop(self):
        pass

    cpdef on_bookticker(self, OKXBookticker event):
        cdef _SymbolStats st = self._get_or_create(event.symbol)
        cdef double mid = _mid_from_bookticker(event)

        st.n_bookticker += 1
        self._touch_ts(st, event.timestamp)

        if mid > 0.0:
            st.last_mid = mid
            st.last_mid_ts = event.timestamp
            self._flush_pending(st, event.timestamp, mid, self.horizon)

    cpdef on_trades(self, OKXTrades event):
        cdef _SymbolStats st = self._get_or_create(event.symbol)
        st.n_trades += 1
        self._touch_ts(st, event.timestamp)
        if event.price > 0.0:
            st.last_trade = event.price
            st.last_trade_ts = event.timestamp

    cpdef on_factor(self, FactorSignal signal):
        cdef _SymbolStats st = self._get_or_create(signal.symbol)
        st.n_factor += 1
        self._touch_ts(st, signal.timestamp)

        # Turnover proxy: update autocorr regardless of whether we can evaluate y.
        self._update_x_autocorr(st, signal.value)

        if st.last_mid <= 0.0:
            st.n_skipped_no_price += 1
            return

        # Enqueue: (factor_ts, factor_value, ref_mid)
        st.pending.append((signal.timestamp, signal.value, st.last_mid))

        # If horizon == 0 and we already have an up-to-date mid at same ts,
        # we still wait for the *next* market observation to avoid r==0 bias.
        # (This matches typical forward-return evaluation.)

    cpdef reset(self):
        self._sym = {}
        self._global_first_ts = 0
        self._global_last_ts = 0

    cpdef list symbols(self):
        return list(self._sym.keys())

    def _symbol_dict(self, _SymbolStats st):
        cdef dict d = {}
        d["symbol"] = st.symbol
        d["time"] = {
            "first_ts": st.first_ts,
            "last_ts": st.last_ts,
            "span": (st.last_ts - st.first_ts) if st.first_ts and st.last_ts else 0,
        }
        d["counters"] = {
            "bookticker": st.n_bookticker,
            "trades": st.n_trades,
            "factor": st.n_factor,
            "evaluated": st.n_xy,
            "pending": len(st.pending),
            "skipped_no_price": st.n_skipped_no_price,
            "skipped_bad_price": st.n_skipped_bad_price,
        }
        d["last_market"] = {
            "last_mid": st.last_mid,
            "last_mid_ts": st.last_mid_ts,
            "last_trade": st.last_trade,
            "last_trade_ts": st.last_trade_ts,
        }

        # core moments
        cdef double mx = st.x_stats.mean()
        cdef double sx = st.x_stats.std()
        cdef double my = st.y_stats.mean()
        cdef double sy = st.y_stats.std()
        cdef double md = st.delay_stats.mean()
        cdef double sd = st.delay_stats.std()

        # correlation/regression
        cdef double corr = _nan()
        cdef double beta = _nan()
        cdef double alpha = _nan()
        cdef double tstat = _nan()

        # factor autocorr (lag-1)
        cdef double x_autocorr1 = _nan()
        cdef double turnover_proxy = _nan()

        cdef double n
        cdef double cov
        cdef double vx
        cdef double vy

        if st.n_xy >= 2:
            n = <double>st.n_xy
            cov = st.sum_xy / n - (st.sum_x / n) * (st.sum_y / n)
            vx = st.sum_x2 / n - (st.sum_x / n) * (st.sum_x / n)
            vy = st.sum_y2 / n - (st.sum_y / n) * (st.sum_y / n)
            if vx < 0.0 and vx > -1e-18:
                vx = 0.0
            if vy < 0.0 and vy > -1e-18:
                vy = 0.0
            if vx > 0.0 and vy > 0.0:
                corr = cov / sqrt(vx * vy)
            if vx > 0.0:
                beta = cov / vx
                alpha = my - beta * mx
            # correlation t-stat approximation
            if st.n_xy > 2 and _isfinite(corr) and fabs(corr) < 1.0:
                tstat = corr * sqrt((st.n_xy - 2) / (1.0 - corr * corr))

        if st.n_ac >= 2:
            n = <double>st.n_ac
            cov = st.sum_x_prev_curr / n - (st.sum_x_prev / n) * (st.sum_x_curr / n)
            vx = st.sum_x_prev2 / n - (st.sum_x_prev / n) * (st.sum_x_prev / n)
            vy = st.sum_x_curr2 / n - (st.sum_x_curr / n) * (st.sum_x_curr / n)
            if vx < 0.0 and vx > -1e-18:
                vx = 0.0
            if vy < 0.0 and vy > -1e-18:
                vy = 0.0
            if vx > 0.0 and vy > 0.0:
                x_autocorr1 = cov / sqrt(vx * vy)
                turnover_proxy = 1.0 - x_autocorr1

        d["params"] = {
            "horizon": self.horizon,
        }
        d["factor"] = {
            "mean": mx,
            "std": sx,
            "min": st.x_stats.min_v,
            "max": st.x_stats.max_v,
            "pos": st.n_x_pos,
            "neg": st.n_x_neg,
            "zero": st.n_x_zero,
        }
        d["forward_return"] = {
            "mean": my,
            "std": sy,
            "min": st.y_stats.min_v,
            "max": st.y_stats.max_v,
            "pos": st.n_y_pos,
            "neg": st.n_y_neg,
            "zero": st.n_y_zero,
        }
        d["relationship"] = {
            "corr": corr,
            "corr_tstat": tstat,
            "reg_beta": beta,
            "reg_alpha": alpha,
            "hit": st.n_hit,
            "miss": st.n_miss,
            "hit_rate": _safe_div(<double>st.n_hit, <double>(st.n_hit + st.n_miss)) if (st.n_hit + st.n_miss) > 0 else _nan(),
            "x_autocorr1": x_autocorr1,
            "turnover_proxy": turnover_proxy,
        }
        d["delay"] = {
            "mean": md,
            "std": sd,
            "min": st.delay_stats.min_v,
            "max": st.delay_stats.max_v,
        }
        return d

    cpdef dict get_symbol_stats(self, str symbol):
        cdef _SymbolStats st = self._sym.get(symbol)
        if st is None:
            raise KeyError(symbol)
        return self._symbol_dict(st)

    cpdef dict get_stats(self):
        cdef dict out = {}
        out["params"] = {
            "horizon": self.horizon,
            "enable_store": bool(self.enable_store),
            "max_store": int(self.max_store),
        }
        out["time"] = {
            "first_ts": self._global_first_ts,
            "last_ts": self._global_last_ts,
            "span": (self._global_last_ts - self._global_first_ts) if self._global_first_ts and self._global_last_ts else 0,
        }
        out["symbols"] = list(self._sym.keys())
        out["per_symbol"] = {k: self._symbol_dict(v) for k, v in self._sym.items()}
        return out

    def _format_symbol_report(self, _SymbolStats st):
        d = self._symbol_dict(st)
        cdef list lines = []

        cdef dict counters = d["counters"]
        cdef dict factor = d["factor"]
        cdef dict fr = d["forward_return"]
        cdef dict rel = d["relationship"]
        cdef dict delay = d["delay"]
        cdef dict lastm = d["last_market"]
        cdef dict time = d["time"]

        lines.append(f"Symbol: {st.symbol}")
        lines.append(f"  Time: first={time['first_ts']} last={time['last_ts']} span={time['span']}")
        lines.append(
            "  Counters: "
            f"bookticker={counters['bookticker']} trades={counters['trades']} "
            f"factor={counters['factor']} evaluated={counters['evaluated']} pending={counters['pending']} "
            f"skipped_no_price={counters['skipped_no_price']} skipped_bad_price={counters['skipped_bad_price']}"
        )
        lines.append(
            "  LastMarket: "
            f"mid={lastm['last_mid']:.8f} mid_ts={lastm['last_mid_ts']} "
            f"trade={lastm['last_trade']:.8f} trade_ts={lastm['last_trade_ts']}"
        )

        lines.append(
            "  Factor(x): "
            f"mean={factor['mean']:.6g} std={factor['std']:.6g} min={factor['min']:.6g} max={factor['max']:.6g} "
            f"pos/neg/zero={factor['pos']}/{factor['neg']}/{factor['zero']}"
        )
        lines.append(
            "  Return(y): "
            f"mean={fr['mean']:.6g} std={fr['std']:.6g} min={fr['min']:.6g} max={fr['max']:.6g} "
            f"pos/neg/zero={fr['pos']}/{fr['neg']}/{fr['zero']}"
        )
        lines.append(
            "  Relation: "
            f"corr={rel['corr']:.6g} t={rel['corr_tstat']:.6g} beta={rel['reg_beta']:.6g} alpha={rel['reg_alpha']:.6g} "
            f"hit_rate={rel['hit_rate']:.4f} (hit={rel['hit']} miss={rel['miss']}) "
            f"x_autocorr1={rel['x_autocorr1']:.6g} turnover_proxy={rel['turnover_proxy']:.6g}"
        )
        lines.append(
            "  Delay: "
            f"mean={delay['mean']:.6g} std={delay['std']:.6g} min={delay['min']:.6g} max={delay['max']:.6g}"
        )

        return lines

    cpdef str format_report(self, str symbol=None, int max_symbols=20):
        cdef list lines = []
        lines.append("FactorEvaluator Report")
        lines.append(f"  horizon={self.horizon} enable_store={bool(self.enable_store)} max_store={int(self.max_store)}")
        lines.append(f"  global_first_ts={self._global_first_ts} global_last_ts={self._global_last_ts} span={(self._global_last_ts - self._global_first_ts) if self._global_first_ts and self._global_last_ts else 0}")

        if symbol is not None:
            st = self._sym.get(symbol)
            if st is None:
                lines.append(f"  (no data for symbol='{symbol}')")
            else:
                lines.extend(self._format_symbol_report(st))
            return "\n".join(lines) + "\n"

        # sort symbols by evaluated count
        cdef list items = list(self._sym.items())
        items.sort(key=_sort_by_evaluated, reverse=True)

        cdef int shown = 0
        for k, st in items:
            if shown >= max_symbols:
                break
            lines.append("")
            lines.extend(self._format_symbol_report(st))
            shown += 1

        if len(items) > shown:
            lines.append("")
            lines.append(f"  ... {len(items) - shown} more symbols not shown (increase max_symbols)")

        return "\n".join(lines) + "\n"

    cpdef print_report(self, str symbol=None, int max_symbols=20):
        print(self.format_report(symbol=symbol, max_symbols=max_symbols), end="")
