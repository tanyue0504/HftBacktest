#ifndef ORDERBOOK_H
#define ORDERBOOK_H

#include <map>
#include <unordered_map>
#include <vector>
#include <cmath>
#include <algorithm>
#include <cstdint> // 引入 int64_t

// 使用 int64_t 的最大值作为休眠单标记
// 假设有 18 位精度，9e18 足够大
const int64_t HUGE_RANK = 4000000000000000000LL; 

struct Order {
    uint64_t id;
    bool is_buy;
    int64_t price; // 整数价格
    int64_t qty;   // 整数数量
    int64_t rank;  // 整数排队量
};

struct Fill {
    uint64_t order_id;
    int64_t price;
    int64_t qty;
    bool is_maker;
};

class OrderBook {
private:
    std::unordered_map<uint64_t, Order*> order_map;
    
    // 价格也是 int64_t
    std::map<int64_t, std::vector<Order*>, std::greater<int64_t>> bids;
    std::map<int64_t, std::vector<Order*>, std::less<int64_t>> asks;

    std::vector<Fill> fill_queue;

    void _remove_order_from_book(Order* order);

public:
    OrderBook();
    ~OrderBook();

    // 参数全部改为 int64_t
    void add_order(uint64_t id, bool is_buy, int64_t price, int64_t qty, int64_t initial_rank);
    void cancel_order(uint64_t id);
    void reduce_qty(uint64_t id, int64_t delta);

    void update_bbo(bool is_buy, int64_t price, int64_t market_qty);
    void execute_trade(bool maker_is_buy, int64_t price, int64_t volume);

    std::vector<Fill> get_fills();
    bool has_order(uint64_t id);
};

#endif