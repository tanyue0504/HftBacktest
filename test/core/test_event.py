import pytest
import sys
from hft_backtest.event import Event

class TestEvent:
    def test_basic_initialization(self):
        """测试基本初始化"""
        ts = 1600000000
        e = Event(ts)
        assert e.timestamp == ts
        assert e.source == 0
        assert e.producer == 0

    def test_derive_basic(self):
        """测试 derive 方法的基本功能"""
        ts = 123456789
        e = Event(ts)
        e.source = 1
        e.producer = 2
        
        # 创建衍生对象
        e_derived = e.derive()
        
        # 检查字段是否重置
        assert e_derived.timestamp == 0
        assert e_derived.source == 0
        assert e_derived.producer == 0
        
        # 检查原对象未变
        assert e.timestamp == ts
        assert e.source == 1
        
        # 检查是否为不同对象
        assert e is not e_derived

    def test_comparison(self):
        """测试比较操作符 __lt__"""
        e1 = Event(100)
        e2 = Event(200)
        assert e1 < e2
        assert not (e2 < e1)

    @pytest.mark.xfail(reason="Event.derive() uses raw memcpy and ignores Python __dict__ attributes", strict=True)
    def test_python_subclass_attributes(self):
        """
        测试 Python 子类的属性处理
        预期失败：底层优化不支持 Python 动态属性 (__dict__)
        """
        class MyEvent(Event):
            def __init__(self, ts, payload):
                super().__init__(ts)
                self.payload = payload  # Python 对象

        data = {"key": "value"}
        e = MyEvent(100, data)
        
        e_derived = e.derive()
        
        # 如果代码支持 __dict__ 拷贝，这里应该通过
        # 但目前不支持，所以预期会抛出 AttributeError
        assert e_derived.payload is data

    @pytest.mark.xfail(reason="Event.derive() does not support dynamic attributes", strict=True)
    def test_memory_safety_stress(self):
        """
        压力测试：检测内存泄漏或非法访问
        预期失败：动态添加的 custom_list 无法被 derive 复制
        """
        class PayloadEvent(Event):
            pass

        # 创建大量对象并 derive
        for i in range(100):
            e = PayloadEvent(i)
            # 动态添加属性
            e.custom_list = [1, 2, 3] 
            e2 = e.derive()
            
            # 这里会报错，因为 custom_list 没有被拷过去
            assert e2.custom_list[0] == 1

if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))