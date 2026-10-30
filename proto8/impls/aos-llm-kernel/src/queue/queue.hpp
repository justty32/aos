// queue.hpp：【queue】排隊——kernel 自己記的帳（$AOS_STACK/queue.json）與「誰先跑」。
//
//   read_queue / write_queue   queue.json＝{"counter_runs": kernel 跑過幾次（10-25 原 runs）, "seen_at_runs": {信號: 第一次看到它是第幾次}}
//                              （沒有＝從 0 起；在但讀不懂＝QueueBad；寫：先寫暫存再改名，N-05）
//   effective                  這封信現在算幾級：level＋等了幾次÷10（10-15 定案「每等 10 拍升一級」；不封頂，等久了 low 可以超過 high）
//   order                      排隊：級數大的先 → deadline 近的先（有寫的排在沒寫的前面）→ 單子 `_metainfo` 宣告的 time_ms 短的先
//                              （有寫的在沒寫的前面，10-24）→ 等得久的先 → 先寄的先（信號字典序）
#pragma once

#include "common/common.hpp"

#include <string>
#include <vector>

namespace aos::llm_kernel {

struct Queue {
    long long runs = 0;
    Json seen_at_runs = Json::object();
};

struct Waiting {
    std::string id;
    Json letter;               // letter.json 整份
    Priority priority;
    long long seen_at_runs = 0;
};

Queue read_queue(const std::string& stack);
void write_queue(const std::string& stack, const Queue& q);

long long waited_runs(const Waiting& w, long long runs);
long long effective(const Waiting& w, long long runs);
void order(std::vector<Waiting>& ws, long long runs);

}  // namespace aos::llm_kernel
