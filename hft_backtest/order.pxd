# cython: language_level=3
from hft_backtest.event cimport Event

# --- 定义全局常量 (Python可见，C是纯整数) ---
cpdef enum:
    # 订单类型
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
    ORDER_STATE_REJECTED = 5    # 已拒单

cdef class Order(Event):
    # --- 核心字段 (cdef public 让 Python 可读写) ---
    # 使用 C 类型 (long, int, double) 确保 8字节对齐和极致性能
    
    cdef public long order_id
    cdef public int order_type      # 对应上面的 Enum
    cdef public int state           # 对应上面的 Enum
    
    # 基础数据
    cdef public str symbol          # 字符串保持对象引用
    cdef double _quantity
    cdef double _price
    
    # 撮合引擎专用 (用户通常只读，但为了方便设为 public)
    cdef public double rank         # 队列位置
    cdef public double traded       # 累计成交量
    
    # 成交回报数据
    cdef public double filled_price
    cdef public double commission_fee

    # 下单约束
    # post_only=True 表示该订单只允许作为 Maker 挂单；若会立即吃单则应被拒单。
    cdef public bint post_only
    
    # 内部缓存 (用于 price_int/quantity_int)
    cdef bint _quantity_cache_valid
    cdef bint _price_cache_valid
    cdef long _quantity_int_cache
    cdef long _price_int_cache