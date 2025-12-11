"""
基于溢价率的多空轮动策略

策略逻辑：
- 持仓规则：多头1个（溢价率最低），空头1个（溢价率最高）
- 平仓条件：
  1. 数据中没有该持仓币种时强行平仓
  2. 多头持仓的溢价率横截面排名 > 0.8 时平仓
  3. 空头持仓的溢价率横截面排名 < 0.2 时平仓
- 开仓条件：补充缺失方向的仓位

使用方法：
  python demo.py              # 运行全量回测
  python demo.py --max-rows 1000  # 只使用前1000行数据（快速测试）
"""

import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pyarrow import parquet as pq

from hft_backtest import Strategy, Data, Order, BacktestEngine
from hft_backtest.dataset import Dataset
from hft_backtest.low_freq import BarAccount, BarMatcher, BarRecorder


# =============================================================================
# 数据类（内嵌，不再依赖外部 dataset.py）
# =============================================================================

class BarParquetData(Dataset):
    """
    低频回测专用的 Parquet 数据集
    自动将 Timestamp 对象转换为毫秒级整数时间戳
    """

    def __init__(
        self,
        name: str,
        path: str,
        timecol: str,
        chunksize: int = 10**6,
        max_rows: int = 0,  # 0表示读取全部，>0表示只读取前N行
    ):
        super().__init__(name)
        self.path = path
        self.timecol = timecol
        self.chunksize = chunksize
        self.max_rows = max_rows

    def __iter__(self):
        pq_file = pq.ParquetFile(self.path)
        rows_yielded = 0

        for batch in pq_file.iter_batches(batch_size=self.chunksize):
            df = batch.to_pandas()

            # 如果设置了max_rows限制
            if self.max_rows > 0:
                remaining = self.max_rows - rows_yielded
                if remaining <= 0:
                    break
                if len(df) > remaining:
                    df = df.head(remaining)

            for line in df.itertuples(index=False):
                timestamp = getattr(line, self.timecol)
                # 转换 Timestamp 对象为毫秒整数
                if hasattr(timestamp, 'value'):
                    timestamp = int(timestamp.value / 1e6)
                yield Data(
                    timestamp=timestamp,
                    name=self.name,
                    data=line,
                )
                rows_yielded += 1


# =============================================================================
# 策略类
# =============================================================================

class PremiumRotationStrategy(Strategy):
    """基于溢价率的多空轮动策略"""

    def __init__(
        self,
        position_size: float = 10000.0,
        symbol_field: str = "symbol",
        premium_field: str = "premium",
        close_field: str = "close",
        verbose: bool = False,
    ):
        super().__init__()
        self.position_size = position_size
        self.symbol_field = symbol_field
        self.premium_field = premium_field
        self.close_field = close_field
        self.verbose = verbose

        self.latest_premium = {}
        self.latest_prices = {}
        self.last_execution_timestamp = None

    def on_data(self, data: Data):
        if data.name == "kline":
            self._update_kline(data)
            if self.last_execution_timestamp != data.timestamp:
                self.last_execution_timestamp = data.timestamp
                if self.verbose:
                    from datetime import datetime
                    dt = datetime.fromtimestamp(data.timestamp / 1000)
                    print(f"\n=== 执行策略 @ {dt} ===")
                self._execute_strategy()
        elif data.name == "premium":
            self._update_premium(data)

    def _update_kline(self, data: Data):
        line = data.data
        symbol = getattr(line, self.symbol_field, None)
        close = getattr(line, self.close_field, None)
        if symbol and close is not None:
            self.latest_prices[symbol] = close

    def _update_premium(self, data: Data):
        line = data.data
        symbol = getattr(line, self.symbol_field, None)
        premium = getattr(line, self.premium_field, None)
        if symbol and premium is not None:
            self.latest_premium[symbol] = premium

    def _execute_strategy(self):
        positions = self.event_engine.get_positions()
        pending_orders = self.event_engine.get_orders()

        if pending_orders:
            return

        premium_ranks = self._calculate_premium_ranks()
        if not premium_ranks:
            return

        current_long = None
        current_short = None
        for symbol, qty in positions.items():
            if qty > 0:
                current_long = symbol
            elif qty < 0:
                current_short = symbol

        if self._check_close_conditions(premium_ranks, positions, current_long, current_short):
            return
        self._check_open_conditions(premium_ranks, positions, current_long, current_short)

    def _calculate_premium_ranks(self) -> dict:
        if not self.latest_premium:
            return {}
        symbols = list(self.latest_premium.keys())
        premium_values = np.array([self.latest_premium[s] for s in symbols])
        ranks = {}
        n = len(symbols)
        if n <= 1:
            for s in symbols:
                ranks[s] = 0.5
        else:
            sorted_indices = np.argsort(premium_values)
            for i, idx in enumerate(sorted_indices):
                ranks[symbols[idx]] = i / (n - 1)
        return ranks

    def _check_close_conditions(self, premium_ranks, positions, current_long, current_short) -> bool:
        if current_long:
            should_close = False
            if current_long not in self.latest_premium:
                should_close = True
                if self.verbose:
                    print(f"[CLOSE LONG] {current_long}: 数据缺失")
            elif premium_ranks.get(current_long, 0) > 0.8:
                should_close = True
                if self.verbose:
                    print(f"[CLOSE LONG] {current_long}: 排名={premium_ranks[current_long]:.2%} > 80%")
            if should_close:
                self._close_position(current_long, positions)
                return True

        if current_short:
            should_close = False
            if current_short not in self.latest_premium:
                should_close = True
                if self.verbose:
                    print(f"[CLOSE SHORT] {current_short}: 数据缺失")
            elif premium_ranks.get(current_short, 1) < 0.2:
                should_close = True
                if self.verbose:
                    print(f"[CLOSE SHORT] {current_short}: 排名={premium_ranks[current_short]:.2%} < 20%")
            if should_close:
                self._close_position(current_short, positions)
                return True
        return False

    def _check_open_conditions(self, premium_ranks, positions, current_long, current_short) -> bool:
        if not premium_ranks:
            return False

        if not current_long:
            symbols_sorted = sorted(premium_ranks.keys(), key=lambda s: premium_ranks[s])
            target = symbols_sorted[0]
            if target in self.latest_prices:
                if self.verbose:
                    print(f"[OPEN LONG] {target}: 排名={premium_ranks[target]:.2%}")
                self._open_long(target)
                return True

        if not current_short:
            symbols_sorted = sorted(premium_ranks.keys(), key=lambda s: premium_ranks[s], reverse=True)
            target = symbols_sorted[0]
            if target in self.latest_prices:
                if self.verbose:
                    print(f"[OPEN SHORT] {target}: 排名={premium_ranks[target]:.2%}")
                self._open_short(target)
                return True
        return False

    def _open_long(self, symbol: str):
        price = self.latest_prices.get(symbol)
        if price and price > 0:
            order = Order.market_order(symbol=symbol, quantity=self.position_size / price)
            self.send_order(order)

    def _open_short(self, symbol: str):
        price = self.latest_prices.get(symbol)
        if price and price > 0:
            order = Order.market_order(symbol=symbol, quantity=-self.position_size / price)
            self.send_order(order)

    def _close_position(self, symbol: str, positions: dict):
        if symbol in positions:
            order = Order.market_order(symbol=symbol, quantity=-positions[symbol])
            self.send_order(order)

    def on_order(self, order: Order):
        if order.state == order.state.FILLED and self.verbose:
            print(f"[FILLED] {order.symbol} {order.quantity:.6f} @ {order.filled_price:.2f}")


# =============================================================================
# 工具函数
# =============================================================================

def plot_pnl(record_dir: str):
    """读取最新的 snapshots.csv 文件并画出 PnL 图"""
    import os
    import glob

    snapshot_files = glob.glob(os.path.join(record_dir, "*_snapshots.csv"))
    if not snapshot_files:
        print("未找到 snapshots 文件")
        return

    latest_file = max(snapshot_files, key=os.path.getctime)
    print(f"\n读取文件: {latest_file}")

    df = pd.read_csv(latest_file)
    pnl_by_time = df.groupby('time')['pnl'].sum().reset_index()
    pnl_by_time['cumulative_pnl'] = pnl_by_time['pnl'].cumsum()
    pnl_by_time['date'] = pd.to_datetime(pnl_by_time['time'], unit='ms')

    plt.figure(figsize=(15, 8))

    plt.subplot(2, 1, 1)
    plt.plot(pnl_by_time['date'], pnl_by_time['cumulative_pnl'], linewidth=2)
    plt.title('Cumulative PnL', fontsize=14, fontweight='bold')
    plt.xlabel('Date')
    plt.ylabel('Cumulative PnL (USDT)')
    plt.grid(True, alpha=0.3)
    plt.axhline(y=0, color='r', linestyle='--', alpha=0.5)

    plt.subplot(2, 1, 2)
    plt.bar(pnl_by_time['date'], pnl_by_time['pnl'], alpha=0.6, width=0.02)
    plt.title('Period PnL', fontsize=14, fontweight='bold')
    plt.xlabel('Date')
    plt.ylabel('Period PnL (USDT)')
    plt.grid(True, alpha=0.3)
    plt.axhline(y=0, color='r', linestyle='--', alpha=0.5)

    plt.tight_layout()

    output_path = os.path.join(record_dir, 'pnl_chart.png')
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"PnL 图已保存至: {output_path}")

    # 统计信息
    total_pnl = pnl_by_time['cumulative_pnl'].iloc[-1]
    max_pnl = pnl_by_time['cumulative_pnl'].max()
    min_pnl = pnl_by_time['cumulative_pnl'].min()
    max_drawdown = max_pnl - min_pnl

    trade_files = glob.glob(os.path.join(record_dir, "*_trades.csv"))
    num_trades = len(pd.read_csv(max(trade_files, key=os.path.getctime))) if trade_files else 0

    print("\n" + "=" * 80)
    print("回测统计")
    print("=" * 80)
    print(f"总 PnL: {total_pnl:.2f} USDT")
    print(f"最大 PnL: {max_pnl:.2f} USDT")
    print(f"最小 PnL: {min_pnl:.2f} USDT")
    print(f"最大回撤: {max_drawdown:.2f} USDT")
    print(f"回测周期: {pnl_by_time['date'].iloc[0]} 至 {pnl_by_time['date'].iloc[-1]}")
    print(f"总交易次数: {num_trades}")
    print(f"回测Bar数: {len(pnl_by_time)}")
    print("=" * 80)


# =============================================================================
# 主函数
# =============================================================================

def run_backtest(max_rows: int = 0, verbose: bool = False):
    """
    运行回测

    Args:
        max_rows: 每个数据源最多读取的行数，0表示全部
        verbose: 是否打印详细日志
    """
    import time as time_module

    record_dir = "test/bar/record"

    print("=" * 80)
    print(f"开始加载数据... (max_rows={max_rows if max_rows > 0 else '全部'})")
    print("=" * 80)

    kline_data = BarParquetData(
        name="kline",
        path="test/bar/futures_kline_1h.parquet",
        timecol="open_time",
        max_rows=max_rows,
    )

    premium_data = BarParquetData(
        name="premium",
        path="test/bar/futures_premium_1h.parquet",
        timecol="open_time",
        max_rows=max_rows,
    )

    backtest_engine = BacktestEngine(
        datasets=[kline_data, premium_data],
        delay=0,
    )

    print("数据加载完成，初始化组件...")

    # 服务端组件
    matcher = BarMatcher(
        symbol_field="symbol",
        open_field="open",
        high_field="high",
        low_field="low",
        taker_fee=2e-4,
        maker_fee=1.1e-4,
        data_source_name="kline",
    )
    backtest_engine.add_component(matcher, is_server=True)

    account = BarAccount(
        symbol_field="symbol",
        close_field="close",
        data_source_name="kline",
    )
    backtest_engine.add_component(account, is_server=True)

    recorder = BarRecorder(
        dir_path=record_dir,
        data_source_name="kline",
    )
    backtest_engine.add_component(recorder, is_server=True)

    # 客户端组件
    local_account = BarAccount(
        symbol_field="symbol",
        close_field="close",
        data_source_name="kline",
    )
    backtest_engine.add_component(local_account, is_server=False)

    strategy = PremiumRotationStrategy(
        position_size=10000.0,
        symbol_field="symbol",
        premium_field="premium",
        close_field="close",
        verbose=verbose,
    )
    backtest_engine.add_component(strategy, is_server=False)

    print("=" * 80)
    print("开始回测...")
    print("=" * 80)

    start_time = time_module.time()
    backtest_engine.run()
    elapsed = time_module.time() - start_time

    print("=" * 80)
    print(f"回测完成！耗时: {elapsed:.2f}秒")
    print("=" * 80)

    plot_pnl(record_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='溢价率轮动策略回测')
    parser.add_argument('--max-rows', type=int, default=0, help='每个数据源最多读取行数，0表示全部')
    parser.add_argument('--verbose', '-v', action='store_true', help='打印详细日志')
    args = parser.parse_args()

    run_backtest(max_rows=args.max_rows, verbose=args.verbose)
