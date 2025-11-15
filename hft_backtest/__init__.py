"""
HFT Backtest Framework

A simple high-frequency trading backtesting framework.
"""

__version__ = "0.1.0"

from .dataset import Dataset, MergedDataset, MarketData
from .account import Account, Position
from .performance import PerformanceCalculator, SimplePerformanceCalculator

__all__ = [
    "Dataset",
    "MergedDataset",
    "MarketData",
    "Account",
    "Position",
    "PerformanceCalculator",
    "SimplePerformanceCalculator",
]
