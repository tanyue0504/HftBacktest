from __future__ import annotations

from typing import Dict

from hft_backtest.core.account import Account
from hft_backtest.core.event_engine import EventEngine
from hft_backtest.core.order import Order

from .event import AshareDailyEvent


class AshareAccount(Account):
    def __init__(self, initial_balance: float = 0.0, allow_short: bool = False):
        super().__init__()
        self.initial_balance = float(initial_balance)
        self.cash_balance = float(initial_balance)
        self.allow_short = allow_short

        self.order_dict: Dict[int, Order] = {}
        self.position_qty: Dict[str, float] = {}
        self.sellable_qty: Dict[str, float] = {}
        self.market_values: Dict[str, float] = {}
        self.last_close: Dict[str, float] = {}
        self.last_pct_chg: Dict[str, float] = {}
        self.last_trade_date: Dict[str, str] = {}

        self.total_turnover = 0.0
        self.total_commission = 0.0
        self.total_trade_count = 0

    def start(self, engine: EventEngine):
        engine.register(Order, self.on_order)
        engine.register(AshareDailyEvent, self.on_daily)

    def stop(self):
        pass

    def on_daily(self, event: AshareDailyEvent):
        symbol = event.ts_code
        close_price = getattr(event, "close", None)
        pct_chg = getattr(event, "pct_chg", None)
        trade_date = str(getattr(event, "trade_date", ""))

        # T+1 规则：进入新交易日后，上一日持仓转为可卖仓位。
        if trade_date and self.last_trade_date.get(symbol) != trade_date:
            position = self.position_qty.get(symbol, 0.0)
            if position > 1e-12:
                self.sellable_qty[symbol] = position
            else:
                self.sellable_qty.pop(symbol, None)
            self.last_trade_date[symbol] = trade_date

        if close_price is not None:
            self.last_close[symbol] = float(close_price)
        pct_chg_value = 0.0 if pct_chg is None else float(pct_chg)
        self.last_pct_chg[symbol] = pct_chg_value

        if symbol in self.market_values:
            self.market_values[symbol] *= 1.0 + pct_chg_value / 100.0

    def on_order(self, order: Order):
        if order.is_cancel_order:
            return

        if order.is_submitted or order.is_received:
            self.order_dict[order.order_id] = order
            return

        if order.is_canceled or order.is_rejected:
            self.order_dict.pop(order.order_id, None)
            return

        if not order.is_filled:
            return

        self.order_dict.pop(order.order_id, None)
        symbol = order.symbol
        qty = float(order.quantity)
        prev_qty = self.position_qty.get(symbol, 0.0)
        prev_value = self.market_values.get(symbol, 0.0)
        new_qty = prev_qty + qty

        # 防御性校验：正常路径由 matcher 预先阻断，这里只兜底异常状态。
        if not self.allow_short and new_qty < -1e-12:
            raise RuntimeError(f"Unexpected negative position in ledger: {symbol}")

        trade_notional = qty * float(order.filled_price)
        self.cash_balance -= trade_notional
        self.cash_balance -= float(order.commission_fee)
        self.total_turnover += abs(trade_notional)
        self.total_commission += float(order.commission_fee)
        self.total_trade_count += 1

        if qty > 0:
            valuation_price = self.last_close.get(symbol, float(order.filled_price))
            new_value = prev_value + qty * valuation_price
        elif qty < 0 and prev_qty > 0:
            sell_qty = min(-qty, prev_qty)
            reduction_ratio = sell_qty / prev_qty
            new_value = prev_value * (1.0 - reduction_ratio)
            if symbol in self.sellable_qty:
                left = self.sellable_qty[symbol] - sell_qty
                if left <= 1e-12:
                    self.sellable_qty.pop(symbol, None)
                else:
                    self.sellable_qty[symbol] = left
        else:
            new_value = prev_value

        if abs(new_qty) < 1e-12:
            self.position_qty.pop(symbol, None)
            self.sellable_qty.pop(symbol, None)
            self.market_values.pop(symbol, None)
        else:
            self.position_qty[symbol] = new_qty
            self.market_values[symbol] = new_value

    def get_position_qty(self, symbol: str) -> float:
        return float(self.position_qty.get(symbol, 0.0))

    def get_sellable_qty(self, symbol: str) -> float:
        return float(self.sellable_qty.get(symbol, 0.0))

    def get_positions(self):
        return self.position_qty.copy()

    def get_orders(self):
        return self.order_dict.copy()

    def get_prices(self):
        return self.last_close.copy()

    def get_balance(self):
        return self.cash_balance

    def get_equity(self):
        return self.cash_balance + sum(self.market_values.values())

    def get_total_turnover(self):
        return self.total_turnover

    def get_total_commission(self):
        return self.total_commission

    def get_total_funding_fee(self):
        return 0.0

    def get_total_trade_pnl(self):
        return self.get_equity() - self.initial_balance

    def get_total_trade_count(self):
        return self.total_trade_count

    def get_market_value(self):
        return sum(self.market_values.values())