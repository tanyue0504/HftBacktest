import sys

import pandas as pd
import pytest

from hft_backtest import EventEngine, FactorSampler, Timer
from hft_backtest.factor import FactorSignal


class TestFactorSampler:
    def test_emits_rows_on_timer(self):
        ee = EventEngine()
        fs = FactorSampler(max_records=1000, enable_store=True, emit_empty=False)
        fs.start(ee)

        sym = "BTC-USDT"

        f1 = FactorSignal(sym, 1.0, name="f1")
        f1.timestamp = 900
        ee.put(f1)

        ee.put(Timer(1000))

        recs = fs.get_records(symbol=sym)
        assert len(recs) == 1
        r0 = recs[0]
        assert r0["timestamp"] == 1000
        assert r0["symbol"] == sym
        assert r0["factors"]["f1"] == pytest.approx(1.0)

        df = fs.to_dataframe(factors=["f1"], fill_nan=True)
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["timestamp", "symbol", "f1"]
        assert len(df) == 1
        assert df.iloc[0]["timestamp"] == 1000
        assert df.iloc[0]["symbol"] == sym
        assert df.iloc[0]["f1"] == pytest.approx(1.0)

    def test_filters_out_future_factor_timestamp(self):
        ee = EventEngine()
        fs = FactorSampler(max_records=1000, enable_store=True, emit_empty=False)
        fs.start(ee)

        sym = "ETH-USDT"

        # factor timestamp is after timer ts; should not be included
        f1 = FactorSignal(sym, 2.0, name="f1")
        f1.timestamp = 1100
        ee.put(f1)

        ee.put(Timer(1000))

        assert fs.get_records(symbol=sym) == []

    def test_dense_records_shape(self):
        ee = EventEngine()
        fs = FactorSampler(max_records=1000, enable_store=True, emit_empty=True)
        fs.start(ee)

        sym = "SOL-USDT"

        f1 = FactorSignal(sym, 1.0, name="f1")
        f1.timestamp = 900
        ee.put(f1)

        f2 = FactorSignal(sym, -3.0, name="f2")
        f2.timestamp = 950
        ee.put(f2)

        ee.put(Timer(1000))

        dense = fs.get_dense_records(factors=["f1", "f2"], fill_nan=True)
        assert len(dense) == 1
        row = dense[0]
        assert row["timestamp"] == 1000
        assert row["symbol"] == sym
        assert row["f1"] == pytest.approx(1.0)
        assert row["f2"] == pytest.approx(-3.0)


if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))
