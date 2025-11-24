# HftBacktest
用python写的简易高频回测框架

## 设计思路
1. 事件与事件引擎是最顶层，负责接受和推送事件
2. 所有组件都需要接入时间引擎，监听事件进行处理并可能推送事件广播处理结果
3. 事件引擎分为server和client两个，直接监听事件引擎是无延迟的
4. 模拟延迟系统通过delaybus连接两个事件引擎，实现server和client的信息互通和模拟延迟
5. 事件可以继承，但注册监听的时候会严格比较是否为同一类型。

## 模块详解
### event_engine
1. 事件驱动回测的核心组件
2. 提供注册监听方法
3. 提供put推送事件方法
4. 确保事件按顺序推送
### delay_bus
1. 高频交易回测延迟模拟的核心组件
2. 监听source event engine的事件，延迟一定时间后推送到target event engine
3. 可用于将server event engine的消息延迟传递给client event engine，如行情，成交回报等
4. 同理可用于延迟client event engine的消息，如发送订单等
### dataset
1. 定义了Data类事件，包含数据的时间戳，数据（DataFrame格式），数据源名称
MergedDataset可以组合多个数据源按时间顺序推进
### match_engine
1. 监听Submitted状态的订单和撤单指令
2. 维护限价单的排位，处理撤单和撮合成交
3. 当订单状态被成交或取消，推送最新订单状态到事件引擎
### account
1. 监听订单提交，服务器收到回报并更新订单状态
2. 监听订单成交和取消，更新订单状态
3. 监听Data:trade事件，记录每个标的的最新成交价
4. 提供接口查询订单，仓位，最新价 并注入到event_engine
### settlement_engine
1. 监听Data:fundingrate, 等各类结算数据事件触发资金费率等结算事件
2. 发出Settlement事件， 结算资金费率
### recorder
1. 监听成交事件并记录到trade.csv
2. 监听资金费率事件并记录
3. 计算相关绩效指标并记录，如保证金占用，pnl等
### stategy
1. 策略类，需要继承后实现
2. 必须实现on_data方法
3. 已经实现了send_order方法，需要注意的是创建订单请从工厂方法创建
4. 可选实现on_order，支持更加细粒度的订单处理逻辑
5. 所有回调都需要自己注册监听
### backtest_engine
1. 创建双端事件引擎
2. 构建延迟总线
3. 载入数据集
4. 添加撮合引擎
5. 添加结算引擎
6. 添加双端账户
7. 添加策略
这个顺序不能乱。乱序处理可能导致策略先监听到order回报，然后账户还没更新订单和持仓的情况