# hft_backtest/backtest.pxd
# cython: language_level=3

from hft_backtest.event_engine cimport EventEngine, Component
from hft_backtest.delaybus cimport DelayBus
from hft_backtest.reader cimport DataReader

cdef class BacktestEngine:
    # 引擎
    cdef public EventEngine server_engine
    cdef public EventEngine client_engine
    
    # 组件列表 (存 Python 对象即可，启动/停止不频发)
    cdef list server_components
    cdef list client_components
    
    # 数据源
    cdef DataReader dataset
    
    # Timer 相关
    cdef bint _use_timer
    cdef long _timer_interval_v
    
    # Bus (强类型定义，以便直接访问内部队列)
    cdef public DelayBus server2client_bus
    cdef public DelayBus client2server_bus

    # 【新增】起止时间控制
    cdef public long long start_time
    cdef public long long end_time
    
    # 方法
    cpdef add_component(self, Component component, bint is_server)
    cpdef run(self)