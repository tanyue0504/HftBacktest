"""
Performance calculation and tracking.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from .dataset import MarketData


class PerformanceCalculator(ABC):
    """
    Abstract base class for performance calculation.
    
    The key design principle is that the PerformanceCalculator receives data pushes
    from the Account, rather than querying positions. This solves the problem stated
    in the issue: without data access, accurate performance calculation is impossible.
    
    Users should inherit from this class to implement custom performance metrics.
    """
    
    @abstractmethod
    def initialize(self, initial_capital: float):
        """
        Initialize the calculator with starting capital.
        
        Args:
            initial_capital: Starting capital amount
        """
        pass
    
    @abstractmethod
    def on_market_data(self, data: MarketData, position_quantity: float, 
                      position_avg_price: float, cash: float):
        """
        Called when market data is updated.
        
        This method receives both market data and current position information,
        enabling accurate performance tracking without requiring position queries.
        
        Args:
            data: Market data update
            position_quantity: Current position quantity for this symbol
            position_avg_price: Average entry price for this position
            cash: Current cash balance
        """
        pass
    
    @abstractmethod
    def on_trade(self, symbol: str, quantity: float, price: float, 
                commission: float, cash: float):
        """
        Called when a trade is executed.
        
        Args:
            symbol: Trading symbol
            quantity: Quantity traded (positive for buy, negative for sell)
            price: Execution price
            commission: Trading commission/fees
            cash: Cash balance after trade
        """
        pass
    
    @abstractmethod
    def get_metrics(self) -> Dict:
        """
        Get performance metrics.
        
        Returns:
            Dictionary of performance metrics
        """
        pass


class SimplePerformanceCalculator(PerformanceCalculator):
    """
    Simple implementation of performance calculator.
    
    Tracks basic metrics like equity curve, returns, drawdown, etc.
    """
    
    def __init__(self):
        """Initialize calculator."""
        self.initial_capital = 0.0
        self.equity_curve: List[tuple] = []  # (timestamp, equity)
        self.trades: List[Dict] = []
        self.peak_equity = 0.0
        self.max_drawdown = 0.0
        self._last_prices: Dict[str, float] = {}
    
    def initialize(self, initial_capital: float):
        """Initialize with starting capital."""
        self.initial_capital = initial_capital
        self.peak_equity = initial_capital
        self.equity_curve = [(0, initial_capital)]
    
    def on_market_data(self, data: MarketData, position_quantity: float, 
                      position_avg_price: float, cash: float):
        """Process market data update and calculate current equity."""
        # Store latest price
        self._last_prices[data.symbol] = data.price
        
        # Calculate current equity
        equity = cash
        # Add value of this position
        if position_quantity != 0:
            equity += position_quantity * data.price
        
        # Store equity point
        self.equity_curve.append((data.timestamp, equity))
        
        # Update peak and drawdown
        if equity > self.peak_equity:
            self.peak_equity = equity
        
        current_drawdown = (self.peak_equity - equity) / self.peak_equity
        if current_drawdown > self.max_drawdown:
            self.max_drawdown = current_drawdown
    
    def on_trade(self, symbol: str, quantity: float, price: float, 
                commission: float, cash: float):
        """Record trade execution."""
        self.trades.append({
            'symbol': symbol,
            'quantity': quantity,
            'price': price,
            'commission': commission,
            'cash_after': cash
        })
    
    def get_metrics(self) -> Dict:
        """Calculate and return performance metrics."""
        if not self.equity_curve:
            return {}
        
        final_equity = self.equity_curve[-1][1]
        total_return = (final_equity - self.initial_capital) / self.initial_capital
        
        metrics = {
            'initial_capital': self.initial_capital,
            'final_equity': final_equity,
            'total_return': total_return,
            'total_return_pct': total_return * 100,
            'max_drawdown': self.max_drawdown,
            'max_drawdown_pct': self.max_drawdown * 100,
            'num_trades': len(self.trades),
            'peak_equity': self.peak_equity,
        }
        
        # Calculate Sharpe ratio if we have enough data
        if len(self.equity_curve) > 1:
            returns = []
            for i in range(1, len(self.equity_curve)):
                prev_equity = self.equity_curve[i-1][1]
                curr_equity = self.equity_curve[i][1]
                if prev_equity > 0:
                    ret = (curr_equity - prev_equity) / prev_equity
                    returns.append(ret)
            
            if returns:
                import statistics
                mean_return = statistics.mean(returns)
                if len(returns) > 1:
                    std_return = statistics.stdev(returns)
                    if std_return > 0:
                        # Annualized Sharpe ratio (assuming daily data)
                        sharpe = (mean_return / std_return) * (252 ** 0.5)
                        metrics['sharpe_ratio'] = sharpe
        
        return metrics
