from ast import Or
import test
from hft_backtest import CsvDataset, ParquetDataset
from itertools import product
from datetime import datetime
from hft_backtest.dataset import MergedDataset
from hft_backtest.okx.event import OKXTrades, OKXBookticker, OKXFundingRate, OKXDelivery
from pathlib import Path
import pandas as pd

import pyximport
pyximport.install()
from hft_backtest.event import Event
from hft_backtest.order import Order

def test_okx_trades():
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
    dt1 = datetime.now()
    for data in ds_trades:
        # print(data)
        # break
        pass
    dt2 = datetime.now()
    print("Elapsed time:", dt2 - dt1)

def test_okx_bookticker():
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
    dt1 = datetime.now()
    for data in ds_bookticker:
        # print(data)
        # break
        pass
    dt2 = datetime.now()
    print("Elapsed time:", dt2 - dt1)

def test_okx_fundingrate():
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
    dt1 = datetime.now()
    for data in ds_funding:
        # print(data)
        # break
        pass
    dt2 = datetime.now()
    print("Elapsed time:", dt2 - dt1)

def test_okx_fundingrate():
    ds_funding = ParquetDataset(
        path="./test/okx/data/okx_funding_rate.parquet",
        event_type=OKXFundingRate,
        columns=[
            'funding_time',
            "symbol",
            "funding_rate",
        ],
    )
    dt1 = datetime.now()
    for data in ds_funding:
        # print(data)
        # break
        pass
    dt2 = datetime.now()
    print("Elapsed time:", dt2 - dt1)

def test_okx_delivery():
    ds_delivery = ParquetDataset(
        path="./test/okx/data/delivery.parquet",
        event_type=OKXDelivery,
        columns=[
            'created_time',
            "symbol",
            "price",
        ],
    )
    dt1 = datetime.now()
    for data in ds_delivery:
        # print(data)
        # break
        pass
    dt2 = datetime.now()
    print("Elapsed time:", dt2 - dt1)

def test_cevent():
    ds_trades = ParquetDataset(
        path="./test/okx/data/trades_2025-08-01.parquet",
        event_type=Event,
        columns=[
            'created_time',
            # "instrument_name",
            # "trade_id",
            # "price",
            # "size",
            # "side",
        ],
    )
    dt1 = datetime.now()
    for data in ds_trades:
        # print(data)
        # break
        # data.derive()
        pass
    dt2 = datetime.now()
    print("Elapsed time:", dt2 - dt1)
    

if __name__ == "__main__":
    test_cevent()
    # test_okx_delivery()
    # test_okx_fundingrate()
    # test_okx_trades()
    # test_okx_bookticker()
    