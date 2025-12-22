from hft_backtest import MergedDataset, ParquetDataset, CsvDataset, Strategy, EventEngine, BacktestEngine, TradeRecorder, AccountRecorder, Order
from hft_backtest.helper import EventPrinter
from hft_backtest.delaybus import DelayBus, FixedDelayModel
from hft_backtest.account import Account
from hft_backtest.okx.event import OKXTrades, OKXFundingRate, OKXBookticker, OKXDelivery
from hft_backtest.okx.account import OKXAccount
from hft_backtest.okx.matcher import OKXMatcher
from hft_backtest.timer import Timer
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

    # 【修改 1】MergedDataset 接受列表参数
    return MergedDataset([ds_trades, ds_bookticker, ds_funding, ds_delivery])

class DemoStrategy(Strategy):
    def __init__(self, account: Account):
        super().__init__(account)
        self.flag = 0

    def on_trade(self, event: OKXTrades):
        # print(f"Trade event: {event}")
        if self.flag == 0:
            # 【修改 2】使用 create_market 工厂方法
            order = Order.create_market('BTC-USDT-SWAP', 1)
            self.send_order(order)
            print(f"Created order: {order}")
            self.flag = 1
        if self.flag == 1:
            # 【修改 3】使用 create_limit 工厂方法
            order = Order.create_limit('BTC-USDT-SWAP', -1, 115710)
            self.send_order(order)
            print(f"Created order: {order}")
            self.flag = 2

    def on_order(self, order: Order):
        if self.flag == 2:
            if not self.account.get_orders() and not self.account.get_positions():
                print("All orders filled and positions closed. Stopping strategy.")
                raise RuntimeError("Stop Strategy")

    def start(self, event_engine: EventEngine):
        self.event_engine = event_engine
        event_engine.register(OKXTrades, self.on_trade)
        event_engine.register(Order, self.on_order)

    def stop(self):
        pass

def main():
    ds = get_ds()

    matcher = OKXMatcher()
    account_client = OKXAccount(initial_balance=1000000)
    account_server = OKXAccount(initial_balance=1000000)
    strategy = DemoStrategy(account=account_client)
    
    path = Path(__file__).parent.parent
    trader_recorder = TradeRecorder(path=path / "tmp/okx_trades_demo.csv", account=account_server)
    
    # 【修复】AccountRecorder 移除 interval
    account_recorder = AccountRecorder(path=path / "tmp/okx_account_demo.csv", account=account_server, interval=5 * 60 * 1000)
    
    delay_model_server = FixedDelayModel(delay=10)
    delay_model_client = FixedDelayModel(delay=10)
    server2client_bus = DelayBus(delay_model_server)
    client2server_bus = DelayBus(delay_model_client)

    # 监听 Trades 和 Order
    # 修改 demo.py 中的这一行
    # 加入 OKXFundingRate，这样第一条数据进去你就能看到
    # 如果想看 Timer 刷屏，也可以加入 Timer (hft_backtest.timer)
    event_printer = EventPrinter(tips="[Engine]", event_types=[OKXTrades, Order])
    
    backtest_engine = BacktestEngine(
        dataset=ds,
        server2client_delaybus=server2client_bus,
        client2server_delaybus=client2server_bus,
        timer_interval=1000
    )
    
    # Printer 加在 Server 端，这样能在数据刚进入引擎时就看到
    backtest_engine.add_component(event_printer, is_server=True)
    backtest_engine.add_component(matcher, is_server=True)
    backtest_engine.add_component(account_server, is_server=True)
    backtest_engine.add_component(trader_recorder, is_server=True)
    backtest_engine.add_component(account_recorder, is_server=True)
    
    backtest_engine.add_component(account_client, is_server=False)
    # 策略要放到最后，因为会通过raise来结束，其他组件需要先运行完，否则记录可能不会正常生成
    backtest_engine.add_component(strategy, is_server=False)
    
    
    backtest_engine.run()

if __name__ == "__main__":
    main()