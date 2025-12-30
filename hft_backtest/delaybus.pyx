# hft_backtest/delaybus.pyx
# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False
# cython: cdivision=True

from cpython.ref cimport Py_INCREF, Py_DECREF
from libc.limits cimport LLONG_MAX
import math

# 导入 Component 供继承
from hft_backtest.event_engine cimport Component, EventEngine
from hft_backtest.event cimport Event

# ==========================================
# Latency Models
# ==========================================

cdef class LatencyModel:
    """延迟模型基类"""
    cpdef long get_delay(self, Event event):
        return 0

cdef class FixedDelayModel(LatencyModel):
    """固定延迟模型"""
    def __init__(self, long delay):
        self.delay = delay

    cpdef long get_delay(self, Event event):
        return self.delay

# ==========================================
# DelayBus Implementation
# ==========================================

cdef class DelayBus(Component):
    def __init__(
        self, 
        LatencyModel delay_model,
    ):
        self.model = delay_model
        self._source_id = 0
        self.target_engine = None
    
    cpdef set_target_engine(self, EventEngine engine):
        """
        允许延迟绑定目标引擎
        """
        self.target_engine = engine

    cpdef start(self, EventEngine engine):
        """
        组件启动：
        1. 记录 Source Engine ID (用于过滤事件)
        2. 注册监听器
        """
        self._source_id = engine._id
        
        # 注册为 Global Listener，接收所有事件，我们在 on_event 里过滤
        # is_senior=False (Junior)，确保在策略处理完事件后，我们再搬运事件
        engine.global_register(self.on_event, ignore_self=False, is_senior=False)

    cpdef stop(self):
        pass

    cpdef on_event(self, Event event):
        """
        事件回调
        """
        # 1. 来源过滤：只处理 Source Engine 产生的事件
        if event.source != self._source_id:
            return

        # 【核心修复】使用 derive (现已基于 copy.copy) 创建副本
        # 这确保了如果发送方后续修改对象，不会影响延迟总线中的副本
        cdef Event snapshot = event.derive()
        
        # 还原元数据 (因为 derive 会重置这些路由信息，作为网线我们需要保留原始信息)
        snapshot.timestamp = event.timestamp
        snapshot.source = event.source
        snapshot.producer = event.producer

        # 2. 计算延迟 (使用原事件或副本均可)
        cdef long delay = self.model.get_delay(event)
        cdef long trigger_time = event.timestamp + delay
        
        # 3. 入堆 (注意：这里 push 的是 snapshot)
        self._push(trigger_time, snapshot)

    cpdef process_until(self, long timestamp):
        """
        处理堆中 trigger_time <= timestamp 的事件
        """
        cdef BusItem item
        
        while not self._queue.empty():
            item = self._queue.front()
            
            if item.trigger_time > timestamp:
                break
            
            self._pop_and_process()

    @property
    def next_timestamp(self):
        """获取下一个最早触发的时间"""
        if self._queue.empty():
            return float('inf')
        return self._queue.front().trigger_time

    # ====================================================
    # 解耦接口 (C-API)
    # 供 BacktestEngine 直接调用，避免直接访问 _queue
    # ====================================================
    
    cdef bint is_empty(self):
        """C 级快速判空"""
        return self._queue.empty()

    cdef long peek_trigger_time(self):
        """
        C 级快速查看堆顶时间。
        如果队列为空，返回 LLONG_MAX，方便比较逻辑。
        """
        if self._queue.empty():
            return LLONG_MAX
        return self._queue.front().trigger_time

    # ----------------------------------------------------
    #  Min-Heap Logic (C++ Vector)
    # ----------------------------------------------------
    
    cdef void _push(self, long trigger_time, Event event):
        cdef BusItem item
        item.trigger_time = trigger_time
        item.event = <PyObject*>event
        
        # [关键] 增加引用计数，防止 Event 在传输过程中被 GC
        # 即使 derive 改用了 copy.copy，这里依然需要 INCREF，
        # 因为 std::vector 存的是裸指针，不懂 Python 的生命周期。
        Py_INCREF(event)
        
        self._queue.push_back(item)
        self._sift_up(self._queue.size() - 1)

    cdef void _pop_and_process(self):
        # 1. 取出堆顶
        cdef BusItem top = self._queue.front()
        cdef Event event = <Event>top.event
        
        # 2. 移除并保持堆序
        cdef BusItem last = self._queue.back()
        self._queue.pop_back()
        
        if not self._queue.empty():
            self._queue[0] = last
            self._sift_down(0)
            
        # 3. 推送给 Target Engine
        # 同步目标引擎时间
        if self.target_engine.timestamp < top.trigger_time:
            self.target_engine.timestamp = top.trigger_time

        # 【直接推送】
        self.target_engine.put(event)
        
        # [关键] 释放堆中持有的引用
        # 此时 target_engine 可能已经接手了该对象（增加了它的引用），
        # 或者处理完不再需要了。我们需要释放 DelayBus 持有的那份引用。
        Py_DECREF(event)

    cdef void _sift_up(self, size_t idx):
        cdef size_t parent
        cdef BusItem temp
        while idx > 0:
            parent = (idx - 1) >> 1
            if self._queue[idx].trigger_time < self._queue[parent].trigger_time:
                temp = self._queue[idx]
                self._queue[idx] = self._queue[parent]
                self._queue[parent] = temp
                idx = parent
            else:
                break

    cdef void _sift_down(self, size_t idx):
        cdef size_t left, right, smallest
        cdef size_t size = self._queue.size()
        cdef BusItem temp
        
        while True:
            left = (idx << 1) + 1
            right = left + 1
            smallest = idx
            
            if left < size and self._queue[left].trigger_time < self._queue[smallest].trigger_time:
                smallest = left
            if right < size and self._queue[right].trigger_time < self._queue[smallest].trigger_time:
                smallest = right
                
            if smallest != idx:
                temp = self._queue[idx]
                self._queue[idx] = self._queue[smallest]
                self._queue[smallest] = temp
                idx = smallest
            else:
                break