class Event:
    timestamp: int
    source: int
    producer: int

    def __init__(self, timestamp: int) -> None: ...
    
    def derive(self) -> Event:
        """
        创建一个当前事件的快速浅拷贝，并重置 timestamp, source, producer 为 0。
        
        【注意/Warning】:
        此方法使用了底层的 C 内存拷贝优化。
        1. 它只保证复制在 .pxd 中定义的 C 字段 (cdef public fields)。
        2. 如果你在 Python 子类中动态添加了属性 (self.x = ...)，这些属性**不会**被正确复制或引用计数管理。
        3. 如果需要携带额外数据，请在 Cython 子类中定义 cdef public 字段，或理解 derive() 会丢弃动态属性。
        """
        ...

    def __lt__(self, other: Event) -> bool: ...