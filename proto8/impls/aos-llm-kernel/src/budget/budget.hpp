// budget.hpp：【budget】token 回報與額度（10-24，thinking 2026-10-24-llm-kernel「token 回報與額度」）。
//
//   Budget        kernel.json 的 budget：max_calls、max_tokens（每窗上限，非負整數；沒寫＝不限）、window（"hour"／"day"／"all"；沒寫＝day，
//                 10-15 定「一天一期歸零」）、spent（到頂時新信怎麼辦："refuse"＝回 BudgetMissing（預設，10-15「見底就擋」）、"wait"＝留在 new/ 等下一窗）、
//                 senders（11-05 feat-proto 件 5：每個寄件人的額度＝{信封 sender: {"max_calls", "max_tokens"}}；窗與 spent 同 kernel 的；
//                 設定的相對路徑從 base〔kernel.json 所在〕算；讀進來與記帳的 key 一律相對 kernel stack，搬家照用；沒列的寄件人不限）
//   sender_key    寄件人與 kernel stack 先各自 abspath／lexically_normal，再 lexically_relative；stack 外面以 ../ 開頭
//   parse_budget  讀 budget 那格（沒寫＝不限、window day）；壞了 CfgBad。11-10 晚 two-machines B09：senders 的 key 解出來的資料夾不在＝
//                 記一條提醒進 warnings（warn_budget 印；寫錯或兩台相對位置不同時額度會安靜不生效），照樣收這格
//   Used          $AOS_STACK/used.json＝{"window", "since", "counter_calls", "counter_tokens", "counter_all_calls", "counter_all_tokens"}：這一窗用了多少、開 kernel 以來一共多少
//                 （10-25 計數改 counter_*，原 calls、tokens、all_calls、all_tokens）；
//                 11-05 feat-proto 多一格 packs＝{代號: {"counter_calls", "counter_tokens"}}：這一窗每個包（endpoints 的一組）用了多少（換窗一起歸零）；
//                 同一天多一格 senders＝{相對 kernel stack 的寄件人路徑: {"counter_calls", "counter_tokens"}}：這一窗每個寄件人用了多少（同上，換窗歸零）
//   window_since  這一刻所在那一窗的起點（kernel 的本地時間，帶時區的 ISO 8601；hour＝整點、day＝午夜；all＝null）
//   read_used     讀 used.json（沒有＝全 0；在但讀不懂＝UsedBad）；換窗了（window 或 since 不同）就把 counter_calls、counter_tokens 歸零，counter_all_* 照留
//   add_used      跑過的一封記上去（先換窗）：counter_calls＋1、counter_tokens＋回報的（沒回報＝只算次數），代號有給＝packs 那格也記、
//                 寄件人有給＝senders 那格也記；寫回 used.json（先寫暫存再改名）
//   spent         照這一窗的帳，再開第 started＋1 封會不會超過：counter_calls 已到 max_calls、或 counter_tokens 已經到 max_tokens（token 只能事後知道，所以一次裡可能超過一點）
//   spent_pack    同 spent、看一個包（11-05 feat-proto）：packs.<代號> 的 counter_calls＋started（這包在飛＋這次新掛）≥ 包的 max_calls、
//                 或 counter_tokens ≥ max_tokens（窗＝kernel 的 budget.window）
//   spent_of      spent_pack 的通用版：在 used.json 的一格（packs 或 senders）裡看 name 那人／那包（11-05 feat-proto 件 5；spent_pack＝spent_of(u.packs, …)）
//   report_of     回信（reply.json，endpoint 函數的 stdout）的 usage 物件：
//                 tokens＝total_tokens；沒有就 prompt_tokens＋completion_tokens（非負整數才算）。沒有 usage（含 error 回信）＝沒回報（tokens null）；
//                 有但不是物件、形狀不對＝bad（tokens null，只算次數）
#pragma once

#include "common/common.hpp"

#include <ctime>
#include <map>
#include <optional>
#include <string>
#include <vector>

namespace aos::llm_kernel {

struct Limit {
    std::optional<long long> max_calls;
    std::optional<long long> max_tokens;
    std::string key;   // 11-10 晚 two-machines B10：kernel.json 裡寫的那個 key（原樣；BudgetMissing 的訊息印它）
};

struct Budget {
    std::optional<long long> max_calls;
    std::optional<long long> max_tokens;
    std::string window = "day";
    bool wait = false;                       // spent: "wait"
    std::map<std::string, Limit> senders;    // 寄件人（相對 kernel stack）→ 這人每窗上限
    std::vector<std::string> warnings;       // 11-10 晚 B09：讀設定時的提醒（英文一句一條；warn_budget 印）
};

// 11-10 晚 two-machines B09：印 b.warnings（每條一行 aos-llm-kernel: warning:）。kernel 每拍是新行程，所以只在內容變了才印：
// 印過的全文記在 $AOS_STACK/budget_warned.txt，一樣就不印；沒有提醒＝刪掉那個檔。寫不成只是下一拍再印。
void warn_budget(const Budget& b, const std::string& stack);

struct Used {
    std::string window = "day";
    Json since = nullptr;
    long long calls = 0;
    long long tokens = 0;
    long long all_calls = 0;
    long long all_tokens = 0;
    Json packs = Json::object();     // 代號 → {"counter_calls", "counter_tokens"}（這一窗）
    Json senders = Json::object();   // 寄件人 → {"counter_calls", "counter_tokens"}（這一窗）
};

struct Report {
    Json tokens = nullptr;   // 整數或 null
    bool bad = false;
};

std::string sender_key(const std::string& sender, const std::string& stack);
Budget parse_budget(const Json& v, const std::string& base, const std::string& stack);
Json window_since(const std::string& window, std::time_t now);
Used read_used(const std::string& stack, const std::string& window);
void add_used(const std::string& stack, Used& u, const Report& r, const std::string& endpoint = "", const std::string& sender = "");
bool spent(const Budget& b, const Used& u, long long started);
bool spent_pack(const Used& u, const std::string& name, std::optional<long long> max_calls, std::optional<long long> max_tokens,
                long long started);
bool spent_of(const Json& group, const std::string& name, std::optional<long long> max_calls, std::optional<long long> max_tokens,
              long long started);
Report report_of(const Json& reply);

}  // namespace aos::llm_kernel
