from typing import List

class PyFill:
    order_id: int
    price: float
    qty: float
    is_maker: bool
    
    def __init__(self, order_id: int, price: float, qty: float, is_maker: bool) -> None: ...

class PyOrderBook:
    def __init__(self) -> None: ...
    
    def add_order(self, 
                  oid: int, 
                  is_buy: bool, 
                  price: float, 
                  qty: float, 
                  initial_rank: float) -> None:
        """
        添加订单。
        :param initial_rank: 初始排队量。
           - 插队(Better): 0
           - 排队(At BBO): current_qty
           - 埋伏(Deep): 1e15
        """
        ...
        
    def cancel_order(self, oid: int) -> None:
        """根据 ID 撤单。"""
        ...
        
    def reduce_qty(self, oid: int, delta: float) -> None:
        """
        减少订单数量（不影响排队位置）。
        :param delta: 减少的量。
        """
        ...
        
    def update_bbo(self, 
                   is_buy: bool, 
                   price: float, 
                   market_qty: float) -> None:
        """
        更新盘口状态。
        包含两个逻辑：
        1. 穿价检查 (Implicit Sweep)：如果对手方价格 <= 新Bid (或 >= 新Ask)，立即成交。
        2. 惰性重置 (Lazy Reset)：唤醒深处埋伏的休眠单。
        """
        ...
        
    def execute_trade(self, 
                      maker_is_buy: bool, 
                      price: float, 
                      volume: float) -> None:
        """
        执行逐笔成交。
        包含两个逻辑：
        1. 穿价 (Sweep)：价格优于 trade_price 的挂单全成交。
        2. 触价 (Touch)：价格等于 trade_price 的挂单，扣减 rank，排到即成交。
        """
        ...
        
    def get_fills(self) -> List[PyFill]:
        """获取并清空内部积压的成交回报。"""
        ...
        
    def has_order(self, oid: int) -> bool:
        """检查订单是否存在。"""
        ...