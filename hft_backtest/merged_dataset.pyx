# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False

from cpython.ref cimport PyObject, Py_INCREF, Py_DECREF
from hft_backtest.event cimport Event

cdef class MergedDataset:
    """
    高性能多路归并数据集 (Cython 版)
    
    实现逻辑：
    维护一个“当前胜者”(Current Winner) 和一个“挑战者堆”(Challenger Heap)。
    只有当当前胜者耗尽或被堆中更小的时间戳挑战成功时，才进行堆操作。
    """
    
    def __init__(self, *datasets):
        # 保存迭代器
        self._iters = [iter(ds) for ds in datasets]
        self._initialized = False
        self._cur_event = None
        self._cur_idx = -1
        self._cur_iter = None

    def __iter__(self):
        # 允许迭代器协议
        return self

    def __next__(self):
        # 1. 初始化
        if not self._initialized:
            self._init_heap()
            self._initialized = True
            
            if self._cur_event is None:
                raise StopIteration
            
            return self._cur_event

        # 2. 尝试从当前胜者的数据源获取下一个事件
        cdef Event next_event = None
        cdef object iterator = self._cur_iter
        
        try:
            next_event = <Event>next(iterator)
        except StopIteration:
            if self._heap.empty():
                self._cur_event = None
                raise StopIteration
            else:
                self._pop_heap_to_current()
                return self._cur_event
        except TypeError:
            raise TypeError(f"Dataset yielded non-Event object: {type(next_event)}")

        # 3. 比较：新取出的事件 vs 堆顶事件
        if self._heap.empty():
            self._cur_event = next_event
        else:
            # [修复核心] 引入稳定性比较
            # 获取堆顶信息
            # 只有当 (new_ts < top_ts) 或者 (new_ts == top_ts 且 new_idx < top_idx) 时，才连任
            # 否则，入堆，并弹出更小（或索引更小）的堆顶
            
            if next_event.timestamp < self._heap.front().timestamp:
                self._cur_event = next_event
            elif next_event.timestamp == self._heap.front().timestamp:
                # 稳定性检查：时间相同，比拼索引
                if self._cur_idx < self._heap.front().source_idx:
                    self._cur_event = next_event
                else:
                    # 堆顶的索引更小，应该让位
                    self._push(next_event.timestamp, self._cur_idx, next_event)
                    self._pop_heap_to_current()
            else:
                # 新事件时间更晚，入堆
                self._push(next_event.timestamp, self._cur_idx, next_event)
                self._pop_heap_to_current()
        
        return self._cur_event

    cdef void _init_heap(self):
        """初始化：从所有源预读第一个元素"""
        cdef int i
        cdef int n = len(self._iters)
        cdef Event evt
        
        # 临时收集所有头元素
        # 我们不能直接入堆，因为需要找出最小的作为初始 _cur_event
        # 其余的入堆
        
        cdef vector[MergeItem] temp_candidates
        cdef MergeItem item
        
        for i in range(n):
            try:
                evt = <Event>next(self._iters[i])
                item.timestamp = evt.timestamp
                item.source_idx = i
                item.event = <PyObject*>evt
                Py_INCREF(evt) # 暂时持有引用
                temp_candidates.push_back(item)
            except StopIteration:
                continue

        if temp_candidates.empty():
            self._cur_event = None
            return

        # 找出最小的
        cdef int best_idx = 0
        cdef long min_ts = temp_candidates[0].timestamp
        cdef int min_src_idx = temp_candidates[0].source_idx # 用于相同时间戳比较

        for i in range(1, temp_candidates.size()):
            if temp_candidates[i].timestamp < min_ts:
                min_ts = temp_candidates[i].timestamp
                best_idx = i
                min_src_idx = temp_candidates[i].source_idx
            elif temp_candidates[i].timestamp == min_ts:
                # 稳定排序：时间戳相同，索引小的优先
                if temp_candidates[i].source_idx < min_src_idx:
                    best_idx = i
                    min_src_idx = temp_candidates[i].source_idx

        # 设置当前胜者
        cdef MergeItem winner = temp_candidates[best_idx]
        self._cur_event = <Event>winner.event
        self._cur_idx = winner.source_idx
        self._cur_iter = self._iters[self._cur_idx]
        
        # 此时我们将引用权转移给 self._cur_event (它是 Python 对象，自动管理)
        # 所以需要 DECREF 抵消掉上面 push 时的 INCREF
        Py_DECREF(self._cur_event) 

        # 其余入堆
        for i in range(temp_candidates.size()):
            if i == best_idx:
                continue
            
            # 直接 push 到成员变量 _heap，并保持引用计数 (所有权转移给堆)
            self._heap.push_back(temp_candidates[i])
        
        # 建堆
        # 从后往前 sift_down 是 O(N) 建堆，这里简单点逐个插入或全量排序均可
        # 由于我们手动维护堆，这里手动调整一下
        # 实际上上面的 push_back 是无序的，我们需要 heapify
        # 简单的做法：从 size/2 开始 sift_down
        cdef int j
        for j in range(self._heap.size() // 2, -1, -1):
            self._sift_down(j)

    cdef void _pop_heap_to_current(self):
        """将堆顶弹出并设置为当前胜者"""
        cdef MergeItem top = self._heap.front()
        
        # 转移所有权：堆 -> _cur_event
        self._cur_event = <Event>top.event
        self._cur_idx = top.source_idx
        self._cur_iter = self._iters[self._cur_idx]
        
        # 堆操作：尾部移到头部
        cdef MergeItem last = self._heap.back()
        self._heap.pop_back()
        
        if not self._heap.empty():
            self._heap[0] = last
            self._sift_down(0)
            
        # 注意：这里不需要 Py_DECREF(top.event)，因为我们要把它赋给 self._cur_event
        # PyObject* -> object 转换会自动 INCREF 吗？
        # 在 Cython 中， casting <Event>ptr 会创建一个新的引用 (INCREF)
        # 所以我们需要释放堆持有的那个引用
        Py_DECREF(self._cur_event)

    # --- 堆操作 (与 DelayBus 类似) ---

    cdef void _push(self, long timestamp, int source_idx, Event event):
        cdef MergeItem item
        item.timestamp = timestamp
        item.source_idx = source_idx
        item.event = <PyObject*>event
        
        Py_INCREF(event) # 堆持有引用
        self._heap.push_back(item)
        self._sift_up(self._heap.size() - 1)

    cdef void _sift_up(self, size_t idx):
        cdef size_t parent
        cdef MergeItem temp
        while idx > 0:
            parent = (idx - 1) >> 1
            # 比较：时间戳优先，索引次之 (保持稳定性)
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
        """比较堆中两个元素的大小 (timestamp, source_idx)"""
        if self._heap[i].timestamp < self._heap[j].timestamp:
            return True
        elif self._heap[i].timestamp == self._heap[j].timestamp:
            return self._heap[i].source_idx < self._heap[j].source_idx
        return False