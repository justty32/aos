// queue.hpp：【queue】排隊——kernel 自己記的帳（$AOS_STACK/queue.json）與「誰先跑」。
//
//   read_queue / write_queue   queue.json＝{"counter_runs": kernel 跑過幾次（10-25 原 runs）, "seen_at_runs": {信件名稱: 第一次看到它是第幾次}}
//                              （沒有＝從 0 起；在但讀不懂＝QueueBad；寫：先寫暫存再改名，N-05）
//   effective                  這封信現在算幾級：level＋等了幾次÷10（10-15 定案「每等 10 拍升一級」；不封頂，等久了 low 可以超過 high）
//   order                      排隊：級數大的先 → deadline 近的先（有寫的排在沒寫的前面）→ 等得久的先 → 先寄的先（信件名稱字典序）
//                              （11-04 起 `_metainfo` 的 time_ms 那條拿掉：信裡沒單子）
#pragma once

#include "common/common.hpp"
#include "pack/pack.hpp"

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
    std::string endpoint;      // 用的代號（信的 body.endpoint，沒寫＝kernel.json 的預設）
    Json group;                // 那組設定（指示詞已解、去掉 kernel 看的 exec／slots／budget／speed）＝request.json 的 endpoint
    std::string exec;          // 這組的 endpoint 函數（aos-exec 目標，絕對路徑）
    Pack pack;                 // 這組的 slots／budget／speed（pack.hpp）
    long long seen_at_runs = 0;
};

Queue read_queue(const std::string& stack);
void write_queue(const std::string& stack, const Queue& q);

long long waited_runs(const Waiting& w, long long runs);
long long effective(const Waiting& w, long long runs);
void order(std::vector<Waiting>& ws, long long runs);

}  // namespace aos::llm_kernel
