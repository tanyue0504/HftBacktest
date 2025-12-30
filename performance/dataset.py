import numpy as np
import time

# 模拟用户环境中的 Event 类
# 在实际运行中，如果环境中有编译好的 hft_backtest，我会尝试导入。
# 这里为了演示逻辑，先定义一个模拟类（如果导入失败）。
try:
    from hft_backtest.event import Event
    print("Successfully imported Cython Event.")
except ImportError:
    print("Could not import hft_backtest.event. Using simulated Python class.")
    class Event:
        __slots__ = ['timestamp']
        def __init__(self, timestamp):
            self.timestamp = timestamp

class MockDatasetMap:
    def __init__(self, data):
        # 模拟 dataset 中的列数据
        self.cols = [data]
        self.event_type = Event
    
    def __iter__(self):
        # 模拟 ParquetDataset 的实现：使用 map
        yield from map(self.event_type, *self.cols)

class MockDatasetZip:
    def __init__(self, data):
        # 模拟 dataset 中的列数据
        self.cols = [data]
    
    def __iter__(self):
        # 模拟优化后的实现：使用 zip
        yield from zip(*self.cols)

def run_test():
    N = 10**7 # 使用 1000万数据进行演示，避免超时
    print(f"Generating {N} rows of data...")
    data = np.arange(N, dtype=np.float64)
    
    print("-" * 30)
    
    # Test Map
    ds_map = MockDatasetMap(data)
    start = time.time()
    for _ in ds_map:
        pass
    end = time.time()
    map_time = end - start
    print(f"Map (Event) Time: {map_time:.4f} s")
    
    print("-" * 30)

    # Test Zip
    ds_zip = MockDatasetZip(data)
    start = time.time()
    for _ in ds_zip:
        pass
    end = time.time()
    zip_time = end - start
    print(f"Zip (Tuple) Time: {zip_time:.4f} s")
    
    print("-" * 30)
    
    if zip_time > 0:
        print(f"Speedup: {map_time / zip_time:.2f}x")

if __name__ == "__main__":
    run_test()