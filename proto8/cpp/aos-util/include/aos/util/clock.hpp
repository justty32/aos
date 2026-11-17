// aos/util/clock.hpp：【aos-util】讀樹的時鐘，並按兩鐘規則建立與判斷期限。
//
//   now_cycle           沒設 AOS_CLOCK＝沒時鐘；缺檔＝warning 且 0（每行程每路徑一次）；空檔＝0；壞檔＝ClockBad
//   clock_interval_ms   AOS_CLOCK_INTERVAL 的正整數毫秒；沒設＝1000；壞值＝ClockBad
//   utc_now_epoch_ms   現在的 UTC epoch 毫秒（system_clock，能寫檔跨行程比較）
//   deadline_after     有時鐘以 cycle 起算，否則換成 UTC epoch 毫秒期限
//   expired            依期限的時鐘種類判斷是否到期
#pragma once

#include <optional>

namespace aos {

std::optional<long long> now_cycle();
long long clock_interval_ms();
long long utc_now_epoch_ms();

struct Deadline {
    bool on_clock;   // true＝at 是樹的 cycle；false＝at 是 UTC epoch 毫秒。
    long long at;
};

Deadline deadline_after(long long cycles);
bool expired(const Deadline& deadline);

}  // namespace aos
