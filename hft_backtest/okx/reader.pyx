# hft_backtest/okx/reader.pyx
# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False

import numpy as np
cimport numpy as np
from hft_backtest.event cimport Event
from hft_backtest.reader cimport DataReader
from hft_backtest.okx.event cimport OKXTrades, OKXBookticker

# 初始化 Numpy C-API
np.import_array()

cdef class OKXTradesArrayReader(DataReader):
    def __init__(self, dataset):
        """
        :param dataset: 任何迭代返回 DataFrame 的对象 (如 ParquetDataset(mode='batch'))
        """
        self.batch_iterator = iter(dataset)
        self.length = 0
        self.idx = 0
        self.current_df = None
        # 初始化时尝试加载第一批
        self.load_next_batch()

    cdef void load_next_batch(self):
        try:
            # 1. 跨语言调用：获取下一个 DataFrame Batch
            df = next(self.batch_iterator)
            
            # 2. 绑定内存视图 (极快)
            self.created_times = df['created_time'].values.astype(np.int64)
            self.trade_ids = df['trade_id'].values.astype(np.int64)
            self.prices = df['price'].values.astype(np.float64)
            self.sizes = df['size'].values.astype(np.float64)
            self.instrument_names = df['instrument_name'].values
            self.sides = df['side'].values
            
            # 3. 更新状态
            self.current_df = df # 重要：保活
            self.length = len(df)
            self.idx = 0
            
        except StopIteration:
            self.length = 0
            self.current_df = None

    cdef Event fetch_next(self):
        cdef OKXTrades evt
        
        # 1. 检查库存
        if self.idx >= self.length:
            self.load_next_batch()
            
        # 2. 检查是否读完
        if self.length == 0:
            return None
            
        # 3. 极速创建与赋值
        evt = OKXTrades.__new__(OKXTrades)
        
        evt.timestamp = self.created_times[self.idx]
        evt.trade_id = self.trade_ids[self.idx]
        evt.price = self.prices[self.idx]
        evt.size = self.sizes[self.idx]
        evt.symbol = self.instrument_names[self.idx]
        evt.side = self.sides[self.idx]
        
        self.idx += 1
        return evt

cdef class OKXBooktickerArrayReader(DataReader):
    def __init__(self, dataset):
        self.batch_iterator = iter(dataset)
        self.length = 0
        self.idx = 0
        self.current_df = None
        # 初始化数据指针数组为 NULL
        for i in range(100):
            self.data_ptrs[i] = NULL
        self.load_next_batch()

    cdef void load_next_batch(self):
        # 【修正】声明必须提到函数顶部
        cdef int ptr_idx = 0
        cdef double[:] view
        
        try:
            df = next(self.batch_iterator)
            
            # 基础列绑定
            self.timestamps = df['timestamp'].values.astype(np.int64)
            self.symbols = df['symbol'].values
            if 'local_timestamp' in df.columns:
                self.local_timestamps = df['local_timestamp'].values.astype(np.int64)
            else:
                self.local_timestamps = np.zeros(len(df), dtype=np.int64)

            # 绑定深度数据指针
            self._keep_alive_refs = [] # 清空旧引用
            ptr_idx = 0 # 重置索引
            
            # 遍历 1-25 档
            for i in range(1, 26):
                for col_name in [f'ask_price_{i}', f'ask_amount_{i}', f'bid_price_{i}', f'bid_amount_{i}']:
                    if col_name in df.columns:
                        arr = df[col_name].values.astype(np.float64)
                    else:
                        arr = np.zeros(len(df), dtype=np.float64)
                    
                    # 放入列表防止 GC
                    self._keep_alive_refs.append(arr)
                    
                    # 获取 C 指针
                    view = arr
                    if view.shape[0] > 0:
                        self.data_ptrs[ptr_idx] = &view[0]
                    else:
                        self.data_ptrs[ptr_idx] = NULL
                    ptr_idx += 1
            
            self.current_df = df
            self.length = len(df)
            self.idx = 0
            
        except StopIteration:
            self.length = 0
            self.current_df = None

    cdef Event fetch_next(self):
        cdef OKXBookticker evt
        cdef Py_ssize_t i
        
        if self.idx >= self.length:
            self.load_next_batch()
            
        if self.length == 0:
            return None

        # 【修正】声明提至顶部，这里只赋值
        evt = OKXBookticker.__new__(OKXBookticker)
        i = self.idx
        
        evt.timestamp = self.timestamps[i]
        evt.symbol = self.symbols[i]
        evt.local_timestamp = self.local_timestamps[i]
        
        # 暴力赋值 1-25 档
        if self.data_ptrs[0] != NULL:
            # Depth 1
            evt.ask_price_1 = self.data_ptrs[0][i]; evt.ask_amount_1 = self.data_ptrs[1][i]
            evt.bid_price_1 = self.data_ptrs[2][i]; evt.bid_amount_1 = self.data_ptrs[3][i]
            # Depth 2
            evt.ask_price_2 = self.data_ptrs[4][i]; evt.ask_amount_2 = self.data_ptrs[5][i]
            evt.bid_price_2 = self.data_ptrs[6][i]; evt.bid_amount_2 = self.data_ptrs[7][i]
            # Depth 3
            evt.ask_price_3 = self.data_ptrs[8][i]; evt.ask_amount_3 = self.data_ptrs[9][i]
            evt.bid_price_3 = self.data_ptrs[10][i]; evt.bid_amount_3 = self.data_ptrs[11][i]
            # Depth 4
            evt.ask_price_4 = self.data_ptrs[12][i]; evt.ask_amount_4 = self.data_ptrs[13][i]
            evt.bid_price_4 = self.data_ptrs[14][i]; evt.bid_amount_4 = self.data_ptrs[15][i]
            # Depth 5
            evt.ask_price_5 = self.data_ptrs[16][i]; evt.ask_amount_5 = self.data_ptrs[17][i]
            evt.bid_price_5 = self.data_ptrs[18][i]; evt.bid_amount_5 = self.data_ptrs[19][i]
            # Depth 6
            evt.ask_price_6 = self.data_ptrs[20][i]; evt.ask_amount_6 = self.data_ptrs[21][i]
            evt.bid_price_6 = self.data_ptrs[22][i]; evt.bid_amount_6 = self.data_ptrs[23][i]
            # Depth 7
            evt.ask_price_7 = self.data_ptrs[24][i]; evt.ask_amount_7 = self.data_ptrs[25][i]
            evt.bid_price_7 = self.data_ptrs[26][i]; evt.bid_amount_7 = self.data_ptrs[27][i]
            # Depth 8
            evt.ask_price_8 = self.data_ptrs[28][i]; evt.ask_amount_8 = self.data_ptrs[29][i]
            evt.bid_price_8 = self.data_ptrs[30][i]; evt.bid_amount_8 = self.data_ptrs[31][i]
            # Depth 9
            evt.ask_price_9 = self.data_ptrs[32][i]; evt.ask_amount_9 = self.data_ptrs[33][i]
            evt.bid_price_9 = self.data_ptrs[34][i]; evt.bid_amount_9 = self.data_ptrs[35][i]
            # Depth 10
            evt.ask_price_10 = self.data_ptrs[36][i]; evt.ask_amount_10 = self.data_ptrs[37][i]
            evt.bid_price_10 = self.data_ptrs[38][i]; evt.bid_amount_10 = self.data_ptrs[39][i]
            # Depth 11
            evt.ask_price_11 = self.data_ptrs[40][i]; evt.ask_amount_11 = self.data_ptrs[41][i]
            evt.bid_price_11 = self.data_ptrs[42][i]; evt.bid_amount_11 = self.data_ptrs[43][i]
            # Depth 12
            evt.ask_price_12 = self.data_ptrs[44][i]; evt.ask_amount_12 = self.data_ptrs[45][i]
            evt.bid_price_12 = self.data_ptrs[46][i]; evt.bid_amount_12 = self.data_ptrs[47][i]
            # Depth 13
            evt.ask_price_13 = self.data_ptrs[48][i]; evt.ask_amount_13 = self.data_ptrs[49][i]
            evt.bid_price_13 = self.data_ptrs[50][i]; evt.bid_amount_13 = self.data_ptrs[51][i]
            # Depth 14
            evt.ask_price_14 = self.data_ptrs[52][i]; evt.ask_amount_14 = self.data_ptrs[53][i]
            evt.bid_price_14 = self.data_ptrs[54][i]; evt.bid_amount_14 = self.data_ptrs[55][i]
            # Depth 15
            evt.ask_price_15 = self.data_ptrs[56][i]; evt.ask_amount_15 = self.data_ptrs[57][i]
            evt.bid_price_15 = self.data_ptrs[58][i]; evt.bid_amount_15 = self.data_ptrs[59][i]
            # Depth 16
            evt.ask_price_16 = self.data_ptrs[60][i]; evt.ask_amount_16 = self.data_ptrs[61][i]
            evt.bid_price_16 = self.data_ptrs[62][i]; evt.bid_amount_16 = self.data_ptrs[63][i]
            # Depth 17
            evt.ask_price_17 = self.data_ptrs[64][i]; evt.ask_amount_17 = self.data_ptrs[65][i]
            evt.bid_price_17 = self.data_ptrs[66][i]; evt.bid_amount_17 = self.data_ptrs[67][i]
            # Depth 18
            evt.ask_price_18 = self.data_ptrs[68][i]; evt.ask_amount_18 = self.data_ptrs[69][i]
            evt.bid_price_18 = self.data_ptrs[70][i]; evt.bid_amount_18 = self.data_ptrs[71][i]
            # Depth 19
            evt.ask_price_19 = self.data_ptrs[72][i]; evt.ask_amount_19 = self.data_ptrs[73][i]
            evt.bid_price_19 = self.data_ptrs[74][i]; evt.bid_amount_19 = self.data_ptrs[75][i]
            # Depth 20
            evt.ask_price_20 = self.data_ptrs[76][i]; evt.ask_amount_20 = self.data_ptrs[77][i]
            evt.bid_price_20 = self.data_ptrs[78][i]; evt.bid_amount_20 = self.data_ptrs[79][i]
            # Depth 21
            evt.ask_price_21 = self.data_ptrs[80][i]; evt.ask_amount_21 = self.data_ptrs[81][i]
            evt.bid_price_21 = self.data_ptrs[82][i]; evt.bid_amount_21 = self.data_ptrs[83][i]
            # Depth 22
            evt.ask_price_22 = self.data_ptrs[84][i]; evt.ask_amount_22 = self.data_ptrs[85][i]
            evt.bid_price_22 = self.data_ptrs[86][i]; evt.bid_amount_22 = self.data_ptrs[87][i]
            # Depth 23
            evt.ask_price_23 = self.data_ptrs[88][i]; evt.ask_amount_23 = self.data_ptrs[89][i]
            evt.bid_price_23 = self.data_ptrs[90][i]; evt.bid_amount_23 = self.data_ptrs[91][i]
            # Depth 24
            evt.ask_price_24 = self.data_ptrs[92][i]; evt.ask_amount_24 = self.data_ptrs[93][i]
            evt.bid_price_24 = self.data_ptrs[94][i]; evt.bid_amount_24 = self.data_ptrs[95][i]
            # Depth 25
            evt.ask_price_25 = self.data_ptrs[96][i]; evt.ask_amount_25 = self.data_ptrs[97][i]
            evt.bid_price_25 = self.data_ptrs[98][i]; evt.bid_amount_25 = self.data_ptrs[99][i]
            
        self.idx += 1
        return evt