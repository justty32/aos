// budget.hpp：【budget】token 回報與額度（10-24，thinking 2026-10-24-llm-kernel「token 回報與額度」）。
//
//   Budget        kernel.json 的 budget：max_calls、max_tokens（每窗上限，非負整數；沒寫＝不限；10-25 上限改 max_*，原 calls、tokens，舊名＝CfgBad）、window（"hour"／"day"／"all"；沒寫＝day，
//                 10-15 定「一天一期歸零」）、spent（到頂時新信怎麼辦："refuse"＝回 BudgetMissing（預設，10-15「見底就擋」）、"wait"＝留在 new/ 等下一窗）
//   parse_budget  讀 budget 那格（沒寫＝不限、window day）；壞了 CfgBad
//   Used          $AOS_STACK/used.json＝{"window", "since", "counter_calls", "counter_tokens", "counter_all_calls", "counter_all_tokens"}：這一窗用了多少、開 kernel 以來一共多少
//                 （10-25 計數改 counter_*，原 calls、tokens、all_calls、all_tokens）
//   window_since  這一刻所在那一窗的起點（kernel 的本地時間，帶時區的 ISO 8601；hour＝整點、day＝午夜；all＝null）
//   read_used     讀 used.json（沒有＝全 0；在但讀不懂＝UsedBad）；換窗了（window 或 since 不同）就把 counter_calls、counter_tokens 歸零，counter_all_* 照留
//   add_used      跑過的一封記上去（先換窗）：counter_calls＋1、counter_tokens＋回報的（沒回報＝只算次數）；寫回 used.json（先寫暫存再改名）
//   spent         照這一窗的帳，再開第 started＋1 封會不會超過：counter_calls 已到 max_calls、或 counter_tokens 已經到 max_tokens（token 只能事後知道，所以一次裡可能超過一點）
//   read_report   信小格裡腦寫的 report.json（AOS_KERNEL_REPORT 指的檔）＝API 回覆的 usage 物件：
//                 tokens＝total_tokens；沒有就 prompt_tokens＋completion_tokens（非負整數才算）。沒有這個檔＝沒回報（tokens null）；
//                 有但讀不懂、形狀不對＝bad（tokens null，只算次數）
#pragma once

#include "common/common.hpp"

#include <ctime>
#include <optional>
#include <string>

namespace aos::llm_kernel {

struct Budget {
    std::optional<long long> max_calls;
    std::optional<long long> max_tokens;
    std::string window = "day";
    bool wait = false;   // spent: "wait"
};

struct Used {
    std::string window = "day";
    Json since = nullptr;
    long long calls = 0;
    long long tokens = 0;
    long long all_calls = 0;
    long long all_tokens = 0;
};

struct Report {
    Json tokens = nullptr;   // 整數或 null
    bool bad = false;
};

Budget parse_budget(const Json& v);
Json window_since(const std::string& window, std::time_t now);
Used read_used(const std::string& stack, const std::string& window);
void add_used(const std::string& stack, Used& u, const Report& r);
bool spent(const Budget& b, const Used& u, long long started);
Report read_report(const std::string& path);

}  // namespace aos::llm_kernel
