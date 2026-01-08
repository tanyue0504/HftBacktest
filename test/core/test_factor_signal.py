import re
import sys

import pytest

from hft_backtest import FactorSignal


class TestFactorSignal:
	def test_basic_initialization(self):
		symbol = "BTC-USDT"
		value = 1.2345

		s = FactorSignal(symbol, value)

		assert s.timestamp == 0
		assert s.source == 0
		assert s.producer == 0
		assert s.symbol == symbol
		assert s.value == value

	def test_repr_format(self):
		s = FactorSignal("ETH-USDT", 12.0)
		text = repr(s)
		compact = "".join(text.split())

		assert "FactorSignal" in text
		assert "symbol='ETH-USDT'" in text
		assert "ts=0" in text
		assert re.search(r"value=12\.0000\b", compact) is not None

	def test_derive_resets_header_and_copies_fields(self):
		s = FactorSignal("SOL-USDT", 0.1)
		s.timestamp = 123
		s.source = 7
		s.producer = 9

		derived = s.derive()

		assert derived is not s
		assert isinstance(derived, FactorSignal)

		# header reset
		assert derived.timestamp == 0
		assert derived.source == 0
		assert derived.producer == 0

		# payload copied
		assert derived.symbol == s.symbol
		assert derived.value == s.value

		# independence
		derived.symbol = "SOL-USDT-PERP"
		derived.value = 999.0
		assert s.symbol == "SOL-USDT"
		assert s.value == pytest.approx(0.1)


if __name__ == "__main__":
	sys.exit(pytest.main(["-v", __file__]))
