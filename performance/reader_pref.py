import pandas as pd
import numpy as np
from datetime import datetime
from hft_backtest.okx import OKXTrades, OKXBookticker
# 从新模块导入 (确保你已经编译了 python setup.py build_ext --inplace)
from hft_backtest.okx.reader import OKXTradesArrayReader, OKXBooktickerArrayReader

def test_performance():
    # ==============================================================================
    # Test 1: OKXTrades (6 列)
    # ==============================================================================
    print("=" * 60)
    print("🚀 [测试 1] OKXTrades (小对象，6列)")
    N = 10_000_000
    print(f"    - 数据量: {N:,} 行")
    print("    - 准备 DataFrame...")
    
    df_trades = pd.DataFrame({
        'created_time': np.arange(N, dtype=np.int64),
        'trade_id': np.arange(N, dtype=np.int64),
        'price': np.random.rand(N) * 10000,
        'size': np.random.rand(N),
        'instrument_name': ['BTC-USDT-SWAP'] * N,
        'side': ['buy'] * N
    })
    
    # --- 传统方式 ---
    print("\n[1.1] 传统 ParquetDataset (模拟: map + 迭代器)...")
    def old_iter_trades():
        # 模拟 ParquetDataset 中的 cols 提取过程
        cols = [df_trades[c].values for c in ['created_time', 'instrument_name', 'trade_id', 'price', 'size', 'side']]
        return map(OKXTrades, *cols)
    
    t1 = datetime.now()
    for _ in old_iter_trades():
        pass
    t2 = datetime.now()
    time_old_trades = (t2 - t1).total_seconds()
    print(f"    -> 耗时: {time_old_trades:.4f}s")
    
    # --- 新方式 ---
    print("\n[1.2] OKXTradesArrayReader (新扩展: C内存直读)...")
    # 实例化耗时也包含在内（虽然极快）
    t1 = datetime.now()
    reader_trades = OKXTradesArrayReader(df_trades)
    for _ in reader_trades:
        pass
    t2 = datetime.now()
    time_new_trades = (t2 - t1).total_seconds()
    print(f"    -> 耗时: {time_new_trades:.4f}s")
    
    print(f"\n⚡️ Trades 提速: {time_old_trades / time_new_trades:.1f}x")


    # ==============================================================================
    # Test 2: OKXBookticker (巨型对象，100+ 列)
    # ==============================================================================
    print("\n" + "=" * 60)
    print("🚀 [测试 2] OKXBookticker (大对象，25档深度，103列)")
    N_bt = 1_000_000  # 100万行，防止内存爆炸
    print(f"    - 数据量: {N_bt:,} 行 (列数多，注意内存)")
    print("    - 准备 DataFrame (包含25档 Ask/Bid)...")
    
    # 构造数据字典
    data_bt = {
        'timestamp': np.arange(N_bt, dtype=np.int64),
        'symbol': ['BTC-USDT-SWAP'] * N_bt,
        'local_timestamp': np.arange(N_bt, dtype=np.int64),
    }
    # 生成 1-25 档数据
    for i in range(1, 26):
        data_bt[f'ask_price_{i}'] = np.ones(N_bt, dtype=np.float64) * 10000
        data_bt[f'ask_amount_{i}'] = np.ones(N_bt, dtype=np.float64)
        data_bt[f'bid_price_{i}'] = np.ones(N_bt, dtype=np.float64) * 9000
        data_bt[f'bid_amount_{i}'] = np.ones(N_bt, dtype=np.float64)
    
    df_books = pd.DataFrame(data_bt)
    
    # --- 传统方式 ---
    print("\n[2.1] 传统 ParquetDataset (模拟: map + 103个参数解包)...")
    def old_iter_books():
        # 严格按照 OKXBookticker.__init__ 的顺序构建列列表
        # 顺序: timestamp, symbol, local_timestamp, ask_p1, ask_v1, bid_p1, bid_v1 ...
        cols = [
            df_books['timestamp'].values, 
            df_books['symbol'].values, 
            df_books['local_timestamp'].values
        ]
        for i in range(1, 26):
            cols.extend([
                df_books[f'ask_price_{i}'].values,
                df_books[f'ask_amount_{i}'].values,
                df_books[f'bid_price_{i}'].values,
                df_books[f'bid_amount_{i}'].values
            ])
        return map(OKXBookticker, *cols)

    t1 = datetime.now()
    for _ in old_iter_books():
        pass
    t2 = datetime.now()
    time_old_bt = (t2 - t1).total_seconds()
    print(f"    -> 耗时: {time_old_bt:.4f}s")
    
    # --- 新方式 ---
    print("\n[2.2] OKXBooktickerArrayReader (新扩展: 指针数组遍历)...")
    t1 = datetime.now()
    reader_books = OKXBooktickerArrayReader(df_books)
    for _ in reader_books:
        pass
    t2 = datetime.now()
    time_new_bt = (t2 - t1).total_seconds()
    print(f"    -> 耗时: {time_new_bt:.4f}s")

    print(f"\n⚡️ Bookticker 提速: {time_old_bt / time_new_bt:.1f}x")
    print("=" * 60)

if __name__ == "__main__":
    try:
        test_performance()
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        print("请确保已执行: python setup.py build_ext --inplace")