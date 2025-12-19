import re
import pytest
from unittest.mock import MagicMock, ANY
from hft_backtest import EventEngine, Order, Event
from hft_backtest.account import Account
from hft_backtest.recorder import TradeRecorder, AccountRecorder

class TestTradeRecorder:
    
    @pytest.fixture
    def mock_components(self):
        account = MagicMock(spec=Account)
        engine = MagicMock(spec=EventEngine)
        return account, engine

    def test_lifecycle_and_header(self, tmp_path, mock_components):
        """测试文件创建、表头写入和关闭"""
        account, engine = mock_components
        file_path = tmp_path / "trades.csv"
        
        recorder = TradeRecorder(str(file_path), account)
        recorder.start(engine)
        
        # 验证注册监听
        engine.register.assert_called_with(Order, recorder.on_order)

        recorder.flush(flush_to_disk=True)
        
        # 验证文件创建和表头
        assert file_path.exists()
        with open(file_path, 'r') as f:
            header = f.readline()
            assert "timestamp,order_id,symbol,price,quantity,commission" in header
            
        recorder.stop()
        # 验证文件已关闭（通过尝试写入会报错，或者再次打开验证内容完整性）

    def test_buffering_logic(self, tmp_path, mock_components):
        """测试缓冲区机制：满额写入"""
        account, engine = mock_components
        file_path = tmp_path / "trades_buffer.csv"
        
        # 设置缓冲区大小为 2
        recorder = TradeRecorder(str(file_path), account, buffer_size=2)
        recorder.start(engine)
        
        # 1. 模拟第一个订单
        order1 = Order.create_limit("BTC-USDT", 1.0, 50000.0)
        order1.state = Order.ORDER_STATE_FILLED
        order1.timestamp = 1000
        order1.commission_fee = 5.0
        order1.filled_price = 50000.0
        
        recorder.on_order(order1)
        recorder.file.flush()
        assert len(recorder.buffer) == 0  # Header + 1 Record被刷入文件
        with open(file_path, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 2
            
        # 2. 模拟第二个订单 -> 触发写入
        order2 = Order.create_limit("BTC-USDT", 0.5, 50001.0)
        order2.state = Order.ORDER_STATE_FILLED
        order2.timestamp = 1001
        order2.commission_fee = 2.5
        order2.filled_price = 50001.0
        
        recorder.on_order(order2)
        assert len(recorder.buffer) == 1  # 1 Records

        recorder.flush(flush_to_disk=True)
        assert len(recorder.buffer) == 0  # 缓冲区已清空
        
        # 验证写入
        with open(file_path, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 3 # Header + 2 Records
            assert "1000,1,BTC-USDT,50000.0,1.0,5.0" in lines[1]
            assert "1001,2,BTC-USDT,50001.0,0.5,2.5" in lines[2]
            
        recorder.stop()

    def test_flush_on_stop(self, tmp_path, mock_components):
        """测试 Stop 时强制刷新缓冲区"""
        account, engine = mock_components
        file_path = tmp_path / "trades_flush.csv"
        
        recorder = TradeRecorder(str(file_path), account, buffer_size=100)
        recorder.start(engine)
        
        order = Order.create_market("ETH-USDT", 1.0)
        order.state = Order.ORDER_STATE_FILLED
        order.filled_price = 3000.0
        order.order_id = 1
        order.timestamp = 2000
        recorder.on_order(order)
        
        # 此时未写入
        with open(file_path, 'r') as f:
            assert len(f.readlines()) == 0
            
        # Stop -> Flush
        recorder.stop()
        
        with open(file_path, 'r') as f:
            assert len(f.readlines()) == 2


class TestAccountRecorder:
    
    @pytest.fixture
    def mock_components(self):
        account = MagicMock(spec=Account)
        # 设置 Account 默认返回值
        account.get_equity.return_value = 10000.0
        account.get_balance.return_value = 5000.0
        account.get_total_commission.return_value = 0.0
        account.get_total_funding_fee.return_value = 0.0
        account.get_total_trade_pnl.return_value = 0.0
        account.get_total_trade_count.return_value = 0
        account.get_total_turnover.return_value = 0.0
        
        engine = MagicMock(spec=EventEngine)
        return account, engine

    def test_init_and_register(self, tmp_path, mock_components):
        account, engine = mock_components
        file_path = tmp_path / "account.csv"
        
        recorder = AccountRecorder(str(file_path), account, interval=1000)
        recorder.start(engine)
        
        # 验证注册全局监听
        engine.global_register.assert_called_with(recorder.on_event)
        
        # 验证表头
        recorder.flush(flush_to_disk=True)
        with open(file_path, 'r') as f:
            header = f.readline()
            assert "timestamp,equity,balance,commission,funding,pnl,trade_count,trade_amount" in header
            
        recorder.stop()

    def test_interval_logic(self, tmp_path, mock_components):
        """测试记录间隔逻辑"""
        account, engine = mock_components
        file_path = tmp_path / "account_interval.csv"
        
        # 间隔 1000ms
        recorder = AccountRecorder(str(file_path), account, interval=1000, buffer_size=3)
        recorder.start(engine)
        
        # T=500: 未达到间隔 (500 - 0 < 1000)
        event1 = Event(timestamp=500)
        recorder.on_event(event1)
        
        recorder.flush(flush_to_disk=True)
        with open(file_path, 'r') as f:
            assert len(f.readlines()) == 1 # 只有 Header
            
        # T=1200: 达到间隔 (1200 - 0 > 1000) -> 记录
        assert recorder.last_timestamp == 0
        assert recorder.current_timestamp == 500
        assert len(recorder.buffer) == 0
        event2 = Event(timestamp=1200)
        recorder.on_event(event2)
        assert recorder.last_timestamp == 1200
        assert recorder.current_timestamp == 1200
        assert len(recorder.buffer) == 1
        recorder.flush(flush_to_disk=True)
        with open(file_path, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 2
            assert lines[1].startswith("1200,")
        assert len(recorder.buffer) == 0
            
        # T=1500: 未达到间隔 (1500 - 1200 < 1000)
        event3 = Event(timestamp=1500)
        recorder.on_event(event3)
        
        recorder.flush(flush_to_disk=True)
        with open(file_path, 'r') as f:
            assert len(f.readlines()) == 2 # 依然是2行
            
        recorder.stop()

    def test_flow_calculation(self, tmp_path, mock_components):
        """测试流量字段（差分）的计算逻辑"""
        account, engine = mock_components
        file_path = tmp_path / "account_flow.csv"
        
        recorder = AccountRecorder(str(file_path), account, interval=1000, buffer_size=3)
        recorder.start(engine)
        
        # --- 第一次快照 (T=1000) ---
        # 模拟 Account 状态变化
        account.get_equity.return_value = 10100.0
        account.get_balance.return_value = 6000.0
        # 累计值
        account.get_total_commission.return_value = 5.0
        account.get_total_funding_fee.return_value = 2.0
        account.get_total_trade_pnl.return_value = 100.0
        account.get_total_trade_count.return_value = 1
        account.get_total_turnover.return_value = 50000.0
        
        recorder.on_event(Event(timestamp=1000))
        
        # 验证第一条记录 (Flow = Current - Initial(0))
        recorder.flush(flush_to_disk=True)
        with open(file_path, 'r') as f:
            line1 = f.readlines()[1].strip().split(',')
            # timestamp,equity,balance,commission,funding,pnl,trade_count,trade_amount
            assert line1[0] == "1000"
            assert float(line1[3]) == 5.0   # Commission Flow
            assert float(line1[4]) == 2.0   # Funding Flow
            assert float(line1[5]) == 100.0 # PnL Flow
            assert int(line1[6]) == 1       # Count Flow

        # --- 第二次快照 (T=2000) ---
        # 模拟更多交易
        account.get_total_commission.return_value = 8.0  # +3.0
        account.get_total_funding_fee.return_value = 2.0 # +0.0
        account.get_total_trade_pnl.return_value = 150.0 # +50.0
        account.get_total_trade_count.return_value = 3   # +2
        
        recorder.on_event(Event(timestamp=2000))

        recorder.flush(flush_to_disk=True)
        
        # 验证第二条记录 (Flow = Current - Previous)
        with open(file_path, 'r') as f:
            line2 = f.readlines()[2].strip().split(',')
            assert line2[0] == "2000"
            assert float(line2[3]) == 3.0   # 8.0 - 5.0
            assert float(line2[4]) == 0.0   # 2.0 - 2.0
            assert float(line2[5]) == 50.0  # 150.0 - 100.0
            assert int(line2[6]) == 2       # 3 - 1
            
        recorder.stop()

if __name__ == "__main__":
    import sys
    sys.exit(pytest.main(["-v", "-s", __file__]))