import pytest
import sys
from hft_backtest.event import Event
from hft_backtest.reader import DataReader, PyDatasetWrapper
from hft_backtest.merged_dataset import MergedDataset

# 辅助函数：生成简单的 Event 列表
def create_events(timestamps, source_id=0):
    events = []
    for ts in timestamps:
        e = Event(ts)
        e.source = source_id # 借用 source 字段来标记来源，验证稳定性
        events.append(e)
    return events

class TestMergedDataset:
    def test_basic_merge(self):
        """测试基本的合并逻辑"""
        # Source 0: 1, 3, 5
        ds1 = create_events([1, 3, 5], source_id=0)
        # Source 1: 2, 4, 6
        ds2 = create_events([2, 4, 6], source_id=1)
        
        # 注意：根据 .pyx 实现，必须传入 list
        merged = MergedDataset([ds1, ds2])
        
        result = list(merged)
        timestamps = [e.timestamp for e in result]
        
        assert timestamps == [1, 2, 3, 4, 5, 6]
        # 验证总数
        assert len(result) == 6

    def test_stability(self):
        """测试排序稳定性：相同时间戳，靠前的源优先"""
        # Source 0: 10, 20
        ds1 = create_events([10, 20], source_id=0)
        # Source 1: 10, 20
        ds2 = create_events([10, 20], source_id=1)
        
        merged = MergedDataset([ds1, ds2])
        result = list(merged)
        
        # 预期顺序: 10(s0), 10(s1), 20(s0), 20(s1)
        assert len(result) == 4
        assert result[0].timestamp == 10 and result[0].source == 0
        assert result[1].timestamp == 10 and result[1].source == 1
        assert result[2].timestamp == 20 and result[2].source == 0
        assert result[3].timestamp == 20 and result[3].source == 1

    def test_empty_sources(self):
        """测试包含空源的情况"""
        ds1 = create_events([1, 5], source_id=0)
        ds2 = [] # 空源
        ds3 = create_events([2, 3], source_id=2)
        
        merged = MergedDataset([ds1, ds2, ds3])
        result = list(merged)
        
        timestamps = [e.timestamp for e in result]
        assert timestamps == [1, 2, 3, 5]

    def test_uneven_length(self):
        """测试长度不一致"""
        ds1 = create_events([1, 100], source_id=0)
        ds2 = create_events([2, 3, 4, 5, 6], source_id=1)
        
        merged = MergedDataset([ds1, ds2])
        timestamps = [e.timestamp for e in merged]
        
        assert timestamps == [1, 2, 3, 4, 5, 6, 100]

    def test_init_interface_behavior(self):
        """
        验证 __init__ 接口行为。
        目前的 .pyx 实现强制要求传入 list。
        如果传入多个参数（像 .pyi 暗示的那样），应该会报错。
        """
        ds1 = create_events([1])
        ds2 = create_events([2])
        
        # 尝试使用 varargs 调用 (如果 pyx 没改，这里会挂)
        with pytest.raises(TypeError):
            MergedDataset(ds1, ds2)
            
        # 正确用法
        try:
            MergedDataset([ds1, ds2])
        except TypeError:
            pytest.fail("MergedDataset should accept a list of datasets")

    def test_nested_readers(self):
        """测试传入的已经是 DataReader 的情况"""
        ds1 = create_events([1, 3])
        reader1 = PyDatasetWrapper(ds1)
        
        ds2 = create_events([2, 4])
        # reader2 也是 DataReader
        reader2 = PyDatasetWrapper(ds2)
        
        # MergedDataset 应该能识别它们已经是 Reader，不再二次包装
        merged = MergedDataset([reader1, reader2])
        timestamps = [e.timestamp for e in merged]
        assert timestamps == [1, 2, 3, 4]

if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))