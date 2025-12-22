# hft_backtest/backtest.pyx
# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False

from libc.limits cimport LLONG_MAX
from itertools import chain

# cimport 核心组件
from hft_backtest.event cimport Event
from hft_backtest.event_engine cimport EventEngine, Component
from hft_backtest.reader cimport DataReader, PyDatasetWrapper
# 引入 Bus 和它的结构体 BusItem (为了访问 _queue)
from hft_backtest.delaybus cimport DelayBus, BusItem 

# 引入 Python 层的 Timer 类 (用于实例化)
from hft_backtest.timer import Timer

cdef class BacktestEngine:
    """
    全 Cython 版回测引擎
    """
    def __init__(
        self, 
        dataset, 
        DelayBus server2client_delaybus, 
        DelayBus client2server_delaybus, 
        timer_interval=1000
    ):
        self.server_engine = EventEngine()
        self.client_engine = EventEngine()
        self.server_components = []
        self.client_components = []
        
        # 1. 处理数据集 (如果是普通 Dataset，自动包装)
        if isinstance(dataset, DataReader):
            self.dataset = <DataReader>dataset
        else:
            self.dataset = PyDatasetWrapper(dataset)
            
        self.server2client_bus = server2client_delaybus
        self.client2server_bus = client2server_delaybus
        
        # 2. 处理 Timer 参数
        if timer_interval is None:
            self._use_timer = False
            self._timer_interval_v = 0
        else:
            self._use_timer = True
            self._timer_interval_v = timer_interval
            
        # 3. 自动接线
        self.server2client_bus.set_target_engine(self.client_engine)
        self.client2server_bus.set_target_engine(self.server_engine)
        
        self.add_component(self.server2client_bus, True)
        self.add_component(self.client2server_bus, False)
        
    cpdef add_component(self, Component component, bint is_server):
        if is_server:
            self.server_components.append(component)
        else:
            self.client_components.append(component)
            
    cpdef run(self):
        # 1. 启动所有组件
        cdef Component c
        for c_obj in self.server_components:
            c = <Component>c_obj
            c.start(self.server_engine)
        for c_obj in self.client_components:
            c = <Component>c_obj
            c.start(self.client_engine)
            
        # 2. 声明 C 变量 (放在循环外)
        cdef long t_data = LLONG_MAX
        cdef long t_s2c = LLONG_MAX
        cdef long t_c2s = LLONG_MAX
        cdef long next_timer = LLONG_MAX
        cdef long min_t
        cdef Event current_data = None
        
        try:
            # 预读第一条数据
            current_data = self.dataset.fetch_next()
            
            # Timer 初始化
            if current_data is not None and self._use_timer:
                next_timer = current_data.timestamp
                
            # --- 主循环 (纯 C 速度) ---
            while current_data is not None:
                t_data = current_data.timestamp
                
                # 【极速优化】直接检查 C++ vector 是否为空，避免 Python 属性调用
                if self.server2client_bus._queue.empty():
                    t_s2c = LLONG_MAX
                else:
                    t_s2c = self.server2client_bus._queue.front().trigger_time
                    
                if self.client2server_bus._queue.empty():
                    t_c2s = LLONG_MAX
                else:
                    t_c2s = self.client2server_bus._queue.front().trigger_time
                    
                # 手写 min 比较 (比 Python min() 快)
                min_t = t_data
                if t_s2c < min_t: min_t = t_s2c
                if t_c2s < min_t: min_t = t_c2s
                if next_timer < min_t: min_t = next_timer
                
                # 优先级处理
                if t_s2c <= min_t:
                    self.server2client_bus.process_until(t_s2c)
                    continue
                    
                if t_c2s <= min_t:
                    self.client2server_bus.process_until(t_c2s)
                    continue
                    
                if next_timer <= min_t:
                    # 实例化 Timer (这是少数还要调用 Python 的地方，无法避免)
                    self.client_engine.put(Timer(next_timer))
                    
                    if self._use_timer:
                        next_timer += self._timer_interval_v
                    else:
                        next_timer = LLONG_MAX
                    continue
                    
                if t_data == min_t:
                    self.server_engine.put(current_data)
                    # 高速读取下一条
                    current_data = self.dataset.fetch_next()
            
            # --- 收尾逻辑 ---
            while True:
                # 再次检查剩余的延迟消息
                if self.server2client_bus._queue.empty():
                    t_s2c = LLONG_MAX
                else:
                    t_s2c = self.server2client_bus._queue.front().trigger_time
                    
                if self.client2server_bus._queue.empty():
                    t_c2s = LLONG_MAX
                else:
                    t_c2s = self.client2server_bus._queue.front().trigger_time
                    
                if t_s2c == LLONG_MAX and t_c2s == LLONG_MAX:
                    break
                    
                if t_s2c <= t_c2s:
                     self.server2client_bus.process_until(t_s2c)
                else:
                     self.client2server_bus.process_until(t_c2s)
                     
        finally:
            # 停止组件
            for c_obj in chain(self.server_components, self.client_components):
                c = <Component>c_obj
                c.stop()