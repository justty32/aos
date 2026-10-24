// aos/kernel_llm.hpp：aos-kernel-llm 的公開介面——LLM kernel 的信箱與信（aos-gate 寄信、aos-kernel-llm 收信都用這組）。
//
//   信箱（N-16 資料夾式，Maildir）：一個資料夾，底下四格、一封信＝一個資料夾（名字＝信號 id）：
//     tmp/<id>/    閘門正在寫（寫好 letter.json 才改名進 new/）；撤信、丟信也先改名回這裡再刪
//     new/<id>/    排隊中（kernel 認領＝改名進 cur/；閘門撤信＝改名回 tmp/，兩邊只有一個改得成）
//     cur/<id>/    kernel 正在跑（stdout.txt、stderr.txt、跑完寫 reply.json）
//     done/<id>/   有回信了（reply.json 寫好才改名進來），閘門讀完刪掉
//     .lock        kernel 跑一次的期間 flock 住（同一個信箱同時只有一個 kernel）
//   信：letter.json＝{"inst": 單子（指示詞已解、cwd 是絕對路徑）, "env": 寄信那一刻閘門的整份環境, "priority": 原樣}
//   回信：reply.json＝{"code": 結束碼, "signal": 訊號或 null}，或 {"error": {"code": 代號, "msg": 原因}}（kernel 沒跑或跑不起來）
//
//   letter_id      新信號：<UTC 奈秒 20 位>.<閘門 pid>.<閘門 started_at_ticks>——照字典序排＝照寄的先後；從名字就看得出寄信的人還在不在
//   sender_alive   寄這封信的閘門還在不在（pid＋started_at_ticks 對得上，N-15、N-17；名字讀不懂＝不在）
//   parse_priority 信裡的 priority（10-15 LLM kernel 稿）：沒寫＝normal；"low"／"normal"／"high"；數字看正負；
//                  物件 {"level", "deadline", 其他 key 忽略}；deadline＝ISO 8601（要帶時區）或 epoch 秒。壞了丟 PriorityBad
//   priority_of    一封信的排隊依據：priority＋單子 `_metainfo` 的 time_ms、llm_tokens（10-24）
//   level_name     -1／0／1 → "low"／"normal"／"high"
//   read_reply     讀回信；壞了回 nullopt
//
// 錯一律丟 aos::Error{code, msg}（aos-util 的 aos/error.hpp）。
#pragma once

#include "aos/loop.hpp"

#include <optional>
#include <string>
#include <vector>

namespace aos::kernel_llm {

// 錯誤代號：沿用 aos-loop 的（→ aos-exec → aos-util），再加信箱、信會吐的。
namespace code {
using namespace aos::loop::code;   // ArgumentsBad、FlagUnknown、CfgMissing、CfgBad、StackMissing、WriteFailed、MkdirFailed…
inline constexpr const char* MailboxMissing = "MailboxMissing"; // 閘門：沒設 AOS_KERNEL、或它指的不是資料夾
inline constexpr const char* PriorityBad = "PriorityBad";       // priority 寫壞（閘門自己擋；kernel 收到這種信回 LetterBad）
inline constexpr const char* LetterBad = "LetterBad";           // 回信：letter.json 讀不了、不是物件、inst 不是物件、priority 壞
inline constexpr const char* LetterMissing = "LetterMissing";   // 閘門：自己的信在信箱裡不見了（被人刪掉）
inline constexpr const char* DeadlineMissed = "DeadlineMissed"; // 回信：輪到之前時限已過，沒跑（10-15 LLM kernel 稿定的名字）
inline constexpr const char* RunFailed = "RunFailed";           // 回信：跑到一半 kernel 死了、沒寫回信（下次 kernel 起來時發現）
inline constexpr const char* ReplyBad = "ReplyBad";             // 閘門：回信讀不懂
inline constexpr const char* LockFailed = "LockFailed";         // kernel：信箱被另一個 kernel 鎖著
inline constexpr const char* QueueBad = "QueueBad";             // kernel：$AOS_STACK/queue.json 在但讀不懂
}  // namespace code

// 信箱四格的路徑。
struct Mailbox {
    std::string root;
    std::string tmp() const;
    std::string fresh() const;   // new/（new 是 C++ 關鍵字）
    std::string cur() const;
    std::string done() const;
};

std::string letter_id();
bool sender_alive(const std::string& id);

struct Priority {
    int level = 0;                    // -1 low、0 normal、1 high
    std::optional<double> deadline;   // epoch 秒；沒寫＝nullopt
    // 以下來自單子的 `_metainfo`（被叫者自報的特性，10-24 metainfo 紀錄 § 5；只有 priority_of 會填）
    std::optional<double> time_ms;    // 宣告要跑多久（數字，或 {"val", "max"} 取 val）；沒寫或寫壞＝nullopt
    std::optional<double> llm_tokens; // 宣告吃多少 token（同上；這版只讀不用，留給之後的額度）
    std::vector<std::string> metainfo_bad;   // 寫壞而當沒寫的 key（"_metainfo" 本身不是物件也算），記進 served.jsonl
};
Priority parse_priority(const Json& v);
std::string level_name(int level);

// 一封信的排隊依據——kernel 只從這裡讀：parse_priority(letter["priority"])（壞了丟 PriorityBad）＋單子的 `_metainfo`
// （letter["inst"]["_metainfo"]，只認 time_ms、llm_tokens；形狀不對＝那個 key 當沒寫、記在 metainfo_bad，不擋跑——10-24 metainfo M8）。
Priority priority_of(const Json& letter);

std::optional<Json> read_reply(const std::string& path);

}  // namespace aos::kernel_llm
