"""
Account management for the backtesting engine.
"""

from typing import Dict, Optional
from .dataset import MarketData
from .performance import PerformanceCalculator


class Position:
    """Represents a position in a single instrument."""
    
    def __init__(self, symbol: str, quantity: float = 0.0, avg_price: float = 0.0):
        """
        Initialize a position.
        
        Args:
            symbol: Trading symbol/instrument
            quantity: Number of units held (positive for long, negative for short)
            avg_price: Average entry price
        """
        self.symbol = symbol
        self.quantity = quantity
        self.avg_price = avg_price
    
    def update(self, quantity_change: float, price: float):
        """
        Update position with a new trade.
        
        Args:
            quantity_change: Change in quantity (positive for buy, negative for sell)
            price: Execution price
        """
        if self.quantity * quantity_change < 0:
            # Position reversal or closing
            if abs(quantity_change) >= abs(self.quantity):
                # Full close or reversal
                remaining = quantity_change + self.quantity
                self.quantity = remaining
                self.avg_price = price if remaining != 0 else 0.0
            else:
                # Partial close
                self.quantity += quantity_change
        else:
            # Adding to position
            if self.quantity == 0:
                self.quantity = quantity_change
                self.avg_price = price
            else:
                total_cost = self.quantity * self.avg_price + quantity_change * price
                self.quantity += quantity_change
                self.avg_price = total_cost / self.quantity if self.quantity != 0 else 0.0
    
    def get_pnl(self, current_price: float) -> float:
        """
        Calculate unrealized P&L.
        
        Args:
            current_price: Current market price
            
        Returns:
            Unrealized profit/loss
        """
        return self.quantity * (current_price - self.avg_price)
    
    def __repr__(self):
        return f"Position(symbol={self.symbol}, quantity={self.quantity}, avg_price={self.avg_price})"


class Account:
    """
    Trading account that manages positions and integrates with PerformanceCalculator.
    
    The Account receives market data updates and pushes them to the PerformanceCalculator,
    solving the issue where performance calculation is impossible without data access.
    """
    
    def __init__(self, initial_capital: float = 100000.0, 
                 performance_calculator: Optional[PerformanceCalculator] = None):
        """
        Initialize account.
        
        Args:
            initial_capital: Starting capital
            performance_calculator: Optional performance calculator that will receive data updates
        """
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, Position] = {}
        self.performance_calculator = performance_calculator
        
        # Initialize performance calculator with starting capital
        if self.performance_calculator:
            self.performance_calculator.initialize(initial_capital)
    
    def get_position(self, symbol: str) -> Position:
        """
        Get position for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Position object (creates new one if doesn't exist)
        """
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol)
        return self.positions[symbol]
    
    def execute_order(self, symbol: str, quantity: float, price: float, commission: float = 0.0):
        """
        Execute an order.
        
        Args:
            symbol: Trading symbol
            quantity: Quantity to trade (positive for buy, negative for sell)
            price: Execution price
            commission: Trading commission/fees
        """
        # Update cash
        self.cash -= quantity * price + commission
        
        # Update position
        position = self.get_position(symbol)
        position.update(quantity, price)
        
        # Notify performance calculator of the trade
        if self.performance_calculator:
            self.performance_calculator.on_trade(symbol, quantity, price, commission, self.cash)
    
    def on_market_data(self, data: MarketData):
        """
        Process market data update.
        
        This method pushes market data to the PerformanceCalculator, enabling
        accurate performance tracking without requiring the calculator to query positions.
        
        Args:
            data: Market data update
        """
        if self.performance_calculator:
            # Get current position for this symbol
            position = self.positions.get(data.symbol)
            position_quantity = position.quantity if position else 0.0
            position_avg_price = position.avg_price if position else 0.0
            
            # Push data to performance calculator
            self.performance_calculator.on_market_data(
                data, 
                position_quantity, 
                position_avg_price,
                self.cash
            )
    
    def get_equity(self, market_prices: Dict[str, float]) -> float:
        """
        Calculate total equity.
        
        Args:
            market_prices: Dictionary of symbol -> current price
            
        Returns:
            Total account equity
        """
        equity = self.cash
        for symbol, position in self.positions.items():
            if symbol in market_prices and position.quantity != 0:
                equity += position.quantity * market_prices[symbol]
        return equity
    
    def get_portfolio_value(self, market_prices: Dict[str, float]) -> float:
        """
        Get total portfolio value (alias for get_equity).
        
        Args:
            market_prices: Dictionary of symbol -> current price
            
        Returns:
            Total portfolio value
        """
        return self.get_equity(market_prices)
    
    def __repr__(self):
        return f"Account(cash={self.cash:.2f}, positions={len(self.positions)})"
