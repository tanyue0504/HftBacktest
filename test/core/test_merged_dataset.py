# python test/core/test_merged_dataset.py
import pytest
from hft_backtest import Event
from hft_backtest.dataset import Dataset
from hft_backtest.merged_dataset import MergedDataset

# --- 简单的 Mock 数据集 ---
class MockDataset(Dataset):
    def __init__(self, timestamps, source_id):
        self.timestamps = timestamps
        self.source_id = source_id

    def __iter__(self):
        for ts in self.timestamps:
            evt = Event(timestamp=ts)
            # 这里的 source 只是为了验证数据来源，实际 MergedDataset 不会修改它
            evt.source = self.source_id 
            yield evt

def test_basic_merge():
    """测试基础归并逻辑：交叉时间戳"""
    # Source A: 10, 30, 50
    ds1 = MockDataset([10, 30, 50], source_id=1)
    # Source B: 20, 40, 60
    ds2 = MockDataset([20, 40, 60], source_id=2)
    
    merged = MergedDataset(ds1, ds2)
    result = list(merged)
    
    # 验证时间顺序
    timestamps = [e.timestamp for e in result]
    assert timestamps == [10, 20, 30, 40, 50, 60]
    
    # 验证来源交替
    sources = [e.source for e in result]
    assert sources == [1, 2, 1, 2, 1, 2]

def test_stability():
    """测试稳定性：相同时间戳，应按数据集传入顺序优先"""
    # Source A: 10, 20
    ds1 = MockDataset([10, 20], source_id=1)
    # Source B: 10, 20
    ds2 = MockDataset([10, 20], source_id=2)
    
    merged = MergedDataset(ds1, ds2)
    result = list(merged)
    
    timestamps = [e.timestamp for e in result]
    assert timestamps == [10, 10, 20, 20]
    
    # 关键：时间戳相同时，ds1 (index 0) 应该排在 ds2 (index 1) 前面
    sources = [e.source for e in result]
    assert sources == [1, 2, 1, 2]

def test_biased_fast_path():
    """测试 Biased 优化：单数据源连续输出"""
    # Source A: 1, 2, 3, 4
    ds1 = MockDataset([1, 2, 3, 4], source_id=1)
    # Source B: 10
    ds2 = MockDataset([10], source_id=2)
    
    merged = MergedDataset(ds1, ds2)
    result = list(merged)
    
    assert len(result) == 5
    assert result[-1].timestamp == 10
    
    # 这个测试主要验证代码没崩，因为 Fast Path 逻辑在 C 层面

def test_empty_handling():
    """测试空数据集处理"""
    ds1 = MockDataset([], source_id=1)
    ds2 = MockDataset([10, 20], source_id=2)
    
    merged = MergedDataset(ds1, ds2)
    result = list(merged)
    
    assert len(result) == 2
    assert result[0].timestamp == 10

if __name__ == "__main__":
    import sys
    sys.exit(pytest.main(["-v", __file__]))