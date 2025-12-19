#include "orderbook.h"

OrderBook::OrderBook() {}

OrderBook::~OrderBook() {
    for (auto& pair : order_map) {
        delete pair.second;
    }
}

void OrderBook::add_order(uint64_t id, bool is_buy, int64_t price, int64_t qty, int64_t initial_rank) {
    if (order_map.find(id) != order_map.end()) return;

    Order* order = new Order{id, is_buy, price, qty, initial_rank};
    order_map[id] = order;

    if (is_buy) bids[price].push_back(order);
    else asks[price].push_back(order);
}

void OrderBook::cancel_order(uint64_t id) {
    auto it = order_map.find(id);
    if (it == order_map.end()) return;

    Order* order = it->second;
    _remove_order_from_book(order);
    delete order;
    order_map.erase(it);
}

void OrderBook::_remove_order_from_book(Order* order) {
    if (order->is_buy) {
        auto& list = bids[order->price];
        // 依然需要 remove 逻辑
        for (auto it = list.begin(); it != list.end(); ++it) {
            if (*it == order) {
                list.erase(it);
                break;
            }
        }
        if (list.empty()) bids.erase(order->price);
    } else {
        auto& list = asks[order->price];
        for (auto it = list.begin(); it != list.end(); ++it) {
            if (*it == order) {
                list.erase(it);
                break;
            }
        }
        if (list.empty()) asks.erase(order->price);
    }
}

void OrderBook::reduce_qty(uint64_t id, int64_t delta) {
    auto it = order_map.find(id);
    if (it == order_map.end()) return;
    Order* order = it->second;
    order->qty -= delta;
    if (order->qty <= 0) cancel_order(id);
}

void OrderBook::update_bbo(bool is_buy, int64_t price, int64_t market_qty) {
    // 1. 穿价检查 (整数比较，无需 epsilon)
    if (is_buy) { // New Bid
        auto it = asks.begin();
        // 如果卖单价 <= 买一价
        while (it != asks.end() && it->first <= price) {
            for (auto* order : it->second) {
                fill_queue.push_back({order->id, order->price, order->qty, true});
                order_map.erase(order->id);
                delete order;
            }
            it = asks.erase(it);
        }
    } else { // New Ask
        auto it = bids.begin();
        // 如果买单价 >= 卖一价
        while (it != bids.end() && it->first >= price) {
            for (auto* order : it->second) {
                fill_queue.push_back({order->id, order->price, order->qty, true});
                order_map.erase(order->id);
                delete order;
            }
            it = bids.erase(it);
        }
    }

    // 2. 惰性重置
    if (is_buy) {
        auto it = bids.find(price);
        if (it != bids.end()) {
            for (auto* order : it->second) {
                if (order->rank >= HUGE_RANK) order->rank = market_qty;
            }
        }
    } else {
        auto it = asks.find(price);
        if (it != asks.end()) {
            for (auto* order : it->second) {
                if (order->rank >= HUGE_RANK) order->rank = market_qty;
            }
        }
    }
}

void OrderBook::execute_trade(bool maker_is_buy, int64_t price, int64_t volume) {
    if (maker_is_buy) { // Buyer is Maker, check Bids
        auto it = bids.begin();
        while (it != bids.end()) {
            int64_t order_price = it->first;
            
            // 穿价: 买单价 > 成交价
            if (order_price > price) {
                for (auto* order : it->second) {
                    fill_queue.push_back({order->id, order->price, order->qty, true});
                    order_map.erase(order->id);
                    delete order;
                }
                it = bids.erase(it);
            } 
            // 触价: 买单价 == 成交价
            else if (order_price == price) {
                // 注意：vector 删除元素时迭代器失效问题，这里用索引遍历安全
                // 或者重新设计数据结构。这里简单处理：
                // 为了避免 vector erase 的开销和迭代器问题，我们收集要删除的 ID
                // 但考虑到 HFT 回测同价单不多，且 rank 扣减是顺序的
                
                auto& list = it->second;
                for (auto list_it = list.begin(); list_it != list.end(); ) {
                    Order* order = *list_it;
                    order->rank -= volume;
                    
                    if (order->rank < 0) {
                        fill_queue.push_back({order->id, price, order->qty, true});
                        order_map.erase(order->id);
                        delete order;
                        list_it = list.erase(list_it); // 返回下一个有效迭代器
                    } else {
                        ++list_it;
                    }
                }
                break; // 触价层处理完即止
            } else {
                break; // 没够着
            }
        }
    } else { // Seller is Maker, check Asks
        auto it = asks.begin();
        while (it != asks.end()) {
            int64_t order_price = it->first;
            
            if (order_price < price) { // 穿价
                for (auto* order : it->second) {
                    fill_queue.push_back({order->id, order->price, order->qty, true});
                    order_map.erase(order->id);
                    delete order;
                }
                it = asks.erase(it);
            } else if (order_price == price) { // 触价
                auto& list = it->second;
                for (auto list_it = list.begin(); list_it != list.end(); ) {
                    Order* order = *list_it;
                    order->rank -= volume;
                    if (order->rank < 0) {
                        fill_queue.push_back({order->id, price, order->qty, true});
                        order_map.erase(order->id);
                        delete order;
                        list_it = list.erase(list_it);
                    } else {
                        ++list_it;
                    }
                }
                break;
            } else {
                break;
            }
        }
    }
}

std::vector<Fill> OrderBook::get_fills() {
    std::vector<Fill> result = fill_queue;
    fill_queue.clear();
    return result;
}

bool OrderBook::has_order(uint64_t id) {
    return order_map.find(id) != order_map.end();
}