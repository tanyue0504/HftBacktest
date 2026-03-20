from __future__ import annotations

from collections import defaultdict
from typing import Dict

from hft_backtest.core.event_engine import EventEngine
from hft_backtest.core.matcher import MatchEngine
from hft_backtest.core.order import Order

from .account import AshareAccount
from .event import AshareDailyEvent, AshareStkLimitEvent


class AshareDailyMatcher(MatchEngine):
    def __init__(
        self,
        account: AshareAccount,
        fill_mode: str = "close",
        commission_rate: float = 0.0003,
        stamp_tax_rate: float = 0.001,
        min_commission: float = 5.0,
        enforce_integer_lot: bool = False,
    ):
        if fill_mode not in {"close", "next_open"}:
            raise ValueError("fill_mode must be either 'close' or 'next_open'")
        self.account = account
        self.fill_mode = fill_mode
        self.commission_rate = commission_rate
        self.stamp_tax_rate = stamp_tax_rate
        self.min_commission = min_commission
        self.enforce_integer_lot = enforce_integer_lot
        self.event_engine = None
        self.active_orders: Dict[str, Dict[int, Order]] = defaultdict(dict)
        self.order_meta: Dict[int, dict] = {}
        self.order_reserved_sell: Dict[int, float] = {}
        self.symbol_reserved_sell: Dict[str, float] = defaultdict(float)
        self.latest_daily: Dict[str, AshareDailyEvent] = {}
        self.latest_limits: Dict[str, dict] = {}

    def start(self, engine: EventEngine):
        self.event_engine = engine
        engine.register(Order, self.on_order)
        engine.register(AshareStkLimitEvent, self.on_stk_limit)
        engine.register(AshareDailyEvent, self.on_daily)

    def stop(self):
        pass

    def on_stk_limit(self, event: AshareStkLimitEvent):
        self.latest_limits[event.ts_code] = {
            "timestamp": event.timestamp,
            "up_limit": getattr(event, "up_limit", None),
            "down_limit": getattr(event, "down_limit", None),
        }

    def on_order(self, order: Order):
        if order.is_cancel_order:
            self._cancel_order(order.order_id)
            return
        if not order.is_submitted:
            return

        # A 股日线默认允许历史浮点仓位，整手检查通过开关控制。
        if self.enforce_integer_lot and not self._is_integer_lot(order.quantity):
            self._cancel_submitted_order(order)
            return

        if order.quantity < 0 and not self.account.allow_short:
            if not self._reserve_sell_capacity(order):
                self._cancel_submitted_order(order)
                return

        received = order.derive()
        received.state = Order.ORDER_STATE_RECEIVED
        self.active_orders[received.symbol][received.order_id] = received
        latest_daily = self.latest_daily.get(received.symbol)
        self.order_meta[received.order_id] = {
            "eligible_after": latest_daily.timestamp if latest_daily is not None else -1,
        }
        self.event_engine.put(received)

        if self.fill_mode == "close":
            self._try_fill_symbol(received.symbol, latest_daily)

    def on_daily(self, event: AshareDailyEvent):
        self.latest_daily[event.ts_code] = event
        self._try_fill_symbol(event.ts_code, event)

    def _cancel_order(self, order_id: int):
        for symbol, orders in list(self.active_orders.items()):
            existing = orders.pop(order_id, None)
            if existing is None:
                continue
            report = existing.derive()
            report.order_type = Order.ORDER_TYPE_LIMIT
            report.state = Order.ORDER_STATE_CANCELED
            self._release_sell_reservation(order_id, symbol)
            self.order_meta.pop(order_id, None)
            self.event_engine.put(report)
            if not orders:
                self.active_orders.pop(symbol, None)
            return

    def _try_fill_symbol(self, symbol: str, market_event: AshareDailyEvent | None):
        if market_event is None:
            return
        orders = self.active_orders.get(symbol)
        if not orders:
            return

        # 同一批次内顺序扣减可卖仓位，防止多笔卖单在同一bar超卖。
        remaining_sellable = self.account.get_sellable_qty(symbol)

        for order_id, order in list(orders.items()):
            meta = self.order_meta.get(order_id, {})
            if self.fill_mode == "next_open" and meta.get("eligible_after", -1) >= market_event.timestamp:
                continue

            if order.quantity < 0 and not self.account.allow_short:
                need = -float(order.quantity)
                if need > remaining_sellable + 1e-12:
                    self._cancel_invalid_order(order)
                    continue

            limit_error = self._is_price_limit_invalid(order)
            if limit_error:
                self._cancel_invalid_order(order)
                continue

            fill_price = self._resolve_fill_price(order, market_event)
            if fill_price is None:
                continue
            if not self._passes_price_condition(order, fill_price):
                continue
            if not self._is_tradeable_price(symbol, fill_price):
                continue

            self._fill_order(order, fill_price)
            if order.quantity < 0 and not self.account.allow_short:
                remaining_sellable = max(0.0, remaining_sellable + float(order.quantity))

    def _resolve_fill_price(self, order: Order, market_event: AshareDailyEvent) -> float | None:
        if self.fill_mode == "next_open":
            candidate = getattr(market_event, "open", None)
        else:
            candidate = getattr(market_event, "close", None)
        if candidate is None:
            return None
        try:
            return float(candidate)
        except (TypeError, ValueError):
            return None

    def _passes_price_condition(self, order: Order, fill_price: float) -> bool:
        if order.is_market_order:
            return True
        if order.quantity > 0:
            return fill_price <= order.price
        return fill_price >= order.price

    def _is_tradeable_price(self, symbol: str, fill_price: float) -> bool:
        limits = self.latest_limits.get(symbol)
        if limits is None:
            return fill_price > 0
        up_limit = limits.get("up_limit")
        down_limit = limits.get("down_limit")
        if up_limit is not None and fill_price > float(up_limit):
            return False
        if down_limit is not None and fill_price < float(down_limit):
            return False
        return fill_price > 0

    def _is_price_limit_invalid(self, order: Order) -> str | None:
        if order.is_market_order:
            return None
        limits = self.latest_limits.get(order.symbol)
        if limits is None:
            return None
        up_limit = limits.get("up_limit")
        down_limit = limits.get("down_limit")
        if up_limit is not None and order.price > float(up_limit):
            return "order price is above up_limit"
        if down_limit is not None and order.price < float(down_limit):
            return "order price is below down_limit"
        return None

    def _fill_order(self, order: Order, fill_price: float):
        report = order.derive()
        report.state = Order.ORDER_STATE_FILLED
        report.filled_price = fill_price
        notional = abs(fill_price * report.quantity)
        commission = max(notional * self.commission_rate, self.min_commission)
        if report.quantity < 0:
            commission += notional * self.stamp_tax_rate
        report.commission_fee = commission
        self._release_sell_reservation(order.order_id, order.symbol)
        self.active_orders[order.symbol].pop(order.order_id, None)
        if not self.active_orders[order.symbol]:
            self.active_orders.pop(order.symbol, None)
        self.order_meta.pop(order.order_id, None)
        self.event_engine.put(report)

    def _cancel_invalid_order(self, order: Order):
        report = order.derive()
        report.state = Order.ORDER_STATE_CANCELED
        self._release_sell_reservation(order.order_id, order.symbol)
        self.active_orders[order.symbol].pop(order.order_id, None)
        if not self.active_orders[order.symbol]:
            self.active_orders.pop(order.symbol, None)
        self.order_meta.pop(order.order_id, None)
        self.event_engine.put(report)

    def _cancel_submitted_order(self, order: Order):
        report = order.derive()
        report.state = Order.ORDER_STATE_CANCELED
        self.event_engine.put(report)

    def _reserve_sell_capacity(self, order: Order) -> bool:
        # 规则解释：卖单在提交阶段先占用可卖仓位，防止同一时刻多单超卖。
        need = -float(order.quantity)
        symbol = order.symbol
        sellable = self.account.get_sellable_qty(symbol)
        reserved = self.symbol_reserved_sell.get(symbol, 0.0)
        available = sellable - reserved
        if need > available + 1e-12:
            return False
        self.order_reserved_sell[order.order_id] = need
        self.symbol_reserved_sell[symbol] = reserved + need
        return True

    def _release_sell_reservation(self, order_id: int, symbol: str):
        reserved = self.order_reserved_sell.pop(order_id, None)
        if reserved is None:
            return
        left = self.symbol_reserved_sell.get(symbol, 0.0) - reserved
        if left <= 1e-12:
            self.symbol_reserved_sell.pop(symbol, None)
        else:
            self.symbol_reserved_sell[symbol] = left

    @staticmethod
    def _is_integer_lot(quantity: float) -> bool:
        quantity_i = round(float(quantity))
        return abs(float(quantity) - quantity_i) < 1e-12