# cython: language_level=3

from hft_backtest.event_engine cimport Component, EventEngine
from hft_backtest.factor cimport FactorSignal
from hft_backtest.timer cimport Timer


cdef class FactorSampler(Component):
    cdef public object event_engine
    cdef public int max_records
    cdef public bint enable_store
    cdef public bint emit_empty

    cdef dict _latest_by_symbol   # {symbol: {factor_name: (factor_ts, value)}}
    cdef dict _symbols_set        # {symbol: True}
    cdef dict _factors_set        # {factor_name: True}

    cdef object _records          # deque[dict]
    cdef object _new_records      # deque[dict]

    cdef void _append_record(self, dict rec)

    cpdef start(self, EventEngine engine)
    cpdef stop(self)
    cpdef reset(self)

    cpdef on_factor(self, FactorSignal signal)
    cpdef on_timer(self, Timer timer)

    cpdef list symbols(self)
    cpdef list factors(self)
    cpdef list get_records(self, str symbol=*, long long start_ts=*, long long end_ts=*, int limit=*)
    cpdef list get_dense_records(self, object factors=*, bint fill_nan=*, int limit=*)
    cpdef object to_dataframe(self, object factors=*, bint fill_nan=*, int limit=*)
    cpdef list pop_new_records(self, int max_items=*)
    cpdef dict get_row(self, long long ts, str symbol)
