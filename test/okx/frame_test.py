from hft_backtest import BacktestEngine, Strategy, Order, EventEngine, ParquetDataset, CsvDataset, EventPrinter
from hft_backtest.dataset import MergedDataset
from hft_backtest.okx.event import OKXBookticker, OKXTrades, OKXFundingRate, OKXDelivery
from datetime import datetime

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
        # "funding_rate", # price
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


if __name__ == "__main__":
    ds = MergedDataset(ds_trades, ds_bookticker, ds_funding, ds_delivery)
    backtest_engine = BacktestEngine(datasets=[ds], delay=100,start_timestamp=1754006400000, end_timestamp=1754092800000)
    event_printer = EventPrinter(event_types=[OKXTrades, OKXBookticker, OKXFundingRate, OKXDelivery], tips="[OKX Event]")
    backtest_engine.add_component(event_printer, is_server=True)
    backtest_engine.run()
