from turtle import end_fill
from hft_backtest import MergedDataset, ParquetDataset, CsvDataset, Strategy, EventEngine, BacktestEngine, TradeRecorder, AccountRecorder, Order
from hft_backtest.account import Account
from hft_backtest.okx.event import OKXTrades, OKXFundingRate, OKXBookticker, OKXDelivery
from hft_backtest.okx.account import OKXAccount
from hft_backtest.okx.matcher import OKXMatcher

from pathlib import Path

def get_ds():
    ds_trades = ParquetDataset(
        path="./test/okx/data/trades_2025-08-01.parquet",
        event_type=OKXTrades,
        columns=[
            'created_time',
            "instrument_name",
            "trade_id",
            "price",
            "size",
            "side",
        ],
    )

    book_fields = []
    for i in range(25):
        book_fields.extend([f"asks[{i}].price", f"asks[{i}].amount", f"bids[{i}].price", f"bids[{i}].amount",])
    ds_bookticker = CsvDataset(
        path='/shared_dir/Tan/okex_L2_0801/QTUM-USDT-SWAP/okex-swap_book_snapshot_25_2025-08-01_QTUM-USDT-SWAP.csv.gz',
        event_type=OKXBookticker,
        columns=[
            'timestamp',
            'exchange',
            'symbol',
            'local_timestamp',
        ] + book_fields,
        compression='gzip',
    )

    ds_funding = ParquetDataset(
        path="./test/okx/data/okx_funding_rate.parquet",
        event_type=OKXFundingRate,
        columns=[
            'funding_time',
            "symbol",
            "funding_rate",
            "funding_rate", # price
        ],
    )


    ds_delivery = ParquetDataset(
        path="./test/okx/data/delivery.parquet",
        event_type=OKXDelivery,
        columns=[
            'created_time',
            "symbol",
            "price",
        ],
    )

    return MergedDataset(ds_trades, ds_bookticker, ds_funding, ds_delivery)

class DemoStrategy(Strategy):
    def __init__(self, account: Account):
        super().__init__(account)
        self.flag = 0

    def on_trade(self, event: OKXTrades):
        print(f"Trade event: {event}")
        if self.flag == 0:
            order = Order.market_order('BTC-USDT-SWAP', 1)
            self.send_order(order)
            print(f"Created order: {order}")
            self.flag = 1
        if self.flag == 1:
            order = Order.limit_order('BTC-USDT-SWAP', -1, 115710)
            self.send_order(order)
            print(f"Created order: {order}")
            self.flag = 2
        

    def start(self, event_engine: EventEngine):
        self.event_engine = event_engine
        event_engine.register(OKXTrades, self.on_trade)

    def stop(self):
        pass

def main():
    ds = get_ds()
    matcher =OKXMatcher()
    account = OKXAccount(initial_balance=1000000)
    strategy = DemoStrategy(account=account)
    path = Path(__file__).parent.parent
    trader_recorder = TradeRecorder(path=path / "tmp/okx_trades_demo.csv", account=account)
    account_recorder = AccountRecorder(path=path / "tmp/okx_account_demo.csv", account=account, interval=1000)
    backtest_engine = BacktestEngine(datasets=[ds], delay=10)
    backtest_engine.add_component(matcher, is_server=True)
    backtest_engine.add_component(account, is_server=False)
    backtest_engine.add_component(strategy, is_server=False)
    backtest_engine.add_component(trader_recorder, is_server=False)
    backtest_engine.add_component(account_recorder, is_server=False)
    backtest_engine.run()

if __name__ == "__main__":
    main()