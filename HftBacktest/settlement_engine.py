from event_engine import Event, EventEngine
from dataset import Data
import pandas as pd

class CalcFundingRate(Event):
    """
    资金费率结算事件
    timestamp: 结算时间戳 (int)
    funding_rate_dict: dict[str, float] 每个品种当前持仓应付（收）资金费
    """
    
    def __init__(
        self,
        timestamp:int,
        funding_rate_dict: dict[str, float],
    ):
        super().__init__(timestamp=timestamp)
        self.funding_rate_dict = funding_rate_dict

class SettlementEngine:
    """
    结算引擎
    1. 监听Data:fundingrate等结算数据事件触发资金费率等结算事件
    2. 发出Settlement事件， 结算资金费率
    """
    def __init__(
        self,
        event_engine: EventEngine,
    ):
        self.event_engine = event_engine
        # 注册监听
        event_engine.register(Data, self.on_data)

    def on_data(self, data: Data):
        # 仅处理资金费率数据
        if data.name != "funding_rate":
            return
        df: pd.DataFrame = data.data

        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert 'symbol' in df.columns
        assert 'funding_rate' in df.columns

        # 获取持仓和价格
        position_dict = self.event_engine.get_positions()
        price_dict = self.event_engine.get_prices()
        # 映射到df
        df['position'] = df['symbol'].map(position_dict)
        df['price'] = df['symbol'].map(price_dict)
        df['funding_fee'] = df['position'] * df['funding_rate'] * df['price']
        df = df[df['funding_fee'].abs() > 1e-8]  # 过滤无持仓的品种
        funding_rate_dict = df.set_index('symbol')['funding_fee'].to_dict()
        # 发出结算事件
        if funding_rate_dict:
            event = CalcFundingRate(
                timestamp=self.event_engine.timestamp,
                funding_rate_dict=funding_rate_dict,
            )
            self.event_engine.put(event)