from hft_backtest import CsvDataset, ParquetDataset
from itertools import product
from datetime import datetime
from hft_backtest.dataset import MergedDataset
from hft_backtest.okx.event import OKXTrades, OKXBookticker, OKXFundingRate
from pathlib import Path
import pandas as pd

ds0 = ParquetDataset(
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
dt1 = datetime.now()
for data in ds0:
    # print(data)
    # break
    pass
dt2 = datetime.now()
print("Elapsed time:", dt2 - dt1)

renmae_dict = {
    f"{bidask}[{num - 1}].{priceamount}": f"{bidask}_{priceamount}_{num}"
    for bidask, priceamount, num in product(['bids', 'asks'], ['price', 'amount'], range(1, 26))
}

ds = CsvDataset(
    name="book_ticker",
    path="/shared_dir/Tan/okex_L2_0801/BTC-USDT-SWAP/okex-swap_book_snapshot_25_2025-08-01_BTC-USDT-SWAP.csv.gz",
    timecol="timestamp",
    event_type=OKXBookticker,
    compression="gzip",
    rename=renmae_dict,
)

dt1 = datetime.now()
for data in ds:
    # print(data)
    # break
    pass
dt2 = datetime.now()
print("Elapsed time:", dt2 - dt1)

ds2 = ParquetDataset(
    name="trades",
    path="./test/okx/data/trades_2025-08-01.parquet",
    timecol="created_time",
    event_type=OKXTrades,
    rename={"instrument_name":'symbol'},
)
dt1 = datetime.now()
for data in ds2:
    # print(data)
    # break
    pass
dt2 = datetime.now()
print("Elapsed time:", dt2 - dt1)

ds3 = ParquetDataset(
    name="funding_rate",
    path='./test/okx/data/okx_funding_rate.parquet',
    timecol="funding_time",
    event_type=OKXFundingRate,
    rename={"instrument_name":'symbol'},
)
dt1 = datetime.now()
for data in ds3:
    # print(data)
    # break
    pass
dt2 = datetime.now()
print("Elapsed time:", dt2 - dt1)

ds_list = []
for file in Path('/shared_dir/Tan/okex_L2_0801/').rglob('*.csv.gz'):
    ds_temp = CsvDataset(
        name="book_ticker",
        path=str(file),
        timecol="timestamp",
        event_type=OKXBookticker,
        compression="gzip",
        rename=renmae_dict,
    )
    ds_list.append(ds_temp)
ds4 = MergedDataset(*ds_list[:3])
dt1 = datetime.now()
for data in ds4:
    # print(data)
    # break
    pass
dt2 = datetime.now()
print("Elapsed time for merged dataset:", dt2 - dt1)