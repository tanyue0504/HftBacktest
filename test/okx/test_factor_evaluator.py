import sys

import pytest

from hft_backtest import EventEngine
from hft_backtest.factor import FactorSignal
from hft_backtest.okx import OKXBookticker, OKXTrades, FactorEvaluator


class TestOKXFactorEvaluator:
    def test_basic_evaluation_and_report(self):
        ee = EventEngine()
        ev = FactorEvaluator(horizon=0, enable_store=True, max_store=1000)
        ev.start(ee)

        sym = "BTC-USDT-SWAP"

        # Initial quote (mid=100.1)
        ee.put(
            OKXBookticker(
                timestamp=1000,
                symbol=sym,
                bid_price_1=100.0,
                ask_price_1=100.2,
                bid_amount_1=1.0,
                ask_amount_1=1.0,
            )
        )

        f1 = FactorSignal(sym, 1.0, name="test_factor")
        f1.timestamp = 1000
        ee.put(f1)

        # Next quote up (mid=100.5)
        ee.put(
            OKXBookticker(
                timestamp=1010,
                symbol=sym,
                bid_price_1=100.4,
                ask_price_1=100.6,
                bid_amount_1=1.0,
                ask_amount_1=1.0,
            )
        )

        f2 = FactorSignal(sym, -2.0, name="test_factor")
        f2.timestamp = 1020
        ee.put(f2)

        # Next quote down (mid=100.1)
        ee.put(
            OKXBookticker(
                timestamp=1030,
                symbol=sym,
                bid_price_1=100.0,
                ask_price_1=100.2,
                bid_amount_1=1.0,
                ask_amount_1=1.0,
            )
        )

        # Trades are not used for eval, but should be counted
        ee.put(OKXTrades(timestamp=1031, symbol=sym, trade_id=1, price=100.1, size=0.5, side="buy"))

        stats = ev.get_symbol_stats(sym)
        assert stats["params"]["horizon"] == 0

        counters = stats["counters"]
        assert counters["bookticker"] == 3
        assert counters["trades"] == 1
        assert counters["factor"] == 2
        assert counters["evaluated"] == 2
        assert counters["pending"] == 0
        assert counters["skipped_no_price"] == 0
        assert counters["skipped_bad_price"] == 0

        # Since x=[1,-2] and y=[+, -], hit_rate should be 1
        rel = stats["relationship"]
        assert rel["hit"] == 2
        assert rel["miss"] == 0
        assert rel["hit_rate"] == pytest.approx(1.0)

        delay = stats["delay"]
        assert delay["mean"] == pytest.approx(10.0)
        assert delay["min"] == pytest.approx(10.0)
        assert delay["max"] == pytest.approx(10.0)

        report = ev.format_report(symbol=sym)
        assert "FactorEvaluator Report" in report
        assert f"Symbol: {sym}" in report

    def test_horizon_delays_realization(self):
        ee = EventEngine()
        ev = FactorEvaluator(horizon=50, enable_store=False, max_store=0)
        ev.start(ee)

        sym = "ETH-USDT-SWAP"

        ee.put(
            OKXBookticker(
                timestamp=1000,
                symbol=sym,
                bid_price_1=200.0,
                ask_price_1=200.2,
                bid_amount_1=1.0,
                ask_amount_1=1.0,
            )
        )

        f = FactorSignal(sym, 1.0, name="test_factor")
        f.timestamp = 1000
        ee.put(f)

        # Not enough horizon yet (1000+50=1050)
        ee.put(
            OKXBookticker(
                timestamp=1049,
                symbol=sym,
                bid_price_1=201.0,
                ask_price_1=201.2,
                bid_amount_1=1.0,
                ask_amount_1=1.0,
            )
        )

        counters = ev.get_symbol_stats(sym)["counters"]
        assert counters["evaluated"] == 0
        assert counters["pending"] == 1

        # First tick meeting horizon -> realize
        ee.put(
            OKXBookticker(
                timestamp=1050,
                symbol=sym,
                bid_price_1=201.0,
                ask_price_1=201.2,
                bid_amount_1=1.0,
                ask_amount_1=1.0,
            )
        )

        stats = ev.get_symbol_stats(sym)
        counters = stats["counters"]
        assert counters["evaluated"] == 1
        assert counters["pending"] == 0
        assert stats["delay"]["mean"] == pytest.approx(50.0)

    def test_skip_when_no_market_price(self):
        ee = EventEngine()
        ev = FactorEvaluator(horizon=0)
        ev.start(ee)

        sym = "SOL-USDT-SWAP"

        f = FactorSignal(sym, 1.0, name="test_factor")
        f.timestamp = 1000
        ee.put(f)

        stats = ev.get_symbol_stats(sym)
        counters = stats["counters"]
        assert counters["factor"] == 1
        assert counters["evaluated"] == 0
        assert counters["pending"] == 0
        assert counters["skipped_no_price"] == 1


if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))
