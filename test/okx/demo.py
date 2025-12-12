from hft_backtest import CsvDataset, BacktestEngine, Strategy, Order, EventEngine, Data
from itertools import product
from datetime import datetime

renmae_dict = {
    f"{bidask}[{num - 1}].{priceamount}": f"{bidask}_{priceamount}_{num}"
    for bidask, priceamount, num in product(['bids', 'asks'], ['price', 'amount'], range(1, 26))
}

ds_btc = CsvDataset(
    name="book_ticker",
    path="/shared_dir/Tan/okex_L2_0801/BTC-USDT-SWAP/okex-swap_book_snapshot_25_2025-08-01_BTC-USDT-SWAP.csv.gz",
    timecol="timestamp",
    compression="gzip",
    rename=renmae_dict,
    symbol="BTC-USDT-SWAP",
)

class BuyAndHoldStrategy(Strategy):
    def start(self, engine: EventEngine):
        self.has_bought = False

    def on_bookticker(self, data: Data):
        if not self.has_bought:
            order = Order(
                symbol=data.symbol,
                price=data.asks_1_price,
                amount=1,
                side='buy',
                order_type='market',
            )
            self.send_order(order)
            self.has_bought = True

def test_read_timecost():
    dt1 = datetime.now()
    for data in ds_btc:
        # print(data)
        # break
        pass
    dt2 = datetime.now()
    print("Elapsed time:", dt2 - dt1)

def main():
    pass

if __name__ == "__main__":
    backtest_engine = BacktestEngine(datasets=[ds_btc], delay=100)