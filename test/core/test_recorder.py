import pytest
from unittest.mock import MagicMock
from hft_backtest import TradeRecorder, Order, Account, EventEngine

class TestTradeRecorder:
    
    @pytest.fixture
    def mock_components(self):
        account = MagicMock(spec=Account)
        engine = MagicMock(spec=EventEngine)
        return account, engine

    def test_init_creates_header(self, tmp_path, mock_components):
        """测试初始化是否创建文件并写入表头"""
        account, engine = mock_components
        file_path = tmp_path / "trades_init.csv"
        
        recorder = TradeRecorder(str(file_path), account)
        recorder.start(engine)
        recorder.flush(flush_to_disk=True)
        
        assert file_path.exists()
        # 【修复】使用 utf-8-sig 读取，消除 BOM 差异
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            header = f.readline().strip()
            assert header == "timestamp,order_id,symbol,price,quantity,commission"
        
        recorder.stop()

    def test_on_order_logic(self, tmp_path, mock_components):
        account, engine = mock_components
        file_path = tmp_path / "trades_logic.csv"
        recorder = TradeRecorder(str(file_path), account)
        recorder.start(engine)
        
        assert len(recorder.buffer) == 1
        
        order_created = Order.create_limit("BTC-USDT", 1.0, 50000.0)
        recorder.on_order(order_created)
        assert len(recorder.buffer) == 1
        
        order_filled = Order.create_limit("BTC-USDT", 1.0, 50000.0)
        order_filled.state = Order.ORDER_STATE_FILLED
        order_filled.timestamp = 123456789
        order_filled.commission_fee = 0.001
        order_filled.filled_price = 50000.0
        
        recorder.on_order(order_filled)
        assert len(recorder.buffer) == 2
        assert str(order_filled.order_id) in recorder.buffer[1]
        
        recorder.stop()

    def test_buffering_logic(self, tmp_path, mock_components):
        account, engine = mock_components
        file_path = tmp_path / "trades_buffer.csv"
        
        recorder = TradeRecorder(str(file_path), account, buffer_size=2)
        recorder.start(engine)
        assert len(recorder.buffer) == 1 
        
        order1 = Order.create_limit("BTC-USDT", 1.0, 50000.0)
        order1.state = Order.ORDER_STATE_FILLED
        order1.timestamp = 1000
        order1.commission_fee = 5.0
        order1.filled_price = 50000.0
        
        recorder.on_order(order1)
        assert len(recorder.buffer) == 0
        
        order2 = Order.create_limit("BTC-USDT", 0.5, 50001.0)
        order2.state = Order.ORDER_STATE_FILLED
        order2.timestamp = 1001
        
        recorder.on_order(order2)
        assert len(recorder.buffer) == 1 
        
        recorder.stop()
        
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
            assert len(lines) == 3 
            assert f"{order1.order_id}" in lines[1]
            assert f"{order2.order_id}" in lines[2]