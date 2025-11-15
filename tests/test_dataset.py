"""
Tests for dataset module.
"""

import unittest
from hft_backtest import Dataset, MergedDataset, MarketData


class SimpleTestDataset(Dataset):
    """Simple dataset for testing."""
    
    def __init__(self, data_points):
        self.data_points = data_points
    
    def __iter__(self):
        for timestamp, symbol, price, volume in self.data_points:
            yield MarketData(timestamp, symbol, price, volume)
    
    def reset(self):
        pass


class TestMarketData(unittest.TestCase):
    """Test MarketData class."""
    
    def test_creation(self):
        """Test creating market data."""
        data = MarketData(1.0, 'AAPL', 150.0, 1000)
        self.assertEqual(data.timestamp, 1.0)
        self.assertEqual(data.symbol, 'AAPL')
        self.assertEqual(data.price, 150.0)
        self.assertEqual(data.volume, 1000)
    
    def test_comparison(self):
        """Test comparing market data by timestamp."""
        data1 = MarketData(1.0, 'AAPL', 150.0, 1000)
        data2 = MarketData(2.0, 'AAPL', 151.0, 1000)
        self.assertTrue(data1 < data2)
        self.assertFalse(data2 < data1)
    
    def test_extra_fields(self):
        """Test extra fields in market data."""
        data = MarketData(1.0, 'AAPL', 150.0, 1000, bid=149.9, ask=150.1)
        self.assertEqual(data.extra['bid'], 149.9)
        self.assertEqual(data.extra['ask'], 150.1)


class TestMergedDataset(unittest.TestCase):
    """Test MergedDataset class."""
    
    def test_merge_two_datasets(self):
        """Test merging two datasets."""
        dataset1 = SimpleTestDataset([
            (1.0, 'AAPL', 150.0, 1000),
            (3.0, 'AAPL', 152.0, 1000),
            (5.0, 'AAPL', 153.0, 1000),
        ])
        
        dataset2 = SimpleTestDataset([
            (2.0, 'GOOGL', 2800.0, 500),
            (4.0, 'GOOGL', 2810.0, 500),
        ])
        
        merged = MergedDataset([dataset1, dataset2])
        
        results = list(merged)
        self.assertEqual(len(results), 5)
        
        # Check order
        self.assertEqual(results[0].timestamp, 1.0)
        self.assertEqual(results[0].symbol, 'AAPL')
        self.assertEqual(results[1].timestamp, 2.0)
        self.assertEqual(results[1].symbol, 'GOOGL')
        self.assertEqual(results[2].timestamp, 3.0)
        self.assertEqual(results[2].symbol, 'AAPL')
        self.assertEqual(results[3].timestamp, 4.0)
        self.assertEqual(results[3].symbol, 'GOOGL')
        self.assertEqual(results[4].timestamp, 5.0)
        self.assertEqual(results[4].symbol, 'AAPL')
    
    def test_merge_empty_dataset(self):
        """Test merging with empty dataset."""
        dataset1 = SimpleTestDataset([
            (1.0, 'AAPL', 150.0, 1000),
        ])
        dataset2 = SimpleTestDataset([])
        
        merged = MergedDataset([dataset1, dataset2])
        results = list(merged)
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].symbol, 'AAPL')
    
    def test_merge_single_dataset(self):
        """Test merging a single dataset."""
        dataset = SimpleTestDataset([
            (1.0, 'AAPL', 150.0, 1000),
            (2.0, 'AAPL', 151.0, 1000),
        ])
        
        merged = MergedDataset([dataset])
        results = list(merged)
        
        self.assertEqual(len(results), 2)


if __name__ == '__main__':
    unittest.main()
