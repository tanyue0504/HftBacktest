import pytest
import os
import tempfile
from unittest.mock import MagicMock
from hft_backtest import TradeRecorder, AccountRecorder, Order, Account, EventEngine, Timer
import sys

# ============================
# 辅助 Mock 类 (用于集成测试)
# ============================
class MockAccount(Account):
    """用于测试的 Mock 账户，实现了真实的数据接口"""
    def __init__(self):
        super().__init__()
        self.equity = 1000.0
        self.balance = 1000.0
        self.total_commission = 0.0
        self.total_turnover = 0.0
        self.total_trade_count = 0
        self.total_pnl = 0.0
        self.total_funding_fee = 0.0
        
    def on_order(self, order): pass
    def get_positions(self): return {}
    def get_orders(self): return {}
    def get_prices(self): return {}
    
    def get_balance(self): return self.balance
    def get_equity(self): return self.equity
    
    def get_total_commission(self): return self.total_commission
    def get_total_turnover(self): return self.total_turnover
    def get_total_funding_fee(self): return self.total_funding_fee
    def get_total_trade_pnl(self): return self.total_pnl
    def get_total_trade_count(self): return self.total_trade_count

# ============================
# TradeRecorder 测试
# ============================
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
        
        # start 应该已经写入表头到 buffer，但不一定 flush 到磁盘
        # 手动 flush 以便检查
        recorder.flush(flush_to_disk=True)
        
        assert file_path.exists()
        # 【关键】使用 utf-8-sig 读取以处理 BOM
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            header = f.readline().strip()
            assert header == "timestamp,order_id,symbol,price,quantity,commission"
        
        recorder.stop()

    def test_on_order_logic(self, tmp_path, mock_components):
        """测试订单过滤逻辑"""
        account, engine = mock_components
        file_path = tmp_path / "trades_logic.csv"
        recorder = TradeRecorder(str(file_path), account)
        recorder.start(engine)
        
        # 1. 未成交订单 -> 不记录
        order_created = Order.create_limit("BTC-USDT", 1.0, 50000.0)
        # buffer 只有 header
        assert len(recorder.buffer) == 1
        recorder.on_order(order_created)
        assert len(recorder.buffer) == 1
        
        # 2. 已成交订单 -> 记录
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
        """测试缓冲区自动刷新"""
        account, engine = mock_components
        file_path = tmp_path / "trades_buffer.csv"
        
        # 设置 buffer_size=2，意味着 header 占用 1 个，再来 1 个订单就满了(>=2)
        recorder = TradeRecorder(str(file_path), account, buffer_size=2)
        recorder.start(engine)
        
        # 当前 buffer: [Header]
        assert len(recorder.buffer) == 1 
        
        order1 = Order.create_limit("BTC-USDT", 1.0, 50000.0)
        order1.state = Order.ORDER_STATE_FILLED
        order1.order_id = 101
        
        # on_order 后 buffer: [Header, Order1]. len=2 >= buffer_size. 触发 flush.
        recorder.on_order(order1)
        assert len(recorder.buffer) == 0 # 已 flush
        
        order2 = Order.create_limit("BTC-USDT", 0.5, 50001.0)
        order2.state = Order.ORDER_STATE_FILLED
        order2.order_id = 102
        
        # on_order 后 buffer: [Order2]. len=1 < 2. 不 flush.
        recorder.on_order(order2)
        assert len(recorder.buffer) == 1 
        
        recorder.stop() # stop 触发强制 flush
        
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
            assert len(lines) == 3 
            assert "101" in lines[1]
            assert "102" in lines[2]

# ============================
# AccountRecorder 测试
# ============================
class TestAccountRecorder:
    
    def test_account_recorder_flows(self):
        """测试账户记录器：状态增量计算与时间间隔"""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            path = tmp.name
            
        try:
            acc = MockAccount()
            # 设置 buffer_size=1 确保每次 record 都有可能写入 (start 写入 header 后 flush)
            recorder = AccountRecorder(path, acc, interval=100, buffer_size=1)
            engine = EventEngine()
            
            recorder.start(engine)
            
            # T=0: 初始状态 (全0增量)
            # 应该触发记录，因为 last_timestamp 初始化为 -100
            engine.put(Timer(0))
            
            # T=50: 不足 interval (100)，应该跳过
            acc.equity = 1050.0
            engine.put(Timer(50))
            
            # T=100: 达到 interval，状态发生变化
            acc.equity = 1100.0        # +100 total
            acc.total_commission = 5.0 # +5
            acc.total_pnl = 105.0      # +105 (flow pnl)
            
            engine.put(Timer(100))
            
            # stop 会强制再记录一次 T=100 的状态 (作为结束快照)
            recorder.stop()
            
            # 验证
            with open(path, 'r', encoding='utf-8-sig') as f:
                lines = f.readlines()
            
            # 预期行数: 
            # 1. Header
            # 2. T=0
            # 3. T=100
            # 4. T=100 (Stop Force Record) - AccountRecorder.stop 默认行为是强制记录最后状态
            assert len(lines) >= 3
            
            # 检查 Header
            assert lines[0].startswith("timestamp,equity")
            
            # 检查 T0 Line: flow 应该是 0
            row0 = lines[1].strip().split(',')
            assert row0[0] == '0'
            assert float(row0[1]) == 1000.0 # initial equity
            assert float(row0[3]) == 0.0    # commission flow
            
            # 检查 T100 Line: 应该体现增量
            # 注意：T=50 的 1050.0 应该被跳过
            row1 = lines[2].strip().split(',')
            assert row1[0] == '100'
            assert float(row1[1]) == 1100.0 # current equity
            assert float(row1[3]) == 5.0    # commission flow (5 - 0)
            assert float(row1[5]) == 105.0  # pnl flow
            
        finally:
            if os.path.exists(path):
                os.remove(path)

if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))