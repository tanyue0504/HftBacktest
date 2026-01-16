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
# 引入 Bus 和它的结构体 BusItem
from hft_backtest.delaybus cimport DelayBus, BusItem 

# 引入 Python 层的 Timer 类
from hft_backtest.timer import Timer

cdef class BacktestEngine:
    """
    全 Cython 版回测引擎
    包含防傻设计：
    1. 时间单调性检查 (防止时间倒流)
    2. 自动熔断机制 (End Time Check)
    3. 类型安全检查
    """
    def __init__(
        self, 
        dataset, 
        DelayBus server2client_delaybus, 
        DelayBus client2server_delaybus, 
        timer_interval=1000,
        long long start_time=0,
        long long end_time=LLONG_MAX
    ):
        self.server_engine = EventEngine()
        self.client_engine = EventEngine()
        self.server_components = []
        self.client_components = []
        
        # 1. 处理数据集
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

        # 3. 记录起止时间
        self.start_time = start_time
        self.end_time = end_time
            
        # 4. 自动接线
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
        # 1. 启动组件
        cdef Component c
        for c_obj in self.server_components:
            c = <Component>c_obj
            c.start(self.server_engine)
        for c_obj in self.client_components:
            c = <Component>c_obj
            c.start(self.client_engine)
            
        # 2. 声明 C 变量 (统一使用 long long 防止溢出)
        cdef long long t_data = LLONG_MAX
        cdef long long t_s2c = LLONG_MAX
        cdef long long t_c2s = LLONG_MAX
        cdef long long next_timer = LLONG_MAX
        cdef long long min_t = 0
        
        # [防傻核心变量] 记录上一次处理的时间，初始为 start_time 或 0
        cdef long long last_engine_time = self.start_time 
        
        cdef Event current_data = None
        
        try:
            # 预读第一条数据
            current_data = self.dataset.fetch_next()
            
            # [逻辑]：快进到 start_time
            while current_data is not None and current_data.timestamp < self.start_time:
                current_data = self.dataset.fetch_next()
            
            # Timer 初始化 (对齐到当前数据时间，或者 start_time)
            if self._use_timer:
                if current_data is not None:
                    next_timer = current_data.timestamp
                else:
                    next_timer = self.start_time
                
            # --- 主循环 (纯 C 速度) ---
            while current_data is not None:
                t_data = current_data.timestamp
                
                # 获取 DelayBus 触发时间
                t_s2c = self.server2client_bus.peek_trigger_time()
                t_c2s = self.client2server_bus.peek_trigger_time()
                    
                # 计算最小值 min(t_data, t_s2c, t_c2s, next_timer)
                min_t = t_data
                if t_s2c < min_t: min_t = t_s2c
                if t_c2s < min_t: min_t = t_c2s
                if next_timer < min_t: min_t = next_timer

                # --- [防傻设计 1]：时间单调性检查 (CRITICAL) ---
                # 如果时间倒流，说明逻辑严重错误（如 DelayBus 计算错误或数据乱序）
                if min_t < last_engine_time:
                    raise RuntimeError(
                        f"FATAL: Time travel detected! Engine time regression.\n"
                        f"Current Engine Time: {last_engine_time}\n"
                        f"Next Event Time:   {min_t}\n"
                        f"Diff:              {min_t - last_engine_time}\n"
                        f"Debug Sources:     Data={t_data}, S2C={t_s2c}, C2S={t_c2s}, Timer={next_timer}"
                    )
                last_engine_time = min_t
                # ------------------------------------------------

                # --- [防傻设计 2]：熔断检查 (End Time) ---
                if min_t > self.end_time:
                    break
        
                # 优先级处理与事件分发
                if t_s2c <= min_t:
                    self.server2client_bus.process_until(t_s2c)
                    continue
                
                if t_c2s <= min_t:
                    self.client2server_bus.process_until(t_c2s)
                    continue
                    
                if next_timer <= min_t:
                    self.client_engine.put(Timer(next_timer))
                    if self._use_timer:
                        next_timer += self._timer_interval_v
                    else:
                        next_timer = LLONG_MAX
                    continue
                    
                if t_data == min_t:
                    self.server_engine.put(current_data)
                    current_data = self.dataset.fetch_next()
            
            # --- 收尾逻辑 (处理剩余的在途延迟消息) ---
            while True:
                t_s2c = self.server2client_bus.peek_trigger_time()
                t_c2s = self.client2server_bus.peek_trigger_time()
                    
                if t_s2c == LLONG_MAX and t_c2s == LLONG_MAX:
                    break

                # 计算收尾阶段的 min_t
                if t_s2c <= t_c2s:
                    min_t = t_s2c
                else:
                    min_t = t_c2s
                
                # --- [防傻设计 1 复用]：收尾阶段的时间单调性检查 ---
                if min_t < last_engine_time:
                     raise RuntimeError(
                        f"FATAL: Time travel detected during teardown!\n"
                        f"Current Engine Time: {last_engine_time}, Next: {min_t}"
                    )
                last_engine_time = min_t
                
                # --- [防傻设计 2 复用]：收尾阶段熔断 ---
                if min_t > self.end_time:
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