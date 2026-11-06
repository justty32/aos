// aos/util/tick.hpp：【aos-util】讀樹的 tick 時鐘，並按兩鐘規則建立與判斷期限。
//
//   now_tick           沒設 AOS_TICK＝沒時鐘；有設而缺檔或空檔＝0；壞檔＝TickBad
//   tick_interval_ms   AOS_TICK_INTERVAL 的正整數毫秒；沒設＝1000；壞值＝TickBad
//   utc_now_epoch_ms   現在的 UTC epoch 毫秒（system_clock，能寫檔跨行程比較）
//   deadline_after     有時鐘以 tick 起算，否則換成 UTC epoch 毫秒期限
//   expired            依期限的時鐘種類判斷是否到期
#pragma once

#include <optional>

namespace aos {

std::optional<long long> now_tick();
long long tick_interval_ms();
long long utc_now_epoch_ms();

struct Deadline {
    bool on_tick;   // true＝at 是樹的 tick；false＝at 是 UTC epoch 毫秒。
    long long at;
};

Deadline deadline_after(long long ticks);
bool expired(const Deadline& deadline);

}  // namespace aos
