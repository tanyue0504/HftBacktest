from pathlib import Path

from hft_backtest import AccountRecorder, BacktestEngine, FixedDelayModel, Order, Strategy, TradeRecorder
from hft_backtest.core.delaybus import DelayBus

from hft_backtest.ashare import AshareAccount, AshareDailyEvent, AshareDailyMatcher


class OneShotStrategy(Strategy):
    def __init__(self, account):
        super().__init__(account)
        self.sent = False

    def start(self, engine):
        super().start(engine)
        engine.register(AshareDailyEvent, self.on_daily)

    def on_daily(self, event: AshareDailyEvent):
        if self.sent:
            return
        self.send_order(Order.create_market(event.ts_code, 100.0))
        self.sent = True


def test_core_recorders_work_with_ashare_account(tmp_path: Path):
    dataset = [
        AshareDailyEvent(202401010000, ts_code="000001.SZ", trade_date="20240101", open=10.0, close=10.0, pct_chg=0.0, _next_open=None),
        AshareDailyEvent(202401020000, ts_code="000001.SZ", trade_date="20240102", open=10.0, close=11.0, pct_chg=10.0, _next_open=None),
    ]
    server2client = DelayBus(FixedDelayModel(0))
    client2server = DelayBus(FixedDelayModel(0))
    matcher = AshareDailyMatcher(fill_mode="close", commission_rate=0.0, min_commission=0.0)
    server_account = AshareAccount(initial_balance=2000.0)
    client_account = AshareAccount(initial_balance=2000.0)
    trade_recorder = TradeRecorder(str(tmp_path / "trades.csv"), server_account)
    account_recorder = AccountRecorder(
        str(tmp_path / "account.csv"),
        server_account,
        interval=24 * 60 * 60 * 1000,
    )
    strategy = OneShotStrategy(client_account)

    engine = BacktestEngine(
        dataset,
        server2client,
        client2server,
        timer_interval=24 * 60 * 60 * 1000,
    )
    engine.add_component(matcher, is_server=True)
    engine.add_component(server_account, is_server=True)
    engine.add_component(trade_recorder, is_server=True)
    engine.add_component(account_recorder, is_server=True)
    engine.add_component(client_account, is_server=False)
    engine.add_component(strategy, is_server=False)
    engine.run()

    trade_path = tmp_path / "trades.csv"
    account_path = tmp_path / "account.csv"
    assert trade_path.exists()
    assert account_path.exists()

    trade_lines = trade_path.read_text(encoding="utf-8-sig").strip().splitlines()
    account_lines = account_path.read_text(encoding="utf-8-sig").strip().splitlines()
    assert len(trade_lines) >= 2
    assert len(account_lines) >= 2
    assert trade_lines[0].startswith("timestamp,order_id")
    assert account_lines[0].startswith("timestamp,equity")