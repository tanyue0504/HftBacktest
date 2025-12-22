class Event:
    timestamp: int
    source: int
    producer: int

    def __init__(self, timestamp: int) -> None: ...
    
    def derive(self) -> Event:
        """
        创建一个当前事件的浅拷贝，并重置 timestamp, source, producer 为 0。
        """
        ...

    def __lt__(self, other: Event) -> bool: ...