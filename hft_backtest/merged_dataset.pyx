# hft_backtest/merged_dataset.pyx
# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False

from cpython.ref cimport PyObject, Py_INCREF, Py_DECREF
from hft_backtest.event cimport Event
from hft_backtest.reader cimport DataReader, PyDatasetWrapper

cdef class MergedDataset(DataReader):
    """
    高性能多路归并数据集 (Cython 简化版)
    """
    
    def __init__(self, list datasets):
        # 直接用 Python list 存，无需复杂的 vector<PyObject*>
        self._sources = []
        
        for ds in datasets:
            # 如果已经是高性能 Reader，直接存
            if isinstance(ds, DataReader):
                self._sources.append(ds)
            else:
                # 否则包装一下
                self._sources.append(PyDatasetWrapper(ds))
                
        self._initialized = False
        self._cur_event = None
        self._cur_idx = -1

    # 【核心】高速 C 接口
    cdef Event fetch_next(self):
        # 1. 初始化
        if not self._initialized:
            self._init_heap()
            self._initialized = True
            return self._cur_event

        # 2. 从当前数据源取下一个
        cdef Event next_event = None
        cdef DataReader current_source
        
        # 【关键】从 list 中取出对象，并强转为 C 类型
        # 这一步开销极小，且内存安全
        current_source = <DataReader>self._sources[self._cur_idx]
        
        # 极速调用
        next_event = current_source.fetch_next()
        
        if next_event is None:
            # 当前源耗尽
            if self._heap.empty():
                self._cur_event = None
                return None
            else:
                self._pop_heap_to_current()
                return self._cur_event

        # 3. 比较逻辑 (堆维护)
        if self._heap.empty():
            self._cur_event = next_event
        else:
            # 比较新事件与堆顶
            if next_event.timestamp < self._heap.front().timestamp:
                self._cur_event = next_event
            elif next_event.timestamp == self._heap.front().timestamp:
                # 时间相同，索引小的优先（稳定性）
                if self._cur_idx < self._heap.front().source_idx:
                    self._cur_event = next_event
                else:
                    self._push(next_event.timestamp, self._cur_idx, next_event)
                    self._pop_heap_to_current()
            else:
                # 新事件更晚，入堆，弹出堆顶
                self._push(next_event.timestamp, self._cur_idx, next_event)
                self._pop_heap_to_current()
        
        return self._cur_event

    cdef void _init_heap(self):
        cdef int i
        cdef int n = len(self._sources)
        cdef Event evt
        cdef vector[MergeItem] temp_candidates
        cdef MergeItem item
        cdef DataReader dr
        
        for i in range(n):
            # 类型转换
            dr = <DataReader>self._sources[i]
            evt = dr.fetch_next()
            
            if evt is not None:
                item.timestamp = evt.timestamp
                item.source_idx = i
                item.event = <PyObject*>evt
                Py_INCREF(evt) # 放入堆（vector）时必须增加引用
                temp_candidates.push_back(item)

        if temp_candidates.empty():
            self._cur_event = None
            return

        # 找出最小的做为当前事件
        cdef int best_idx = 0
        cdef long min_ts = temp_candidates[0].timestamp
        cdef int min_src_idx = temp_candidates[0].source_idx

        for i in range(1, temp_candidates.size()):
            if temp_candidates[i].timestamp < min_ts:
                min_ts = temp_candidates[i].timestamp
                best_idx = i
                min_src_idx = temp_candidates[i].source_idx
            elif temp_candidates[i].timestamp == min_ts:
                if temp_candidates[i].source_idx < min_src_idx:
                    best_idx = i
                    min_src_idx = temp_candidates[i].source_idx

        cdef MergeItem winner = temp_candidates[best_idx]
        
        # 转移给 _cur_event (Python 对象自动管理引用)
        self._cur_event = <Event>winner.event
        self._cur_idx = winner.source_idx
        
        # 抵消 push_back 时的 INCREF
        Py_DECREF(self._cur_event)

        # 其余入堆
        for i in range(temp_candidates.size()):
            if i == best_idx:
                continue
            self._heap.push_back(temp_candidates[i])
        
        # 建堆
        cdef int j
        for j in range(self._heap.size() // 2, -1, -1):
            self._sift_down(j)

    cdef void _pop_heap_to_current(self):
        cdef MergeItem top = self._heap.front()
        
        self._cur_event = <Event>top.event
        self._cur_idx = top.source_idx
        
        cdef MergeItem last = self._heap.back()
        self._heap.pop_back()
        
        if not self._heap.empty():
            self._heap[0] = last
            self._sift_down(0)
            
        # 堆不再持有该引用，转移给 _cur_event
        Py_DECREF(self._cur_event)

    # --- 堆操作 (保持精简) ---

    cdef void _push(self, long timestamp, int source_idx, Event event):
        cdef MergeItem item
        item.timestamp = timestamp
        item.source_idx = source_idx
        item.event = <PyObject*>event
        
        Py_INCREF(event) # 只要进堆，就必须 INCREF
        self._heap.push_back(item)
        self._sift_up(self._heap.size() - 1)

    cdef void _sift_up(self, size_t idx):
        cdef size_t parent
        cdef MergeItem temp
        while idx > 0:
            parent = (idx - 1) >> 1
            if self._less(idx, parent):
                temp = self._heap[idx]
                self._heap[idx] = self._heap[parent]
                self._heap[parent] = temp
                idx = parent
            else:
                break

    cdef void _sift_down(self, size_t idx):
        cdef size_t left, right, smallest
        cdef size_t size = self._heap.size()
        cdef MergeItem temp
        while True:
            left = (idx << 1) + 1
            right = left + 1
            smallest = idx
            if left < size and self._less(left, smallest):
                smallest = left
            if right < size and self._less(right, smallest):
                smallest = right
            if smallest != idx:
                temp = self._heap[idx]
                self._heap[idx] = self._heap[smallest]
                self._heap[smallest] = temp
                idx = smallest
            else:
                break

    cdef inline bint _less(self, size_t i, size_t j):
        if self._heap[i].timestamp < self._heap[j].timestamp:
            return True
        elif self._heap[i].timestamp == self._heap[j].timestamp:
            return self._heap[i].source_idx < self._heap[j].source_idx
        return False