"""
pytest -s -v test/okx/test_merged_dataset.py
"""

import pytest
from datetime import datetime
from pathlib import Path
from hft_backtest import CsvDataset, ParquetDataset, MergedDataset
from hft_backtest.okx.event import OKXTrades, OKXBookticker

# --- 配置路径常量 (保持与 loading test 一致) ---
TRADES_PATH = "./test/okx/data/trades_2025-08-01.parquet"
BOOKTICKER_PATH = "/shared_dir/Tan/okex_L2_0801/QTUM-USDT-SWAP/okex-swap_book_snapshot_25_2025-08-01_QTUM-USDT-SWAP.csv.gz"

# --- 辅助函数 ---
def file_missing(path_str):
    return not Path(path_str).exists()

def get_trades_ds():
    """工厂函数：返回一个新的 Trades Dataset 实例"""
    return ParquetDataset(
        path=TRADES_PATH,
        event_type=OKXTrades,
        columns=[
            'created_time', "instrument_name", "trade_id", "price", "size", "side",
        ],
    )

def get_bookticker_ds():
    """工厂函数：返回一个新的 Bookticker Dataset 实例"""
    # 构造 25 档行情字段
    book_fields = []
    for i in range(25):
        book_fields.extend([f"asks[{i}].price", f"asks[{i}].amount", f"bids[{i}].price", f"bids[{i}].amount"])
    
    return CsvDataset(
        path=BOOKTICKER_PATH,
        event_type=OKXBookticker,
        columns=[
            'timestamp', 'exchange', 'symbol', 'local_timestamp',
        ] + book_fields,
        compression='gzip',
    )

@pytest.mark.skipif(file_missing(TRADES_PATH), reason=f"File not found: {TRADES_PATH}")
def test_overhead_single_source():
    """
    测试 1: MergedDataset 的纯开销测试
    对比 [直接迭代 Dataset] vs [MergedDataset(Dataset)] 的速度
    """
    print(f"\n{'='*20} Testing MergedDataset Overhead (Single Source) {'='*20}")
    
    # 1. Baseline: 直接迭代
    ds_direct = get_trades_ds()
    print("Running Direct Dataset iteration...")
    start_t = datetime.now()
    count_direct = 0
    for _ in ds_direct:
        count_direct += 1
    direct_time = (datetime.now() - start_t).total_seconds()
    
    # 2. Test: MergedDataset 迭代
    # 注意：MergedDataset 内部会有堆操作和 next() 调用的开销
    ds_merged = MergedDataset(get_trades_ds())
    print("Running MergedDataset iteration...")
    start_t = datetime.now()
    count_merged = 0
    for _ in ds_merged:
        count_merged += 1
    merged_time = (datetime.now() - start_t).total_seconds()
    
    # 3. 结果对比
    print(f"\n[Result Comparison]")
    print(f"Rows: {count_direct}")
    print(f"Direct Time : {direct_time:.4f} s ({count_direct/direct_time:.0f} rows/s)")
    print(f"Merged Time : {merged_time:.4f} s ({count_merged/merged_time:.0f} rows/s)")
    
    overhead = merged_time - direct_time
    overhead_pct = (overhead / direct_time) * 100
    print(f"Overhead    : {overhead:.4f} s (+{overhead_pct:.2f}%)")
    
    assert count_direct == count_merged, "Row count mismatch!"

@pytest.mark.skipif(file_missing(TRADES_PATH) or file_missing(BOOKTICKER_PATH), reason="Files missing")
def test_integration_multi_source():
    """
    测试 2: 多数据源集成测试
    测试 Trades + Bookticker 同时回放的性能
    """
    print(f"\n{'='*20} Testing Integrated Performance (Trades + Bookticker) {'='*20}")
    
    ds_trades = get_trades_ds()
    ds_book = get_bookticker_ds()

    start_t = datetime.now()
    count_direct = 0
    for _ in ds_trades:
        count_direct += 1
    direct_time1 = (datetime.now() - start_t).total_seconds()

    start_t = datetime.now()
    count_direct = 0
    for _ in ds_book:
        count_direct += 1
    direct_time2 = (datetime.now() - start_t).total_seconds()

    print(f"\n[Direct Dataset Iteration Results]")
    print(f"Trades Rows : {count_direct} in {direct_time1:.4f} s ({count_direct/direct_time1:.0f} rows/s)")
    print(f"Book Rows   : {count_direct} in {direct_time2:.4f} s ({count_direct/direct_time2:.0f} rows/s)")
    
    # 创建合并数据集
    ds_merged = MergedDataset(ds_trades, ds_book)
    
    print("Running MergedDataset (Multi-Source) iteration...")
    start_t = datetime.now()
    count = 0
    
    # 记录第一个和最后一个数据的时间戳，检查顺序
    first_ts = None
    last_ts = None
    
    for event in ds_merged:
        if count == 0:
            first_ts = event.timestamp
        last_ts = event.timestamp
        count += 1
        
        # 抽样检查顺序 (每 10万条检查一次，避免过度拖慢测试)
        if count % 100000 == 0:
            if last_ts < first_ts: # 简单的单调性检查
                 pytest.fail("Timestamp disorder detected!")

    total_time = (datetime.now() - start_t).total_seconds()
    
    print(f"\n[Result]")
    print(f"Total Rows  : {count}")
    print(f"Total Time  : {total_time:.4f} s")
    print(f"Throughput  : {count/total_time:.0f} events/s")
    
    if last_ts is not None and first_ts is not None:
        print(f"Data Range  : {datetime.fromtimestamp(first_ts/1e6)} -> {datetime.fromtimestamp(last_ts/1e6)}") # 假设微秒时间戳
    
    assert count > 0, "Dataset is empty"