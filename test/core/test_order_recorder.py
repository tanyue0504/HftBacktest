import pytest
import os
from unittest.mock import MagicMock
from hft_backtest import OrderRecorder, Order, Account, EventEngine
import sys

# ============================
# OrderRecorder 测试
# ============================
class TestOrderRecorder:
    
    @pytest.fixture
    def mock_components(self):
        # OrderRecorder 初始化需要 Account，但实际上它并不调用 Account 的方法
        # 这里使用 MagicMock 即可
        account = MagicMock(spec=Account)
        engine = MagicMock(spec=EventEngine)
        return account, engine

    def test_init_creates_header(self, tmp_path, mock_components):
        """测试初始化是否创建文件并写入正确的 Order 表头"""
        account, engine = mock_components
        file_path = tmp_path / "orders_init.csv"
        
        recorder = OrderRecorder(str(file_path), account)
        recorder.start(engine)
        
        # 手动 flush 以便检查文件内容
        recorder.flush(flush_to_disk=True)
        
        assert file_path.exists()
        
        # 检查表头字段
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            header = f.readline().strip()
            expected_header = "timestamp,order_id,symbol,type,state,price,quantity,filled_price,commission"
            assert header == expected_header
        
        recorder.stop()

    def test_records_all_states(self, tmp_path, mock_components):
        """测试核心逻辑：OrderRecorder 应记录所有状态的订单，不做过滤"""
        account, engine = mock_components
        file_path = tmp_path / "orders_lifecycle.csv"
        
        recorder = OrderRecorder(str(file_path), account)
        recorder.start(engine)
        
        # 1. 创建一个新订单 (State: CREATED)
        order1 = Order.create_limit("BTC-USDT", 1.0, 50000.0)
        order1.timestamp = 1000
        order1.order_id = 1
        order1.order_type = Order.ORDER_TYPE_LIMIT # 0
        order1.state = Order.ORDER_STATE_CREATED   # 0
        
        recorder.on_order(order1)
        
        # 2. 该订单被撤销 (State: CANCELED)
        # 模拟订单状态变更
        order1_canceled = Order(1, Order.ORDER_TYPE_LIMIT, "BTC-USDT", 1.0, 50000.0)
        order1_canceled.timestamp = 2000
        order1_canceled.state = Order.ORDER_STATE_CANCELED # 4
        
        recorder.on_order(order1_canceled)
        
        # 3. 另一个订单成交 (State: FILLED)
        order2 = Order.create_market("ETH-USDT", 0.5)
        order2.timestamp = 3000
        order2.order_id = 2
        order2.order_type = Order.ORDER_TYPE_MARKET # 1
        order2.state = Order.ORDER_STATE_FILLED     # 3
        order2.filled_price = 3000.0
        order2.commission_fee = 1.5
        
        recorder.on_order(order2)
        
        recorder.stop()
        
        # 读取并验证
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
            
            # 预期: Header + 3条记录
            assert len(lines) == 4
            
            # 检查第一条: CREATED
            row1 = lines[1].strip().split(',')
            assert row1[0] == '1000' # timestamp
            assert row1[1] == '1'    # id
            assert row1[4] == '0'    # state: CREATED
            
            # 检查第二条: CANCELED
            row2 = lines[2].strip().split(',')
            assert row2[0] == '2000'
            assert row2[1] == '1'    # same id
            assert row2[4] == '4'    # state: CANCELED
            
            # 检查第三条: FILLED
            row3 = lines[3].strip().split(',')
            assert row3[2] == 'ETH-USDT'
            assert row3[3] == '1'    # type: MARKET
            assert row3[4] == '3'    # state: FILLED
            assert float(row3[7]) == 3000.0 # filled_price
            assert float(row3[8]) == 1.5    # commission

    def test_buffering_logic(self, tmp_path, mock_components):
        """测试缓冲区自动刷新逻辑"""
        account, engine = mock_components
        file_path = tmp_path / "orders_buffer.csv"
        
        # 设置 buffer_size=3 (Header 占 1 行，也就是说再来 2 个订单就会触发 flush)
        recorder = OrderRecorder(str(file_path), account, buffer_size=3)
        recorder.start(engine)
        
        # 初始 buffer: [Header]
        assert len(recorder.buffer) == 1
        
        # Order 1
        o1 = Order.create_limit("A", 1, 1)
        recorder.on_order(o1)
        # buffer: [Header, O1] (len=2 < 3, 不 flush)
        assert len(recorder.buffer) == 2
        
        # Order 2
        o2 = Order.create_limit("B", 1, 1)
        recorder.on_order(o2)
        # buffer: [Header, O1, O2] (len=3 >= 3, 触发 flush)
        # flush 后 buffer 被清空
        assert len(recorder.buffer) == 0
        
        # Order 3
        o3 = Order.create_limit("C", 1, 1)
        recorder.on_order(o3)
        # buffer: [O3]
        assert len(recorder.buffer) == 1
        
        recorder.stop()
        
        # 验证文件内容
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
            assert len(lines) == 4 # Header + 3 orders

if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))