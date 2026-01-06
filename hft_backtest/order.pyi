from hft_backtest.event import Event

# 模块级常量 (来自 pxd 中的 cpdef enum)
ORDER_TYPE_LIMIT: int
ORDER_TYPE_MARKET: int
ORDER_TYPE_TRACKING: int
ORDER_TYPE_CANCEL: int

ORDER_STATE_NONE: int
ORDER_STATE_CREATED: int
ORDER_STATE_SUBMITTED: int
ORDER_STATE_RECEIVED: int
ORDER_STATE_FILLED: int
ORDER_STATE_CANCELED: int

class Order(Event):
    # 类级常量
    SCALER: int
    
    ORDER_TYPE_LIMIT: int
    ORDER_TYPE_MARKET: int
    ORDER_TYPE_TRACKING: int
    ORDER_TYPE_CANCEL: int
    
    ORDER_STATE_NONE: int
    ORDER_STATE_CREATED: int
    ORDER_STATE_SUBMITTED: int
    ORDER_STATE_RECEIVED: int
    ORDER_STATE_FILLED: int
    ORDER_STATE_CANCELED: int
    ORDER_SATTE_REJECTED: int

    # cdef public 属性
    order_id: int
    order_type: int
    state: int
    symbol: str
    rank: float
    traded: float
    filled_price: float
    commission_fee: float

    def __init__(
        self, 
        order_id: int, 
        order_type: int,
        symbol: str,
        quantity: float,
        price: float,
    ) -> None: ...

    # 状态判断属性
    @property
    def is_limit_order(self) -> bool: ...
    @property
    def is_market_order(self) -> bool: ...
    @property
    def is_tracking_order(self) -> bool: ...
    @property
    def is_cancel_order(self) -> bool: ...
    @property
    def is_created(self) -> bool: ...
    @property
    def is_submitted(self) -> bool: ...
    @property
    def is_received(self) -> bool: ...
    @property
    def is_filled(self) -> bool: ...
    @property
    def is_canceled(self) -> bool: ...
    @property
    def is_rejected(self) -> bool: ...

    # 价格和数量属性 (带 getter/setter)
    @property
    def price(self) -> float: ...
    @price.setter
    def price(self, value: float) -> None: ...

    @property
    def price_int(self) -> int: ...

    @property
    def quantity(self) -> float: ...
    @quantity.setter
    def quantity(self, value: float) -> None: ...

    @property
    def quantity_int(self) -> int: ...

    # 工厂方法
    @staticmethod
    def create_limit(symbol: str, quantity: float, price: float) -> Order: ...
    
    @staticmethod
    def create_market(symbol: str, quantity: float) -> Order: ...
    
    @staticmethod
    def create_tracking(symbol: str, quantity: float) -> Order: ...

    @staticmethod
    def create_cancel(order: Order) -> Order: ...

    def derive(self) -> Event: ...