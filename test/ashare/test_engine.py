from hft_backtest import BacktestEngine, FixedDelayModel, Order, Strategy
from hft_backtest.core.delaybus import DelayBus

from hft_backtest.ashare import AshareAccount, AshareDailyEvent, AshareDailyMatcher, AshareStkLimitEvent


class BuyFirstBarStrategy(Strategy):
    def __init__(self, account, quantity: float, order_factory):
        super().__init__(account)
        self.quantity = quantity
        self.order_factory = order_factory
        self.sent = False
        self.order_states = []

    def start(self, engine):
        super().start(engine)
        engine.register(AshareDailyEvent, self.on_daily)
        engine.register(Order, self.on_order)

    def on_daily(self, event: AshareDailyEvent):
        if self.sent or event.ts_code != "000001.SZ":
            return
        self.send_order(self.order_factory("000001.SZ", self.quantity))
        self.sent = True

    def on_order(self, order: Order):
        if order.symbol == "000001.SZ":
            self.order_states.append(order.state)


def _make_engine(dataset, matcher, server_account, client_account, strategy):
    server2client = DelayBus(FixedDelayModel(0))
    client2server = DelayBus(FixedDelayModel(0))
    engine = BacktestEngine(dataset, server2client, client2server, timer_interval=None)
    engine.add_component(matcher, is_server=True)
    engine.add_component(server_account, is_server=True)
    engine.add_component(client_account, is_server=False)
    engine.add_component(strategy, is_server=False)
    return engine


def test_close_fill_mode_and_pct_chg_valuation_survive_split_like_case():
    dataset = [
        AshareStkLimitEvent(202401010000, ts_code="000001.SZ", trade_date="20240101", up_limit=11.0, down_limit=9.0),
        AshareDailyEvent(202401010000, ts_code="000001.SZ", trade_date="20240101", open=10.0, close=10.0, pct_chg=0.0, _next_open=11.0),
        AshareStkLimitEvent(202401020000, ts_code="000001.SZ", trade_date="20240102", up_limit=6.0, down_limit=4.0),
        AshareDailyEvent(202401020000, ts_code="000001.SZ", trade_date="20240102", open=5.0, close=5.0, pct_chg=0.0, _next_open=None),
    ]
    matcher = AshareDailyMatcher(fill_mode="close", commission_rate=0.0, min_commission=0.0)
    server_account = AshareAccount(initial_balance=2000.0)
    client_account = AshareAccount(initial_balance=2000.0)
    strategy = BuyFirstBarStrategy(client_account, 100.0, lambda symbol, qty: Order.create_market(symbol, qty))

    engine = _make_engine(dataset, matcher, server_account, client_account, strategy)
    engine.run()

    assert server_account.get_positions()["000001.SZ"] == 100.0
    assert server_account.get_balance() == 1000.0
    assert server_account.get_market_value() == 1000.0
    assert server_account.get_equity() == 2000.0
    assert Order.ORDER_STATE_FILLED in strategy.order_states


def test_next_open_fill_mode_uses_next_day_open():
    dataset = [
        AshareDailyEvent(202401010000, ts_code="000001.SZ", trade_date="20240101", open=10.0, close=10.0, pct_chg=0.0, _next_open=11.0),
        AshareDailyEvent(202401020000, ts_code="000001.SZ", trade_date="20240102", open=11.0, close=12.0, pct_chg=20.0, _next_open=None),
    ]
    matcher = AshareDailyMatcher(fill_mode="next_open", commission_rate=0.0, min_commission=0.0)
    server_account = AshareAccount(initial_balance=2000.0)
    client_account = AshareAccount(initial_balance=2000.0)
    strategy = BuyFirstBarStrategy(client_account, 100.0, lambda symbol, qty: Order.create_market(symbol, qty))

    engine = _make_engine(dataset, matcher, server_account, client_account, strategy)
    engine.run()

    assert server_account.get_total_turnover() == 1100.0
    assert server_account.get_balance() == 900.0
    assert server_account.get_market_value() == 1200.0
    assert server_account.get_equity() == 2100.0


def test_limit_order_above_up_limit_is_canceled():
    dataset = [
        AshareStkLimitEvent(202401010000, ts_code="000001.SZ", trade_date="20240101", up_limit=11.0, down_limit=9.0),
        AshareDailyEvent(202401010000, ts_code="000001.SZ", trade_date="20240101", open=10.0, close=10.5, pct_chg=0.0, _next_open=None),
    ]
    matcher = AshareDailyMatcher(fill_mode="close", commission_rate=0.0, min_commission=0.0)
    server_account = AshareAccount(initial_balance=2000.0)
    client_account = AshareAccount(initial_balance=2000.0)
    strategy = BuyFirstBarStrategy(client_account, 100.0, lambda symbol, qty: Order.create_limit(symbol, qty, 12.0))

    engine = _make_engine(dataset, matcher, server_account, client_account, strategy)
    engine.run()

    assert server_account.get_total_trade_count() == 0
    assert Order.ORDER_STATE_CANCELED in strategy.order_states