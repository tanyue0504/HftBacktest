import pytest
from hft_backtest import Event, MergedDataset
# 移除 DataReader 的导入，MockDataset 不需要继承它
# from hft_backtest.reader import DataReader

class MockDataset:
    """
    模拟数据集，用于测试归并逻辑。
    实现标准的 Python 迭代器协议 (__iter__, __next__)。
    """
    def __init__(self, timestamps, source_id):
        self.timestamps = timestamps
        self.source_id = source_id
        self._iter = iter(timestamps)
        
    def __iter__(self):
        return self
        
    def __next__(self):
        try:
            ts = next(self._iter)
            # 构造 Event，设置 timestamp 和 source
            evt = Event(ts)
            evt.source = self.source_id
            return evt
        except StopIteration:
            raise StopIteration

def test_basic_merge():
    """测试基础归并逻辑：交叉时间戳"""
    # Source A: 10, 30, 50
    ds1 = MockDataset([10, 30, 50], source_id=1)
    # Source B: 20, 40, 60
    ds2 = MockDataset([20, 40, 60], source_id=2)
    
    # MergedDataset 会自动检测到 ds1/ds2 是 Python 对象，
    # 并将其包装在 PyDatasetWrapper 中
    merged = MergedDataset([ds1, ds2])
    
    events = list(merged)
    timestamps = [e.timestamp for e in events]
    sources = [e.source for e in events]
    
    # 验证时间戳顺序
    assert timestamps == [10, 20, 30, 40, 50, 60]
    # 验证来源
    assert sources == [1, 2, 1, 2, 1, 2]

def test_stability():
    """测试稳定性：相同时间戳，应按数据集传入顺序优先"""
    # Source A: 10, 20
    ds1 = MockDataset([10, 20], source_id=1)
    # Source B: 10, 20
    ds2 = MockDataset([10, 20], source_id=2)
    
    merged = MergedDataset([ds1, ds2])
    
    events = list(merged)
    # 预期顺序：10(src1), 10(src2), 20(src1), 20(src2)
    
    assert len(events) == 4
    
    assert events[0].timestamp == 10 and events[0].source == 1
    assert events[1].timestamp == 10 and events[1].source == 2
    
    assert events[2].timestamp == 20 and events[2].source == 1
    assert events[3].timestamp == 20 and events[3].source == 2

def test_biased_fast_path():
    """测试 Biased 优化：单数据源连续输出"""
    # Source A: 1, 2, 3, 4
    ds1 = MockDataset([1, 2, 3, 4], source_id=1)
    # Source B: 10
    ds2 = MockDataset([10], source_id=2)
    
    merged = MergedDataset([ds1, ds2])
    
    events = list(merged)
    timestamps = [e.timestamp for e in events]
    
    assert timestamps == [1, 2, 3, 4, 10]

def test_empty_handling():
    """测试空数据集处理"""
    ds1 = MockDataset([], source_id=1)
    ds2 = MockDataset([10, 20], source_id=2)
    
    merged = MergedDataset([ds1, ds2])
    
    events = list(merged)
    assert len(events) == 2
    assert events[0].timestamp == 10
    assert events[1].timestamp == 20

def test_all_empty():
    """测试全空数据集"""
    ds1 = MockDataset([], source_id=1)
    ds2 = MockDataset([], source_id=2)
    
    merged = MergedDataset([ds1, ds2])
    
    events = list(merged)
    assert len(events) == 0

if __name__ == "__main__":
    pytest.main(["-v", __file__])