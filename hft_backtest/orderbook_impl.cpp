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

// hft_backtest/orderbook_impl.cpp

void OrderBook::execute_trade(bool maker_is_buy, int64_t price, int64_t volume) {
    if (maker_is_buy) { // Buyer is Maker (Check Bids)
        auto it = bids.begin();
        while (it != bids.end()) {
            int64_t order_price = it->first;
            
            // -----------------------------------------------------------
            // Case 1: 穿价 (Sweep) - 价格优势，完全成交
            // -----------------------------------------------------------
            // 逻辑：只要价格比成交价好，不管市场上成交了多少量，
            // 都意味着对手盘已经吃光了比我差的单子，扫到了比我好的价格。
            // 所以我是必然全成交的。
            if (order_price > price) { 
                for (auto* order : it->second) {
                    fill_queue.push_back({order->id, order->price, order->qty, true});
                    order_map.erase(order->id);
                    delete order;
                }
                it = bids.erase(it);
            } 
            // -----------------------------------------------------------
            // Case 2: 触价 (Touch) - 价格相等，受限于量
            // -----------------------------------------------------------
            else if (order_price == price) {
                auto& list = it->second;
                for (auto list_it = list.begin(); list_it != list.end(); ) {
                    Order* order = *list_it;
                    
                    order->rank -= volume; // 消耗排队
                    
                    if (order->rank < 0) {
                        // 【核心修正】：不能无脑全成，受限于 Trade 的剩余穿透力
                        // 你的排队是负数，负多少，就说明 Trade "溢出" 到了你这里多少
                        int64_t available_vol = -order->rank; 
                        
                        // 你的成交量 = min(你想要的, 市场给的)
                        int64_t fill_qty = std::min(order->qty, available_vol);
                        
                        fill_queue.push_back({order->id, price, fill_qty, true});
                        
                        order->qty -= fill_qty;
                        order->rank = 0; // 归零，等待下一笔 Trade
                        
                        // 如果吃完了，清理订单
                        if (order->qty <= 0) {
                            order_map.erase(order->id);
                            delete order;
                            list_it = list.erase(list_it);
                            continue;
                        }
                    }
                    ++list_it;
                }
                break; // 触价层处理完，不再继续向下
            } else {
                break; // 没够着
            }
        }
    } else { 
        // Seller is Maker (Check Asks) - 逻辑同上，方向相反
        auto it = asks.begin();
        while (it != asks.end()) {
            int64_t order_price = it->first;
            
            if (order_price < price) { // Sweep
                for (auto* order : it->second) {
                    fill_queue.push_back({order->id, order->price, order->qty, true});
                    order_map.erase(order->id);
                    delete order;
                }
                it = asks.erase(it);
            } else if (order_price == price) { // Touch
                auto& list = it->second;
                for (auto list_it = list.begin(); list_it != list.end(); ) {
                    Order* order = *list_it;
                    order->rank -= volume;
                    
                    if (order->rank < 0) {
                        int64_t available_vol = -order->rank;
                        int64_t fill_qty = std::min(order->qty, available_vol);
                        
                        fill_queue.push_back({order->id, price, fill_qty, true});
                        
                        order->qty -= fill_qty;
                        order->rank = 0;
                        
                        if (order->qty <= 0) {
                            order_map.erase(order->id);
                            delete order;
                            list_it = list.erase(list_it);
                            continue;
                        }
                    }
                    ++list_it;
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