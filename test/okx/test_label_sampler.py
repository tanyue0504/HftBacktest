import sys

import pandas as pd
import pytest

from hft_backtest import EventEngine, Timer
from hft_backtest.okx import OKXBookticker, OKXLabelSampler


class TestOKXLabelSampler:
    def test_emits_y_for_previous_timer_ts(self):
        ee = EventEngine()
        ls = OKXLabelSampler(max_records=1000, enable_store=True, store_prices=True)
        ls.start(ee)

        sym = "BTC-USDT-SWAP"

        ee.put(
            OKXBookticker(
                timestamp=1001,
                symbol=sym,
                bid_price_1=100.0,
                ask_price_1=100.0,
                bid_amount_1=1.0,
                ask_amount_1=1.0,
            )
        )

        # first timer: only snapshot p0
        ee.put(Timer(1010))

        ee.put(
            OKXBookticker(
                timestamp=1015,
                symbol=sym,
                bid_price_1=110.0,
                ask_price_1=110.0,
                bid_amount_1=1.0,
                ask_amount_1=1.0,
            )
        )

        # second timer: emits label for ts=1010 using p1=110
        ee.put(Timer(1020))

        recs = ls.get_records(symbol=sym)
        assert len(recs) == 1
        r0 = recs[0]
        assert r0["timestamp"] == 1010
        assert r0["symbol"] == sym
        assert r0["y"] == pytest.approx(0.1)
        assert r0["p0"] == pytest.approx(100.0)
        assert r0["p1"] == pytest.approx(110.0)
        assert r0["p0_ts"] == 1010
        assert r0["p1_ts"] == 1020

        df = ls.to_dataframe(symbol=sym)
        assert isinstance(df, pd.DataFrame)
        assert set(["timestamp", "symbol", "y"]).issubset(df.columns)
        assert len(df) == 1
        assert df.iloc[0]["timestamp"] == 1010
        assert df.iloc[0]["symbol"] == sym
        assert df.iloc[0]["y"] == pytest.approx(0.1)


if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))
