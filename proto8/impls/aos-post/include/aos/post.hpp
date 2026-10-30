// aos/post.hpp：aos-post 的公開介面——投遞（NORMS N-16 的 10-29 改口＋補）：寄信、認領、讀信、處理完、撤回。
// aos-post 命令列用這組；aos-daemon 的信箱模式（medium-plan 實作第 5 步）直接連這個庫。
//
//   信箱＝一個資料夾，底下三格（第四格 done/ 選用，處理者想留紀錄才有）：
//     tmp/<信號>/   寄信人正在寫、或正在撤回／丟掉的信；處理者永遠不看這格
//     new/<信號>/   寄好了、排隊中（寄信人寫好才 rename 進來，所以看到就是完整的）
//     cur/<信號>/   被處理者認領、處理中（rename new→cur，只有一個人會成功）
//     done/<信號>/  選用：finish 時 keep＝留在這裡
//   信＝一個資料夾，名字叫信號 <UTC 奈秒 20 位>.<pid>.<started_at_ticks>（產生法是 aos-util 的 aos::unique_id，全家一份），
//     裡面必有 letter.json：{"kind": "letter", "sender": 寄信人身分, "sent_at": ISO 8601 UTC 到毫秒,
//     "reply_to"?: 信箱路徑, "in_reply_to"?: 原信號, "body": 內容（形狀由收信的程式定）}
//   有順序的投遞（SendOpts::ordered；N-16、medium-plan § 三）：信箱多 order.lock/（aos-lock 的鎖）與 order.json
//     （{"counter_letters": N}，沒有＝0）；new/ 裡的名字＝<N+1 零填 12 位>.<信號>，處理者照名字排序就是取號順序。
//     寄信人死在中間只會留下缺號、不會重號（先寫 order.json 再 rename，見 send.cpp）
//
//   init        建信箱（mkdir -p 信箱、tmp/ new/ cur/）；已經有＝沒事。建不了丟 MkdirFailed
//   open        拿一個已建好的信箱：信箱或 tmp/ new/ cur/ 不是資料夾丟 MailboxMissing
//   sender      寄信人身分＝$AOS_WS（絕對路徑），沒設才 $HOME（絕對路徑）；人也一樣
//   send        寄一封：mkdir tmp/<信號>（撞名換一個）→ 複製 opts.files → 寫 letter.json → rename 進 new/。回信號（ordered＝帶序號的那個名字）
//   claim       認領一封：new/ 照名字排序，第一個 rename 進 cur/ 成功的；沒有＝nullopt
//   claim_all   認領 new/ 裡全部（照名字排序），回認領到的（照名字排序）；沒有＝空
//   check       讀 cur/<信號>/letter.json、驗必填：好信 ok＝true、letter＝整份；壞信 ok＝false、reason＝原因。
//               不在 cur/ 丟 LetterMissing
//   reply       照 cur/<信號> 那封的 reply_to 投一封回信（in_reply_to＝原信號、body＝給的）；
//               那封沒寫 reply_to 或是壞信＝不回、回 nullopt；寄得出去回回信的信號
//   finish      處理完：keep＝rename cur→done（done/ 沒有就建），否則 rename cur→tmp 再刪；壞信一律丟掉（不管 keep）。
//               不在 cur/ 丟 LetterMissing
//   withdraw    撤回：rename new→tmp 再刪；回 true。不在 new/（已被認領、或本來就沒有）回 false
//
// 錯一律丟 aos::Error{code, msg}（aos-util 的 aos/error.hpp）。
#pragma once

#include "aos/io.hpp"

#include <optional>
#include <string>
#include <utility>
#include <vector>

namespace aos::post {

// 錯誤代號：全家共用的（ArgumentsBad、FlagUnknown、InputBad、InputExtra、WriteFailed、MkdirFailed、Internal；
// 投遞的 CommandUnknown、MailboxMissing、LetterMissing、LetterBad 10-30 收進 aos-util 的 aos/error.hpp）＋只有投遞會吐的。
namespace code {
using namespace aos::code;
inline constexpr const char* WithdrawFailed = "WithdrawFailed"; // 命令列 withdraw：信不在 new/（已被認領，或本來就沒有）
inline constexpr const char* OrderBad = "OrderBad";             // ordered：order.json 在但讀不懂（不是 {"counter_letters": 非負整數}）
}  // namespace code

// 信箱四格的路徑。
struct Mailbox {
    std::string root;   // 絕對路徑
    std::string tmp() const;
    std::string fresh() const;   // new/（new 是 C++ 關鍵字）
    std::string cur() const;
    std::string done() const;
};

struct SendOpts {
    std::optional<std::string> reply_to;      // 信箱路徑（存成絕對路徑；不驗在不在）
    std::optional<std::string> in_reply_to;   // 原信號
    bool ordered = false;                     // 有順序的投遞（order.lock/＋order.json）；拿不到鎖就一直等
    // 信裡另放的檔（N-16「其他檔隨意」）：{信裡的名字, 來源檔路徑}，在寫 letter.json 之前複製進去；複製不了丟 WriteFailed。
    // 名字要是單純的檔名、不能叫 letter.json（ArgumentsBad）。aos-llm-kernel 的回信用它附 stdout.txt、stderr.txt（10-30）
    std::vector<std::pair<std::string, std::string>> files;
};

struct Checked {
    bool ok = false;
    Json letter;          // 好信：整份 letter.json
    std::string reason;   // 壞信：原因
};

void init(const std::string& root);
Mailbox open(const std::string& root);
std::string sender();
std::string send(const Mailbox& mb, const Json& body, const SendOpts& opts);
std::optional<std::string> claim(const Mailbox& mb);
std::vector<std::string> claim_all(const Mailbox& mb);
Checked check(const Mailbox& mb, const std::string& id);
std::optional<std::string> reply(const Mailbox& mb, const std::string& id, const Json& body);
void finish(const Mailbox& mb, const std::string& id, bool keep);
bool withdraw(const Mailbox& mb, const std::string& id);

// 信號（命令列給的）是不是一個單純的名字：不空、不含 /、不以 . 開頭。不是丟 ArgumentsBad。
void check_id(const std::string& id);

}  // namespace aos::post
