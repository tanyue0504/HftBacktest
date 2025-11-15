"""
Simple example demonstrating the HFT backtesting framework.

This example shows:
1. Creating custom Dataset implementations
2. Merging multiple datasets
3. Using Account with PerformanceCalculator
4. Data being pushed to PerformanceCalculator for accurate calculations
"""

from hft_backtest import Dataset, MergedDataset, MarketData, Account, SimplePerformanceCalculator


class SimpleDataset(Dataset):
    """Example dataset that generates simple price data."""
    
    def __init__(self, symbol: str, data_points: list):
        """
        Initialize dataset.
        
        Args:
            symbol: Trading symbol
            data_points: List of (timestamp, price, volume) tuples
        """
        self.symbol = symbol
        self.data_points = data_points
        self.current_index = 0
    
    def __iter__(self):
        """Iterate over data points."""
        self.current_index = 0
        for timestamp, price, volume in self.data_points:
            yield MarketData(timestamp, self.symbol, price, volume)
    
    def reset(self):
        """Reset to beginning."""
        self.current_index = 0


def main():
    """Run a simple backtest example."""
    
    # Create datasets for two symbols
    dataset1 = SimpleDataset('AAPL', [
        (1.0, 150.0, 1000),
        (2.0, 151.0, 1200),
        (3.0, 152.0, 1100),
        (4.0, 151.5, 1300),
        (5.0, 153.0, 1400),
    ])
    
    dataset2 = SimpleDataset('GOOGL', [
        (1.5, 2800.0, 500),
        (2.5, 2810.0, 600),
        (3.5, 2805.0, 550),
        (4.5, 2815.0, 650),
    ])
    
    # Merge datasets
    merged_dataset = MergedDataset([dataset1, dataset2])
    
    # Create account with performance calculator
    perf_calc = SimplePerformanceCalculator()
    account = Account(initial_capital=100000.0, performance_calculator=perf_calc)
    
    print("Starting backtest with initial capital: $100,000")
    print("=" * 60)
    
    # Simple strategy: buy on first tick, sell on last tick
    has_position = {'AAPL': False, 'GOOGL': False}
    
    for data in merged_dataset:
        # Push data to account (which pushes to performance calculator)
        account.on_market_data(data)
        
        print(f"Time {data.timestamp}: {data.symbol} @ ${data.price}")
        
        # Simple strategy logic
        if not has_position[data.symbol] and data.timestamp <= 2.0:
            # Buy 10 shares
            quantity = 10
            account.execute_order(data.symbol, quantity, data.price, commission=1.0)
            has_position[data.symbol] = True
            print(f"  -> BUY {quantity} shares of {data.symbol} @ ${data.price}")
        
        elif has_position[data.symbol] and data.timestamp >= 4.0:
            # Sell all
            if data.symbol in account.positions:
                position = account.positions[data.symbol]
                if position.quantity > 0:
                    quantity_to_sell = position.quantity
                    account.execute_order(data.symbol, -quantity_to_sell, data.price, commission=1.0)
                    has_position[data.symbol] = False
                    print(f"  -> SELL {quantity_to_sell} shares of {data.symbol} @ ${data.price}")
    
    # Get performance metrics
    print("\n" + "=" * 60)
    print("Performance Metrics:")
    print("=" * 60)
    
    metrics = perf_calc.get_metrics()
    for key, value in metrics.items():
        if isinstance(value, float):
            print(f"{key}: {value:.2f}")
        else:
            print(f"{key}: {value}")
    
    print("\n" + "=" * 60)
    print(f"Final account state: {account}")
    print(f"Cash: ${account.cash:.2f}")
    
    for symbol, position in account.positions.items():
        if position.quantity != 0:
            print(f"Position: {position}")


if __name__ == "__main__":
    main()
