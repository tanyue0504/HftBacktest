import sys

import pytest

from hft_backtest import EventEngine
from hft_backtest.factor import FactorSignal
from hft_backtest.okx import FactorMarketSampler, OKXBookticker


class TestOKXFactorMarketSampler:
    def test_aligns_factor_with_next_interval_return(self):
        ee = EventEngine()
        sampler = FactorMarketSampler(interval_ms=10)
        sampler.start(ee)

        sym = "BTC-USDT-SWAP"

        # First bookticker initializes the sampler state (no boundary yet).
        ee.put(
            OKXBookticker(
                timestamp=1005,
                symbol=sym,
                bid_price_1=100.0,
                ask_price_1=100.0,
                bid_amount_1=1.0,
                ask_amount_1=1.0,
            )
        )

        # Factor arrives before t=1010 boundary.
        f = FactorSignal(sym, 1.0, name="f1")
        f.timestamp = 1008
        ee.put(f)

        # Cross boundary 1010: boundary price uses previous mid=100.0
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

        # Cross boundary 1020: boundary price uses previous mid=110.0
        ee.put(
            OKXBookticker(
                timestamp=1025,
                symbol=sym,
                bid_price_1=121.0,
                ask_price_1=121.0,
                bid_amount_1=1.0,
                ask_amount_1=1.0,
            )
        )

        samples = sampler.get_samples(symbol=sym, factor="f1")
        assert len(samples) == 1
        s0 = samples[0]
        assert s0["ts"] == 1010
        assert s0["x"] == pytest.approx(1.0)
        assert s0["x_ts"] == 1008
        # y over (1010 -> 1020): (110-100)/100 = 0.1
        assert s0["y"] == pytest.approx(0.1)

    def test_skips_when_factor_is_after_sample_ts(self):
        ee = EventEngine()
        sampler = FactorMarketSampler(interval_ms=10)
        sampler.start(ee)

        sym = "ETH-USDT-SWAP"

        ee.put(
            OKXBookticker(
                timestamp=1005,
                symbol=sym,
                bid_price_1=200.0,
                ask_price_1=200.0,
                bid_amount_1=1.0,
                ask_amount_1=1.0,
            )
        )

        # Factor arrives AFTER t=1010, so it should NOT be used for the sample at ts=1010.
        f = FactorSignal(sym, 1.0, name="f1")
        f.timestamp = 1012
        ee.put(f)

        ee.put(
            OKXBookticker(
                timestamp=1015,
                symbol=sym,
                bid_price_1=210.0,
                ask_price_1=210.0,
                bid_amount_1=1.0,
                ask_amount_1=1.0,
            )
        )
        ee.put(
            OKXBookticker(
                timestamp=1025,
                symbol=sym,
                bid_price_1=220.0,
                ask_price_1=220.0,
                bid_amount_1=1.0,
                ask_amount_1=1.0,
            )
        )

        assert sampler.get_samples(symbol=sym, factor="f1") == []

    def test_multi_symbol_cross_section_access(self):
        ee = EventEngine()
        sampler = FactorMarketSampler(interval_ms=10)
        sampler.start(ee)

        s1 = "BTC-USDT-SWAP"
        s2 = "SOL-USDT-SWAP"

        # init both
        ee.put(
            OKXBookticker(
                timestamp=1005,
                symbol=s1,
                bid_price_1=100.0,
                ask_price_1=100.0,
                bid_amount_1=1.0,
                ask_amount_1=1.0,
            )
        )
        ee.put(
            OKXBookticker(
                timestamp=1005,
                symbol=s2,
                bid_price_1=50.0,
                ask_price_1=50.0,
                bid_amount_1=1.0,
                ask_amount_1=1.0,
            )
        )

        f1 = FactorSignal(s1, 2.0, name="f1")
        f1.timestamp = 1008
        ee.put(f1)
        f2 = FactorSignal(s2, -1.0, name="f1")
        f2.timestamp = 1007
        ee.put(f2)

        # cross 1010 boundary
        ee.put(
            OKXBookticker(
                timestamp=1015,
                symbol=s1,
                bid_price_1=110.0,
                ask_price_1=110.0,
                bid_amount_1=1.0,
                ask_amount_1=1.0,
            )
        )
        ee.put(
            OKXBookticker(
                timestamp=1015,
                symbol=s2,
                bid_price_1=55.0,
                ask_price_1=55.0,
                bid_amount_1=1.0,
                ask_amount_1=1.0,
            )
        )

        # cross 1020 boundary
        ee.put(
            OKXBookticker(
                timestamp=1025,
                symbol=s1,
                bid_price_1=121.0,
                ask_price_1=121.0,
                bid_amount_1=1.0,
                ask_amount_1=1.0,
            )
        )
        ee.put(
            OKXBookticker(
                timestamp=1025,
                symbol=s2,
                bid_price_1=60.5,
                ask_price_1=60.5,
                bid_amount_1=1.0,
                ask_amount_1=1.0,
            )
        )

        xs = sampler.get_cross_section(ts=1010, factor="f1")
        assert set(xs.keys()) == {s1, s2}
        assert xs[s1]["x"] == pytest.approx(2.0)
        assert xs[s2]["x"] == pytest.approx(-1.0)
        assert xs[s1]["y"] == pytest.approx(0.1)
        assert xs[s2]["y"] == pytest.approx(0.1)


if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))
