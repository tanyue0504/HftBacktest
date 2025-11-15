"""
Example demonstrating custom performance calculator implementation.

This shows how users can create their own performance calculators
with custom metrics that receive data pushes from the Account.
"""

from hft_backtest import (
    Dataset, MergedDataset, MarketData, Account, PerformanceCalculator
)


class SimpleDataset(Dataset):
    """Simple dataset for demonstration."""
    
    def __init__(self, symbol: str, data_points: list):
        self.symbol = symbol
        self.data_points = data_points
    
    def __iter__(self):
        for timestamp, price, volume in self.data_points:
            yield MarketData(timestamp, self.symbol, price, volume)
    
    def reset(self):
        pass


class WinRatePerformanceCalculator(PerformanceCalculator):
    """
    Custom performance calculator that tracks win rate and profit factor.
    
    This demonstrates how to implement a custom calculator that:
    1. Receives market data and position updates via on_market_data()
    2. Tracks trades via on_trade()
    3. Calculates custom metrics like win rate and profit factor
    """
    
    def __init__(self):
        """Initialize the calculator."""
        self.initial_capital = 0.0
        self.trades = []
        self.closed_trades = []  # Track completed trades
        self.open_positions = {}  # Track open positions per symbol
        
    def initialize(self, initial_capital: float):
        """Initialize with starting capital."""
        self.initial_capital = initial_capital
        
    def on_market_data(self, data: MarketData, position_quantity: float,
                      position_avg_price: float, cash: float):
        """
        Receive market data update.
        
        This is called for every market data tick, allowing us to track
        unrealized P&L and other real-time metrics.
        """
        # Store current position state
        self.open_positions[data.symbol] = {
            'quantity': position_quantity,
            'avg_price': position_avg_price,
            'current_price': data.price,
            'unrealized_pnl': position_quantity * (data.price - position_avg_price) if position_quantity != 0 else 0
        }
    
    def on_trade(self, symbol: str, quantity: float, price: float,
                commission: float, cash: float):
        """
        Receive trade notification.
        
        We use this to detect when positions are closed and calculate
        realized P&L for win rate calculation.
        """
        self.trades.append({
            'symbol': symbol,
            'quantity': quantity,
            'price': price,
            'commission': commission,
            'timestamp': len(self.trades)
        })
        
        # Check if this trade closes a position
        if symbol in self.open_positions:
            prev_quantity = self.open_positions[symbol].get('quantity', 0)
            
            # If we're closing or reducing a position, calculate realized P&L
            if prev_quantity * quantity < 0:  # Opposite direction = closing
                avg_price = self.open_positions[symbol].get('avg_price', price)
                
                # Calculate P&L for the closed portion
                closed_quantity = min(abs(quantity), abs(prev_quantity))
                realized_pnl = closed_quantity * (price - avg_price) * (1 if prev_quantity > 0 else -1)
                realized_pnl -= commission
                
                self.closed_trades.append({
                    'symbol': symbol,
                    'quantity': closed_quantity,
                    'entry_price': avg_price,
                    'exit_price': price,
                    'pnl': realized_pnl,
                    'commission': commission
                })
    
    def get_metrics(self) -> dict:
        """Calculate custom performance metrics."""
        if not self.closed_trades:
            return {
                'num_trades': len(self.trades),
                'num_closed_trades': 0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'average_win': 0.0,
                'average_loss': 0.0
            }
        
        # Calculate wins and losses
        wins = [t['pnl'] for t in self.closed_trades if t['pnl'] > 0]
        losses = [abs(t['pnl']) for t in self.closed_trades if t['pnl'] < 0]
        
        num_wins = len(wins)
        num_losses = len(losses)
        total_trades = len(self.closed_trades)
        
        win_rate = (num_wins / total_trades * 100) if total_trades > 0 else 0.0
        
        total_wins = sum(wins) if wins else 0.0
        total_losses = sum(losses) if losses else 0.0
        
        profit_factor = (total_wins / total_losses) if total_losses > 0 else float('inf')
        
        avg_win = (total_wins / num_wins) if num_wins > 0 else 0.0
        avg_loss = (total_losses / num_losses) if num_losses > 0 else 0.0
        
        return {
            'num_trades': len(self.trades),
            'num_closed_trades': total_trades,
            'num_wins': num_wins,
            'num_losses': num_losses,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_profit': total_wins,
            'total_loss': total_losses,
            'net_profit': total_wins - total_losses,
            'average_win': avg_win,
            'average_loss': avg_loss,
        }


def main():
    """Run example with custom performance calculator."""
    
    # Create sample data
    dataset = SimpleDataset('AAPL', [
        (1.0, 150.0, 1000),
        (2.0, 151.0, 1200),
        (3.0, 152.0, 1100),
        (4.0, 151.0, 1300),
        (5.0, 153.0, 1400),
        (6.0, 152.5, 1200),
        (7.0, 154.0, 1500),
        (8.0, 153.5, 1300),
    ])
    
    # Create custom performance calculator
    perf_calc = WinRatePerformanceCalculator()
    
    # Create account with custom calculator
    account = Account(initial_capital=100000.0, performance_calculator=perf_calc)
    
    print("Running backtest with custom performance calculator")
    print("=" * 60)
    
    # Simple strategy: buy low, sell high
    position_open = False
    
    for data in dataset:
        # Push data to account (which pushes to our custom calculator)
        account.on_market_data(data)
        
        print(f"Time {data.timestamp}: {data.symbol} @ ${data.price}")
        
        # Strategy: Buy at 150-151, Sell at 153-154
        if not position_open and data.price <= 151.0:
            account.execute_order(data.symbol, 100, data.price, commission=2.0)
            position_open = True
            print(f"  -> BUY 100 shares @ ${data.price}")
            
        elif position_open and data.price >= 153.0:
            account.execute_order(data.symbol, -100, data.price, commission=2.0)
            position_open = False
            print(f"  -> SELL 100 shares @ ${data.price}")
    
    # Get custom metrics
    print("\n" + "=" * 60)
    print("Custom Performance Metrics:")
    print("=" * 60)
    
    metrics = perf_calc.get_metrics()
    
    print(f"Total Trades: {metrics['num_trades']}")
    print(f"Closed Trades: {metrics['num_closed_trades']}")
    print(f"Number of Wins: {metrics['num_wins']}")
    print(f"Number of Losses: {metrics['num_losses']}")
    print(f"Win Rate: {metrics['win_rate']:.2f}%")
    print(f"Profit Factor: {metrics['profit_factor']:.2f}")
    print(f"Total Profit: ${metrics['total_profit']:.2f}")
    print(f"Total Loss: ${metrics['total_loss']:.2f}")
    print(f"Net Profit: ${metrics['net_profit']:.2f}")
    print(f"Average Win: ${metrics['average_win']:.2f}")
    print(f"Average Loss: ${metrics['average_loss']:.2f}")
    
    print("\n" + "=" * 60)
    print("Key Insight:")
    print("=" * 60)
    print("The custom performance calculator receives data pushes from Account,")
    print("enabling it to track custom metrics like win rate and profit factor")
    print("without needing to query positions or access data sources directly.")


if __name__ == "__main__":
    main()
