from hft_backtest import CsvDataset
from itertools import product
from datetime import datetime

renmae_dict = {
    f"{bidask}[{num - 1}].{priceamount}": f"{bidask}_{priceamount}_{num}"
    for bidask, priceamount, num in product(['bids', 'asks'], ['price', 'amount'], range(1, 26))
}

ds = CsvDataset(
    name="book_ticker",
    path="/shared_dir/Tan/okex_L2_0801/BTC-USDT-SWAP/okex-swap_book_snapshot_25_2025-08-01_BTC-USDT-SWAP.csv.gz",
    timecol="timestamp",
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