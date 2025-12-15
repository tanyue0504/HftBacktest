from abc import abstractmethod, ABC
from hft_backtest import Component, EventEngine, Order

class Recorder(Component, ABC):
    """
    记录器基类
    负责记录交易流水(Trades)和定期快照(Snapshots)
    """
    def __init__(self, dir_path: str):
        self.dir_path = dir_path

    @abstractmethod
    def record_trade(self, order: Order):
        """记录成交明细"""
        pass

    @abstractmethod
    def record_snapshot(self):
        """执行一次快照记录"""
        pass
    
    # 子类需要实现 start/stop 方法来注册监听