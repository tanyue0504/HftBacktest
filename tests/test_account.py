"""
Tests for account module.
"""

import unittest
from hft_backtest import Account, Position, MarketData, SimplePerformanceCalculator


class TestPosition(unittest.TestCase):
    """Test Position class."""
    
    def test_creation(self):
        """Test creating a position."""
        pos = Position('AAPL', 10, 150.0)
        self.assertEqual(pos.symbol, 'AAPL')
        self.assertEqual(pos.quantity, 10)
        self.assertEqual(pos.avg_price, 150.0)
    
    def test_update_new_position(self):
        """Test updating a new position."""
        pos = Position('AAPL')
        pos.update(10, 150.0)
        self.assertEqual(pos.quantity, 10)
        self.assertEqual(pos.avg_price, 150.0)
    
    def test_update_add_to_position(self):
        """Test adding to existing position."""
        pos = Position('AAPL', 10, 150.0)
        pos.update(5, 152.0)
        self.assertEqual(pos.quantity, 15)
        # Average price should be (10*150 + 5*152) / 15 = 150.67
        self.assertAlmostEqual(pos.avg_price, 150.666667, places=5)
    
    def test_update_close_position(self):
        """Test closing a position."""
        pos = Position('AAPL', 10, 150.0)
        pos.update(-10, 155.0)
        self.assertEqual(pos.quantity, 0)
    
    def test_get_pnl(self):
        """Test calculating P&L."""
        pos = Position('AAPL', 10, 150.0)
        pnl = pos.get_pnl(155.0)
        self.assertEqual(pnl, 50.0)  # 10 * (155 - 150)


class TestAccount(unittest.TestCase):
    """Test Account class."""
    
    def test_creation(self):
        """Test creating an account."""
        account = Account(100000.0)
        self.assertEqual(account.initial_capital, 100000.0)
        self.assertEqual(account.cash, 100000.0)
        self.assertEqual(len(account.positions), 0)
    
    def test_execute_buy_order(self):
        """Test executing a buy order."""
        account = Account(100000.0)
        account.execute_order('AAPL', 10, 150.0, commission=1.0)
        
        # Check cash: 100000 - 10*150 - 1 = 98499
        self.assertEqual(account.cash, 98499.0)
        
        # Check position
        pos = account.get_position('AAPL')
        self.assertEqual(pos.quantity, 10)
        self.assertEqual(pos.avg_price, 150.0)
    
    def test_execute_sell_order(self):
        """Test executing a sell order."""
        account = Account(100000.0)
        account.execute_order('AAPL', 10, 150.0, commission=1.0)
        account.execute_order('AAPL', -5, 155.0, commission=1.0)
        
        # Check cash: 100000 - 10*150 - 1 + 5*155 - 1 = 99273
        self.assertEqual(account.cash, 99273.0)
        
        # Check position
        pos = account.get_position('AAPL')
        self.assertEqual(pos.quantity, 5)
    
    def test_get_equity(self):
        """Test calculating equity."""
        account = Account(100000.0)
        account.execute_order('AAPL', 10, 150.0, commission=1.0)
        
        market_prices = {'AAPL': 155.0}
        equity = account.get_equity(market_prices)
        
        # Cash: 98499, Position value: 10*155 = 1550
        # Total: 100049
        self.assertEqual(equity, 100049.0)
    
    def test_on_market_data_with_performance_calculator(self):
        """Test that market data is pushed to performance calculator."""
        perf_calc = SimplePerformanceCalculator()
        account = Account(100000.0, performance_calculator=perf_calc)
        
        # Execute a trade
        account.execute_order('AAPL', 10, 150.0, commission=1.0)
        
        # Push market data
        data = MarketData(1.0, 'AAPL', 155.0, 1000)
        account.on_market_data(data)
        
        # Check that performance calculator received the data
        metrics = perf_calc.get_metrics()
        self.assertIsNotNone(metrics)
        self.assertEqual(metrics['num_trades'], 1)
        self.assertTrue(len(perf_calc.equity_curve) > 1)


class TestAccountPerformanceIntegration(unittest.TestCase):
    """Test integration between Account and PerformanceCalculator."""
    
    def test_performance_tracking(self):
        """Test that performance is tracked correctly through data pushes."""
        perf_calc = SimplePerformanceCalculator()
        account = Account(100000.0, performance_calculator=perf_calc)
        
        # Execute trades and push market data
        account.execute_order('AAPL', 10, 150.0, commission=1.0)
        
        data1 = MarketData(1.0, 'AAPL', 155.0, 1000)
        account.on_market_data(data1)
        
        data2 = MarketData(2.0, 'AAPL', 160.0, 1000)
        account.on_market_data(data2)
        
        # Get metrics
        metrics = perf_calc.get_metrics()
        
        # Check that we have tracked equity
        self.assertTrue(len(perf_calc.equity_curve) >= 2)
        
        # Final equity should reflect the position gain
        # Cash: 98499, Position: 10*160 = 1600, Total = 100099
        self.assertAlmostEqual(metrics['final_equity'], 100099.0, places=1)
        
        # Return should be positive
        self.assertGreater(metrics['total_return'], 0)


if __name__ == '__main__':
    unittest.main()
