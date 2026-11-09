// queue.hpp：【queue】排隊——kernel 自己記的帳（$AOS_STACK/queue.json）、後端最後掛的包與黏著排序。
//
//   read_queue / write_queue   queue.json＝seen_at_ms，及有時鐘才寫的 seen_at_ticks；另存 backends 的 pack／switched_at／counter_switches；兩份 seen 表都只留排隊信。
//                              （沒有＝空帳；在但讀不懂＝QueueBad；跟讀到的 JSON 不同才先寫暫存再改名，N-05）
//                              queue.json 的排法是優先序（見 order），不是先來先處理（C-54 R14，11-06）。
//   effective                  這封信現在算幾級：level＋waited_ticks÷aging_ticks（預設 3 格；不封頂）。
//                              有時鐘數格，沒有時鐘或首次記錄沒 tick 則用牆鐘差÷AOS_TICK_INTERVAL；凍住時鐘不升級。
//   order                      排隊：級數大的先 → deadline 近的先（有寫的排在沒寫的前面）→ 同 backend 黏著最後掛的包 → 包的 speed（fast → normal → slow，11-05 feat-proto）
//                              → 等得久的先 → 先寄的先（信件名稱字典序）
//                              （11-04 起 `_metainfo` 的 time_ms 那條拿掉：信裡沒單子）
#pragma once

#include "common/common.hpp"
#include "pack/pack.hpp"

#include <string>
#include <vector>

namespace aos::llm_kernel {

struct Queue {
    Json original_doc;   // 讀進來的原 JSON；檔不在＝null，寫出前比有沒有變
    Json seen_at_ms = Json::object();
    Json seen_at_ticks = Json::object();
    bool on_tick = false;
    Json backends = Json::object();
};

struct Waiting {
    std::string id;
    Json letter;               // letter.json 整份
    Priority priority;
    std::string endpoint;      // 用的代號（信的 body.endpoint，沒寫＝kernel.json 的預設）
    std::string sender;        // 信封的 sender（不是字串＝空：不認人、budget.senders 不擋）
    Json group;                // 那組設定（指示詞已解、去掉 kernel 看的 exec／slots／budget／speed／backend）＝request.json 的 endpoint
    std::string exec;          // 這組的 endpoint 函數（aos-exec 目標，絕對路徑）
    Pack pack;                 // 這組的 slots／budget／speed／backend（pack.hpp）
    long long waited_ticks = 0;   // scan 同輪共用一次時鐘快照算好，排序不再讀檔
};

Queue read_queue(const std::string& stack);
void write_queue(const std::string& stack, const Queue& q);

long long effective(const Waiting& w, long long aging_ticks);
void order(std::vector<Waiting>& ws, long long aging_ticks, const Queue& q);

}  // namespace aos::llm_kernel
