from enum import Enum, auto
from itertools import count
from typing import Optional

from hft_backtest import Event

class OrderType(Enum):
    """
    订单类型
    - LIMIT_ORDER    限价单（需 price）
    - MARKET_ORDER   市价单（price=None）
    - TRACKING_ORDER 跟踪委托（price=None，本方最优）
    - CANCEL_ORDER   撤单指令（仅包含 cancel_target_id）
    """
    LIMIT_ORDER = auto()
    MARKET_ORDER = auto()
    TRACKING_ORDER = auto()
    CANCEL_ORDER = auto()

class OrderState(Enum):
    """
    订单生命周期（撤单指令不适用）
    CREATED  : 本地已创建
    SUBMITTED: 已提交（在途）
    RECEIVED : 服务器已收到
    FILLED   : 已成交
    CANCELED : 已取消
    """
    CREATED = auto()
    SUBMITTED = auto()
    RECEIVED = auto()
    FILLED = auto()
    CANCELED = auto()

class Order(Event):
    """
    单一订单类型，通过 order_type 区分业务语义。
    字段：
      - order_id: 唯一ID
      - order_type: OrderType
      - symbol: 品种（撤单为 None）
      - quantity: 数量（撤单为 None）
      - price: 价格（市价/跟踪为 None）
      - state: 订单状态（撤单为 None）
      - cancel_target_id: 撤单目标订单ID（仅撤单使用）

      - rank: 上一个booktick时的订单真实排位，表示订单该档位前方剩余订单量
      - traded: 每次来trade数据累计，来booktick时用于估算front_cancel后更新rank并重置traded
      之所以分开维护, 是因为booktick不一定会每次都更新全部档位的排位信息
      当没有booktick信息时, 暂不更新rank；但是traded一旦有成交就必须更新

      - filled_price: 成交价（撮合后填充）
      - commission_fee: 手续费（撮合后填充）
    """
    _ID_GEN = count()
    SCALER = 10**8  # 价格和数量的整数化倍数

    def __init__(
        self,
        order_id: int,
        order_type: OrderType,
        symbol: Optional[str],
        quantity: Optional[float],
        price: Optional[float],
        state: Optional[OrderState],
        cancel_target_id: Optional[int] = None,
        rank: Optional[float] = None,
        traded: Optional[float] = None,
        filled_price: Optional[float] = None,
        commission_fee: Optional[float] = None,
    ):
        super().__init__()
        self.order_id = order_id
        self.order_type = order_type
        self.symbol = symbol
        self.quantity = quantity
        self._quantity_int = None  # 延迟计算
        self.price = price
        self._price_int = None  # 延迟计算
        self.state = state
        self.cancel_target_id = cancel_target_id
        self.rank = rank
        self.traded = traded
        self.filled_price = filled_price
        self.commission_fee = commission_fee

    def __repr__(self) -> str:
        return f"""
Order(
    timestamp={self.timestamp},
    id={self.order_id},
    type={self.order_type.name},
    state={self.state.name if self.state else None},
    symbol={self.symbol},
    qty={self.quantity},
    price={self.price},
    cancel_target_id={self.cancel_target_id},
    rank={self.rank},
    traded={self.traded},
    filled_price={self.filled_price},
    commission_fee={self.commission_fee}
)
        """

    # --- 便捷类型判断 ---
    @property
    def is_limit(self) -> bool:
        return self.order_type == OrderType.LIMIT_ORDER

    @property
    def is_market(self) -> bool:
        return self.order_type == OrderType.MARKET_ORDER

    @property
    def is_tracking(self) -> bool:
        return self.order_type == OrderType.TRACKING_ORDER

    @property
    def is_cancel(self) -> bool:
        return self.order_type == OrderType.CANCEL_ORDER
    
    @property
    def price_int(self) -> int:
        if self.price is None:
            raise ValueError("Order price is None, cannot convert to int.")
        if self._price_int is None:
            self._price_int = int(round(self.price * self.SCALER))
        return self._price_int

    @property
    def quantity_int(self) -> int:
        if self.quantity is None:
            raise ValueError("Order quantity is None, cannot convert to int.")
        if self._quantity_int is None:
            self._quantity_int = int(round(self.quantity * self.SCALER))
        return self._quantity_int

    # --- 工厂方法 ---
    @classmethod
    def _next_id(cls) -> int:
        return next(cls._ID_GEN)

    @classmethod
    def limit_order(cls, symbol: str, quantity: float, price: float) -> "Order":
        assert isinstance(symbol, str)
        assert isinstance(quantity, (int, float))
        assert isinstance(price, (int, float))
        return cls(
            order_id=cls._next_id(),
            order_type=OrderType.LIMIT_ORDER,
            symbol=symbol,
            quantity=float(quantity),
            price=float(price),
            state=OrderState.CREATED,
        )

    @classmethod
    def market_order(cls, symbol: str, quantity: float) -> "Order":
        assert isinstance(symbol, str)
        assert isinstance(quantity, (int, float))
        return cls(
            order_id=cls._next_id(),
            order_type=OrderType.MARKET_ORDER,
            symbol=symbol,
            quantity=float(quantity),
            price=None,
            state=OrderState.CREATED,
        )

    @classmethod
    def tracking_order(cls, symbol: str, quantity: float) -> "Order":
        assert isinstance(symbol, str)
        assert isinstance(quantity, (int, float))
        return cls(
            order_id=cls._next_id(),
            order_type=OrderType.TRACKING_ORDER,
            symbol=symbol,
            quantity=quantity,
            price=None,
            state=OrderState.CREATED,
        )

    @classmethod
    def cancel_order(cls, target_order_id: int) -> "Order":
        assert isinstance(target_order_id, int) and target_order_id >= 0
        return cls(
            order_id=cls._next_id(),
            order_type=OrderType.CANCEL_ORDER,
            symbol=None,
            quantity=None,
            price=None,
            state=None,  # 撤单不参与状态机
            cancel_target_id=target_order_id,
        )