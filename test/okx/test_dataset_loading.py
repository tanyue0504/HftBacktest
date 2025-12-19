"""
pytest -s -v test/okx/test_dataset_loading.py
"""

import pytest
from datetime import datetime
from pathlib import Path
from itertools import product
from hft_backtest import CsvDataset, ParquetDataset
from hft_backtest.okx.event import OKXTrades, OKXBookticker, OKXFundingRate, OKXDelivery

# --- 配置路径常量 ---
TRADES_PATH = "./test/okx/data/trades_2025-08-01.parquet"
BOOKTICKER_PATH = "/shared_dir/Tan/okex_L2_0801/QTUM-USDT-SWAP/okex-swap_book_snapshot_25_2025-08-01_QTUM-USDT-SWAP.csv.gz"
FUNDING_PATH = "./test/okx/data/okx_funding_rate.parquet"
DELIVERY_PATH = "./test/okx/data/delivery.parquet"

# --- 辅助函数：检查文件是否存在 ---
def file_missing(path_str):
    return not Path(path_str).exists()

@pytest.mark.skipif(file_missing(TRADES_PATH), reason=f"File not found: {TRADES_PATH}")
def test_okx_trades():
    print(f"\nTesting OKX Trades loading from {TRADES_PATH}...")
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
    
    count = 0
    dt1 = datetime.now()
    for _ in ds_trades:
        count += 1
        break
    dt2 = datetime.now()
    
    print(f"OKX Trades: Loaded {count} rows. Elapsed time: {dt2 - dt1}")
    assert count > 0, "Dataset should not be empty"

@pytest.mark.skipif(file_missing(BOOKTICKER_PATH), reason=f"File not found: {BOOKTICKER_PATH}")
def test_okx_bookticker():
    print(f"\nTesting OKX Bookticker loading from {BOOKTICKER_PATH}...")
    
    # 构造 25 档行情字段，顺序必须与 Event __init__ 对应
    book_fields = []
    for i in range(25):
        # 注意：这里生成的列名必须真实存在于 CSV/Parquet 文件中
        book_fields.extend([f"asks[{i}].price", f"asks[{i}].amount", f"bids[{i}].price", f"bids[{i}].amount"])
    
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
    
    count = 0
    dt1 = datetime.now()
    for _ in ds_bookticker:
        count += 1
        break
    dt2 = datetime.now()
    
    print(f"OKX Bookticker: Loaded {count} rows. Elapsed time: {dt2 - dt1}")
    assert count > 0, "Dataset should not be empty"

@pytest.mark.skipif(file_missing(FUNDING_PATH), reason=f"File not found: {FUNDING_PATH}")
def test_okx_fundingrate():
    print(f"\nTesting OKX FundingRate loading from {FUNDING_PATH}...")
    ds_funding = ParquetDataset(
        path="./test/okx/data/okx_funding_rate.parquet",
        event_type=OKXFundingRate,
        columns=[
            'funding_time',
            "symbol",
            "funding_rate",
        ],
    )
    
    count = 0
    dt1 = datetime.now()
    for _ in ds_funding:
        count += 1
        break
    dt2 = datetime.now()
    
    print(f"OKX FundingRate: Loaded {count} rows. Elapsed time: {dt2 - dt1}")
    assert count > 0, "Dataset should not be empty"

@pytest.mark.skipif(file_missing(DELIVERY_PATH), reason=f"File not found: {DELIVERY_PATH}")
def test_okx_delivery():
    print(f"\nTesting OKX Delivery loading from {DELIVERY_PATH}...")
    ds_delivery = ParquetDataset(
        path="./test/okx/data/delivery.parquet",
        event_type=OKXDelivery,
        columns=[
            'created_time',
            "symbol",
            "price",
        ],
    )
    
    count = 0
    dt1 = datetime.now()
    for _ in ds_delivery:
        count += 1
        break
    dt2 = datetime.now()
    
    print(f"OKX Delivery: Loaded {count} rows. Elapsed time: {dt2 - dt1}")
    assert count > 0, "Dataset should not be empty"