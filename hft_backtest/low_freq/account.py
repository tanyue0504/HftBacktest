from hft_backtest import Order, OrderState, Data, Account


class BarAccount(Account):
    """
    低频账户类
    支持自定义字段名、数据源名称，以及可选的资金费处理

    资金费处理：
    - 如果配置了 funding_data_source，Account 会监听资金费数据
    - 计算公式：funding_fee = position_qty * price * funding_rate
    - 通过 get_funding_fees() 接口暴露给其他组件（如Recorder）
    """

    def __init__(
        self,
        symbol_field: str,
        close_field: str,
        data_source_name: str = "bars",
        # 资金费相关配置（可选）
        funding_data_source: str = None,  # 如 "funding"，None表示不处理资金费
        funding_rate_field: str = "last_funding_rate",
    ):
        self.symbol_field = symbol_field
        self.close_field = close_field
        self.data_source_name = data_source_name

        # 资金费配置
        self.funding_data_source = funding_data_source
        self.funding_rate_field = funding_rate_field

        self.order_dict: dict[int, Order] = {}
        self.position_dict: dict[str, int] = {}
        self.price_dict: dict[str, float] = {}

        # 资金费累计（每次快照后由Recorder清空）
        self.funding_fee_dict: dict[str, float] = {}

    def on_order(self, order: Order):
        assert isinstance(order, Order)
        if order.is_cancel:
            return

        state = order.state
        assert state != OrderState.CREATED

        if state in (OrderState.SUBMITTED, OrderState.RECEIVED):
            self.order_dict[order.order_id] = order
            return
        elif state == OrderState.FILLED:
            # 更新持仓
            pos = self.position_dict[order.symbol] = self.position_dict.get(order.symbol, 0) + order.quantity_int
            if pos == 0:
                del self.position_dict[order.symbol]

        # 安全删除，防止 KeyError
        if order.order_id in self.order_dict:
            del self.order_dict[order.order_id]

    def on_data(self, data: Data):
        # 处理K线数据：更新价格
        if data.name == self.data_source_name:
            line = data.data
            symbol = getattr(line, self.symbol_field, None)
            close_px = getattr(line, self.close_field, None)
            if symbol is not None and close_px is not None:
                self.price_dict[symbol] = close_px

        # 处理资金费数据（如果配置了）
        elif self.funding_data_source and data.name == self.funding_data_source:
            self._process_funding(data)

    def _process_funding(self, data: Data):
        """处理资金费结算事件"""
        line = data.data
        symbol = getattr(line, self.symbol_field, None)
        funding_rate = getattr(line, self.funding_rate_field, None)

        if symbol is None or funding_rate is None:
            return

        # 检查是否有该标的的持仓
        position_qty = self.position_dict.get(symbol, 0)
        if position_qty == 0:
            return

        # 获取价格
        price = self.price_dict.get(symbol, 0.0)
        if price <= 0:
            return

        # 计算资金费：fee = position_qty * price * funding_rate
        # 转换持仓量（考虑SCALER）
        qty = position_qty / Order.SCALER
        funding_fee = qty * price * funding_rate

        # 累加到资金费字典
        self.funding_fee_dict[symbol] = self.funding_fee_dict.get(symbol, 0.0) + funding_fee

    def get_orders(self):
        return self.order_dict.copy()

    def get_positions(self):
        return {k: v / Order.SCALER for k, v in self.position_dict.items()}

    def get_prices(self):
        return self.price_dict.copy()

    def get_funding_fees(self):
        """获取累计资金费（由Recorder调用后清空）"""
        return self.funding_fee_dict.copy()

    def clear_funding_fees(self):
        """清空资金费记录（Recorder快照后调用）"""
        self.funding_fee_dict.clear()
