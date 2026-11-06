// aos/llm_kernel.hpp：aos-llm-kernel 的公開介面——LLM kernel 的信箱與信（aos-llm 寄信收信、aos-llm-kernel 收信回信都用這組）。
//
//   信箱（N-16 資料夾式，Maildir）：一個資料夾，底下三格、一封信＝一個資料夾（名字＝信件名稱，下面寫 id）：
//     tmp/<id>/、tmp/.<id>/   寄信的正在寫（aos-post 寫 tmp/<id>；aos-llm ask 寫 tmp/.<id>）；撤信、丟信先改名回這裡再刪
//     new/<id>/    排隊中（kernel 認領＝改名進 cur/；寄信的撤信＝改名回 tmp/，兩邊只有一個改得成）
//     cur/<id>/    kernel 認領了、請 daemon 掛成問腦 proc（stack＝這個資料夾：request.json、proc.json、daemon 寫的 loop.json／state.json／stderr.txt、函數寫的 reply.json）；寄出回信就整封刪掉
//                  （11-04 夜使用者「舊信根本不用留，就是刪」：沒有 done/）
//     .flock       kernel 跑一次的期間 flock 住（同一個信箱同時只有一個 kernel）
//   信：letter.json＝N-16 的信（aos-post 寫）：{"sender", "sent_at", "reply_to": 回信信箱（必有，沒有就沒人收得到回信）,
//                    "body": {"endpoint"?: 代號（kernel.json 的 endpoints 表；沒寫＝kernel 的預設）,
//                             "request": OpenAI chat completions 的 body 去掉端點（messages 必有；stream 真＝RequestBad）,
//                             "priority"?: 原樣（parse_priority）}}
//       （thinking 11-04 think-as-function 02 § 1；頂層 inst／env 的舊閘門信不再認＝LetterBad）；其他不認得的 key 一律忽略（C-48）
//   回信：reply.json＝endpoint 函數 stdout 那份 {"message": {...}, "usage"?: {...}, "model"?: ...}，或 {"error": {"code": 代號, "msg": 原因}}
//       （kernel 沒跑、掛不上 daemon〔LaunchFailed〕、endpoint 函數退非 0 或逾時〔EndpointFailed〕、stdout 讀不懂〔ReplyBad〕）。
//       kernel 把同一份當 body、照 N-16 寄一封回信進信的 reply_to（沒寫 reply_to＝回信沒人收，信照刪）（in_reply_to＝原信的信件名稱），寄出的信件名稱記在 <信>/reply_letter.txt
//   用量：reply.json 的 usage.total_tokens（沒有就 prompt_tokens＋completion_tokens）→ used.json（11-04 起取代 AOS_KERNEL_REPORT）
//   寄信的人：sender.flock＝aos-llm ask（同步）建好信就 flock（LOCK_EX）住、拿到行程結束；aos-llm send（非同步）不建＝kernel 不判存活、照跑
//
//   信件名稱＝aos-util 的 aos::unique_id()：<UTC 奈秒 20 位>.<pid>.<started_at_ticks>——照字典序排＝照寄的先後
//   hold_sender    寄信的：開 <信>/sender.flock（0666，權限照信箱的 umask／ACL）、flock 住；回 fd，一直開著到行程結束。失敗丟 WriteFailed
//   has_sender     <信>/sender.flock 在不在（不在＝非同步的信，kernel 不判存活）
//   sender_alive   寄這封信的還在不在：<信>/sender.flock 有人鎖著＝在；檔不在、開不了、鎖得到＝不在
//                  （flock 跟著檔走，不看 pid，所以沙箱〔別的 pid、mount namespace〕裡的寄信人也認得）
//   parse_priority 信裡的 priority（10-15 LLM kernel 稿）：沒寫＝normal；"low"／"normal"／"high"；數字看正負；
//                  物件 {"level", "deadline", 其他 key 忽略}；deadline＝ISO 8601（要帶時區）或 epoch 秒。壞了丟 PriorityBad
//   priority_of    一封信的排隊依據＝parse_priority(letter["body"]["priority"])（11-04 起 `_metainfo` 的兩個依據拿掉：信裡沒單子）
//   reply_of       回信的內容合不合（{"message": 物件, …} 或 {"error": {"code": 字串, "msg": 字串}}）：合＝原樣、不合＝nullopt
//   read_reply     讀 reply.json、照 reply_of 驗；壞了回 nullopt
//
// 錯一律丟 aos::Error{code, msg}（aos-util 的 aos/error.hpp）。
#pragma once

#include "aos/io.hpp"
#include "aos/post.hpp"

#include <optional>
#include <string>
#include <vector>

namespace aos::llm_kernel {

// 錯誤代號：沿用 aos-post 的信箱與通用代號，再加 LLM 信件協定自己的。
namespace code {
using namespace aos::post::code;   // MailboxMissing、LetterMissing、LetterBad
inline constexpr const char* PriorityBad = "PriorityBad";       // priority 寫壞（aos-llm 自己擋；kernel 收到這種信回 LetterBad）
inline constexpr const char* DeadlineMissed = "DeadlineMissed"; // 回信：輪到之前時限已過，沒跑（10-15 LLM kernel 稿定的名字）
inline constexpr const char* DaemonMissing = "DaemonMissing";   // kernel：沒設 AOS_DAEMON、不是資料夾（11-05：問腦請 daemon 掛，kernel 要在 daemon 底下）
inline constexpr const char* ReplyBad = "ReplyBad";             // 回信：endpoint 函數的 stdout 讀不懂；aos-llm：回信讀不懂
inline constexpr const char* LockFailed = "LockFailed";         // kernel：信箱被另一個 kernel 鎖著
inline constexpr const char* QueueBad = "QueueBad";             // kernel：$AOS_STACK/queue.json 在但讀不懂
inline constexpr const char* UsedBad = "UsedBad";               // kernel：$AOS_STACK/used.json（用量帳）在但讀不懂
inline constexpr const char* BudgetMissing = "BudgetMissing";   // 回信：這一窗的額度（kernel.json 的 budget）用完了，沒跑（10-15 稿叫 BudgetExhausted，照 C-54 四種結尾改）
// 11-04 think-as-function（02 § 1～§ 3）：
inline constexpr const char* EndpointMissing = "EndpointMissing"; // 回信：信沒寫 endpoint、kernel.json 也沒寫預設的 endpoint
inline constexpr const char* EndpointUnknown = "EndpointUnknown"; // 回信：信寫的代號不在 kernel.json 的 endpoints 表裡
inline constexpr const char* EndpointFailed = "EndpointFailed";   // 回信：endpoint 函數退非 0（msg 帶它 stderr 的第一行）、或起不來
inline constexpr const char* RequestBad = "RequestBad";           // 回信／aos-llm：request 不是物件、messages 不是陣列、stream 真（串流不做）
}  // namespace code

// 信箱三格的路徑。
struct Mailbox {
    std::string root;
    std::string tmp() const;
    std::string fresh() const;   // new/（new 是 C++ 關鍵字）
    std::string cur() const;
};

inline constexpr const char* SENDER_FLOCK = "sender.flock";   // 10-29 原叫 sender.lock（.lock 留給 N-15 的資料夾鎖）

int hold_sender(const std::string& letter_dir);
bool sender_alive(const std::string& letter_dir);
bool has_sender(const std::string& letter_dir);

struct Priority {
    int level = 0;                    // -1 low、0 normal、1 high
    std::optional<double> deadline;   // epoch 秒；沒寫＝nullopt
};
Priority parse_priority(const Json& v);

// 一封信的排隊依據——kernel 只從這裡讀：parse_priority(letter["body"]["priority"])（壞了丟 PriorityBad）。
Priority priority_of(const Json& letter);

std::optional<Json> reply_of(const Json& r);
std::optional<Json> read_reply(const std::string& path);

}  // namespace aos::llm_kernel
