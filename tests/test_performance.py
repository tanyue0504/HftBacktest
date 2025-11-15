"""
Tests for performance module.
"""

import unittest
from hft_backtest import SimplePerformanceCalculator, MarketData


class TestSimplePerformanceCalculator(unittest.TestCase):
    """Test SimplePerformanceCalculator class."""
    
    def test_initialization(self):
        """Test initializing calculator."""
        calc = SimplePerformanceCalculator()
        calc.initialize(100000.0)
        
        self.assertEqual(calc.initial_capital, 100000.0)
        self.assertEqual(calc.peak_equity, 100000.0)
        self.assertEqual(len(calc.equity_curve), 1)
    
    def test_on_trade(self):
        """Test recording trades."""
        calc = SimplePerformanceCalculator()
        calc.initialize(100000.0)
        
        calc.on_trade('AAPL', 10, 150.0, 1.0, 98499.0)
        
        self.assertEqual(len(calc.trades), 1)
        self.assertEqual(calc.trades[0]['symbol'], 'AAPL')
        self.assertEqual(calc.trades[0]['quantity'], 10)
    
    def test_on_market_data(self):
        """Test processing market data."""
        calc = SimplePerformanceCalculator()
        calc.initialize(100000.0)
        
        # Simulate buying 10 shares at 150
        cash_after_buy = 100000.0 - 10 * 150.0 - 1.0  # 98499
        
        # Market moves to 155
        data = MarketData(1.0, 'AAPL', 155.0, 1000)
        calc.on_market_data(data, position_quantity=10, position_avg_price=150.0, cash=cash_after_buy)
        
        # Equity should be cash + position value
        # 98499 + 10*155 = 100049
        self.assertAlmostEqual(calc.equity_curve[-1][1], 100049.0, places=1)
    
    def test_get_metrics(self):
        """Test calculating performance metrics."""
        calc = SimplePerformanceCalculator()
        calc.initialize(100000.0)
        
        # Simulate some trades and market data
        calc.on_trade('AAPL', 10, 150.0, 1.0, 98499.0)
        
        data1 = MarketData(1.0, 'AAPL', 155.0, 1000)
        calc.on_market_data(data1, 10, 150.0, 98499.0)
        
        data2 = MarketData(2.0, 'AAPL', 160.0, 1000)
        calc.on_market_data(data2, 10, 150.0, 98499.0)
        
        metrics = calc.get_metrics()
        
        self.assertIn('initial_capital', metrics)
        self.assertIn('final_equity', metrics)
        self.assertIn('total_return', metrics)
        self.assertIn('max_drawdown', metrics)
        self.assertIn('num_trades', metrics)
        
        self.assertEqual(metrics['initial_capital'], 100000.0)
        self.assertEqual(metrics['num_trades'], 1)
        self.assertGreater(metrics['final_equity'], 100000.0)
    
    def test_drawdown_calculation(self):
        """Test maximum drawdown calculation."""
        calc = SimplePerformanceCalculator()
        calc.initialize(100000.0)
        
        # Simulate equity going up then down
        data1 = MarketData(1.0, 'AAPL', 155.0, 1000)
        calc.on_market_data(data1, 10, 150.0, 98499.0)  # Equity: 100049
        
        data2 = MarketData(2.0, 'AAPL', 140.0, 1000)
        calc.on_market_data(data2, 10, 150.0, 98499.0)  # Equity: 99899
        
        metrics = calc.get_metrics()
        
        # Drawdown should be positive since equity went down from peak
        self.assertGreater(metrics['max_drawdown'], 0)


if __name__ == '__main__':
    unittest.main()
