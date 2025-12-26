import pytest
import sys
from hft_backtest.reader import PyDatasetWrapper, DataReader
from hft_backtest.event import Event

class TestReader:
    def test_wrap_list(self):
        """测试包装普通 Python 列表"""
        events = [Event(1), Event(2), Event(3)]
        reader = PyDatasetWrapper(events)
        
        # 验证是 DataReader 实例
        assert isinstance(reader, DataReader)
        
        # 验证迭代功能
        result = []
        for e in reader:
            result.append(e)
            
        assert len(result) == 3
        assert result[0].timestamp == 1
        assert result[2].timestamp == 3

    def test_wrap_generator(self):
        """测试包装生成器"""
        def gen():
            yield Event(100)
            yield Event(200)
            
        reader = PyDatasetWrapper(gen())
        
        e1 = next(reader)
        assert e1.timestamp == 100
        
        e2 = next(reader)
        assert e2.timestamp == 200
        
        with pytest.raises(StopIteration):
            next(reader)

    def test_invalid_type_handling(self):
        """测试当源数据包含非 Event 对象时"""
        # 传入一个包含整数的列表，而不是 Event
        data = [Event(1), 999] 
        reader = PyDatasetWrapper(data)
        
        # 第一个没事
        assert next(reader).timestamp == 1
        
        # 第二个应该报错，因为 <Event>999 会失败
        # Cython 类型转换通常会抛出 TypeError
        with pytest.raises(TypeError):
            next(reader)

    def test_source_exception(self):
        """测试源迭代器抛出异常"""
        def broken_gen():
            yield Event(1)
            raise ValueError("Data corrupt")
            
        reader = PyDatasetWrapper(broken_gen())
        
        next(reader) # skip first
        
        with pytest.raises(ValueError, match="Data corrupt"):
            next(reader)

    def test_subclass_fields_preservation(self):
        """
        测试：类型转换不会导致子类字段被截断 (Object Slicing)
        """
        # 1. 定义一个带额外字段的子类
        class OrderEvent(Event):
            def __init__(self, ts, order_id):
                super().__init__(ts)
                self.order_id = order_id  # 子类特有字段

        # 2. 创建子类实例
        original_evt = OrderEvent(100, "ORDER_001")
        
        # 3. 放入 Wrapper (它会通过 <Event?> 强转)
        reader = PyDatasetWrapper([original_evt])
        
        # 4. 取出
        # 在 Python 层，reader 是迭代器，__next__ 会调用 C 的 fetch_next
        retrieved_evt = next(reader)
        
        # 5. 验证
        # (1) 类型仍然是子类
        assert isinstance(retrieved_evt, OrderEvent)
        # (2) 父类字段还在
        assert retrieved_evt.timestamp == 100
        # (3) 子类字段还在 (证明没有截断)
        assert retrieved_evt.order_id == "ORDER_001"
        # (4) 对象身份一致 (证明是指针传递)
        assert retrieved_evt is original_evt

if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))