"""
Dataset classes for providing market data to the backtesting engine.
"""

from abc import ABC, abstractmethod
from typing import Iterator, List
import heapq


class MarketData:
    """Represents a single market data tick."""
    
    def __init__(self, timestamp: float, symbol: str, price: float, volume: float, **kwargs):
        """
        Initialize market data.
        
        Args:
            timestamp: Unix timestamp of the data point
            symbol: Trading symbol/instrument
            price: Price at this tick
            volume: Volume at this tick
            **kwargs: Additional fields (bid, ask, etc.)
        """
        self.timestamp = timestamp
        self.symbol = symbol
        self.price = price
        self.volume = volume
        self.extra = kwargs
    
    def __lt__(self, other):
        """Compare by timestamp for ordering."""
        return self.timestamp < other.timestamp
    
    def __repr__(self):
        return f"MarketData(timestamp={self.timestamp}, symbol={self.symbol}, price={self.price}, volume={self.volume})"


class Dataset(ABC):
    """
    Abstract base class for market data sources.
    
    Users should inherit from this class to implement custom data sources.
    """
    
    @abstractmethod
    def __iter__(self) -> Iterator[MarketData]:
        """
        Iterate over market data in chronological order.
        
        Yields:
            MarketData: Market data ticks in time order
        """
        pass
    
    @abstractmethod
    def reset(self):
        """Reset the dataset to the beginning."""
        pass


class MergedDataset(Dataset):
    """
    Merges multiple datasets into a single chronologically ordered stream.
    
    This class aggregates data from multiple sources and yields them in
    timestamp order, which is essential for accurate backtesting when
    trading multiple instruments or using multiple data sources.
    """
    
    def __init__(self, datasets: List[Dataset]):
        """
        Initialize merged dataset.
        
        Args:
            datasets: List of Dataset instances to merge
        """
        self.datasets = datasets
        self._iterators = []
    
    def __iter__(self) -> Iterator[MarketData]:
        """
        Iterate over merged data in chronological order.
        
        Uses a heap to efficiently merge sorted streams.
        
        Yields:
            MarketData: Market data ticks from all datasets in time order
        """
        # Create iterators for all datasets
        self._iterators = [iter(dataset) for dataset in self.datasets]
        
        # Initialize heap with first element from each iterator
        heap = []
        for idx, it in enumerate(self._iterators):
            try:
                data = next(it)
                heapq.heappush(heap, (data.timestamp, idx, data))
            except StopIteration:
                pass
        
        # Merge streams using heap
        while heap:
            timestamp, idx, data = heapq.heappop(heap)
            yield data
            
            # Try to get next element from the same iterator
            try:
                next_data = next(self._iterators[idx])
                heapq.heappush(heap, (next_data.timestamp, idx, next_data))
            except StopIteration:
                pass
    
    def reset(self):
        """Reset all underlying datasets."""
        for dataset in self.datasets:
            dataset.reset()
        self._iterators = []
