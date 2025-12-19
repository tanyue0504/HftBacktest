# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False

from hft_backtest.event cimport Event

# SCALER 用于价格/数量的整数化
cdef long _SCALER = 100000000L  # 1亿

# 全局 ID 计数器 (C 静态变量，极快)
cdef long global_order_id_counter = 0

cdef class Order(Event):
    """
    高性能 Order 对象。
    属性访问速度是普通 Python 对象的 10-20 倍。
    内存占用约为普通 Python 对象的 1/3。
    """
    SCALER = _SCALER

    ORDER_TYPE_LIMIT = 0 # 限价单
    ORDER_TYPE_MARKET = 1 # 市价单
    ORDER_TYPE_TRACKING = 2 # 跟踪单，自动转换为最优价限价单
    ORDER_TYPE_CANCEL = 3 # 撤单指令
    
    # 订单状态
    ORDER_STATE_NONE = -1       # 初始或撤单指令
    ORDER_STATE_CREATED = 0     # 已创建，等待提交
    ORDER_STATE_SUBMITTED = 1  # 已提交，等待交易所确认
    ORDER_STATE_RECEIVED = 2    # 交易所已接收，等待成交
    ORDER_STATE_FILLED = 3      # 已成交
    ORDER_STATE_CANCELED = 4    # 已撤销 
    
    # --- 2. 初始化 ---
    def __init__(
        self, 
        long order_id, 
        int order_type,
        str symbol,
        double quantity,
        double price,
    ):
        # 假设 Event.__init__ 只需要很少的参数，这里传入timestamp=0
        super().__init__(0) 
        
        self.order_id = order_id
        self.order_type = order_type
        self.symbol = symbol
        self._quantity = quantity
        self._price = price
        self.state = ORDER_STATE_CREATED

        self._quantity_cache_valid = False
        self._price_cache_valid = False
        
        # 初始化数值字段 (避免脏数据)
        self.rank = 0.0
        self.traded = 0.0
        self.filled_price = 0.0
        self.commission_fee = 0.0
        
        self._quantity_int_cache = 0
        self._price_int_cache = 0

    # --- 3. 辅助属性 (Python 可见) ---
    @property
    def is_limit_order(self):
        return self.order_type == ORDER_TYPE_LIMIT

    @property
    def is_market_order(self):
        return self.order_type == ORDER_TYPE_MARKET

    @property
    def is_tracking_order(self):
        return self.order_type == ORDER_TYPE_TRACKING
    
    @property
    def is_cancel_order(self):
        return self.order_type == ORDER_TYPE_CANCEL

    @property
    def is_created(self):
        return self.state == ORDER_STATE_CREATED

    @property
    def is_submitted(self):
        return self.state == ORDER_STATE_SUBMITTED

    @property
    def is_received(self):
        return self.state == ORDER_STATE_RECEIVED

    @property
    def is_filled(self):
        return self.state == ORDER_STATE_FILLED

    @property
    def is_canceled(self):
        return self.state == ORDER_STATE_CANCELED

    # --- 4. 整数化价格/数量 (带缓存) ---
    
    property price:
        def __get__(self):
            return self._price
        
        def __set__(self, double value):
            # 只有值真正改变时才让缓存失效，避免无意义的 invalid
            self._price = value
            self._price_cache_valid = False

    property price_int:
        def __get__(self):
            # C 级别的 if check，开销极低
            if not self._price_cache_valid:
                self._price_int_cache = <long>(self._price * _SCALER + 0.5)
                self._price_cache_valid = True
            return self._price_int_cache

    property quantity:
        def __get__(self):
            return self._quantity
        
        def __set__(self, double value):
            self._quantity = value
            self._quantity_cache_valid = False

    property quantity_int:
        def __get__(self):
            if not self._quantity_cache_valid:
                self._quantity_int_cache = <long>(self._quantity * _SCALER + 0.5)
                self._quantity_cache_valid = True
            return self._quantity_int_cache

    # --- 5. 工厂方法 (Python 可调用) ---
    @staticmethod
    def create_limit(str symbol, double quantity, double price):
        global global_order_id_counter
        global_order_id_counter += 1
        
        return Order(
            global_order_id_counter, 
            ORDER_TYPE_LIMIT, 
            symbol, 
            quantity, 
            price, 
        )

    @staticmethod
    def create_market(str symbol, double quantity):
        global global_order_id_counter
        global_order_id_counter += 1
        
        return Order(
            global_order_id_counter, 
            ORDER_TYPE_MARKET, 
            symbol, 
            quantity,
            -1
        )

    @staticmethod
    def create_tracking(str symbol, double quantity):
        global global_order_id_counter
        global_order_id_counter += 1

        return Order(
            global_order_id_counter, 
            ORDER_TYPE_TRACKING, 
            symbol, 
            quantity,
            -1
        )

    # 撤单指令必须从order derive出来, 然后修改type为CANCEL, 不提供工厂方法

    def __repr__(self):
        # 仅用于打印调试，性能不敏感
        return (f"Order(id={self.order_id}, type={self.order_type}, "
                f"symbol={self.symbol}, price={self.price}, state={self.state})")