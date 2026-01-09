import sys

import pandas as pd
import pytest

from hft_backtest import EventEngine, FactorSampler, Timer
from hft_backtest.factor import FactorSignal
from hft_backtest.okx import OKXBookticker, OKXLabelSampler


class TestFactorLabelMerge:
    def test_merge_on_timestamp_symbol(self):
        ee = EventEngine()

        fs = FactorSampler(max_records=1000, enable_store=True, emit_empty=False)
        fs.start(ee)

        ls = OKXLabelSampler(max_records=1000, enable_store=True, store_prices=False)
        ls.start(ee)

        sym = "BTC-USDT-SWAP"

        # market
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

        # factor arrives before first timer
        f = FactorSignal(sym, 2.0, name="f1")
        f.timestamp = 900
        ee.put(f)

        # first timer creates factor row at 1010 and label sampler snapshots p0
        ee.put(Timer(1010))

        # move market price
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

        # second timer emits label for timestamp=1010
        ee.put(Timer(1020))

        df_x = fs.to_dataframe(factors=["f1"], fill_nan=True)
        df_y = ls.to_dataframe(symbol=sym)

        assert isinstance(df_x, pd.DataFrame)
        assert isinstance(df_y, pd.DataFrame)

        merged = df_x.merge(df_y, on=["timestamp", "symbol"], how="inner")
        assert len(merged) == 1
        assert merged.iloc[0]["timestamp"] == 1010
        assert merged.iloc[0]["symbol"] == sym
        assert merged.iloc[0]["f1"] == pytest.approx(2.0)
        assert merged.iloc[0]["y"] == pytest.approx(0.1)


if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))
