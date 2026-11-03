// aos/post.hpp：aos-post 的公開介面——投遞（NORMS N-16）：寄信、認領、讀信、處理完、撤回。
// aos-post＝IPC 的語法糖、基底工具（thinking 11-03 aos-post）：跟 aos proc 的關聯不深，proc 自己拿它組出想要的效果。
// aos-post 命令列用這組；aos-daemon 的信箱模式、aos-llm-kernel 的回信、aos-llm-send 的回信信箱直接連這個庫。
//
//   信箱＝一個資料夾，底下的格（各函式只驗自己用到的格，少了丟 MailboxMissing，不替人建——init、take、done keep 例外）：
//     tmp/<信件名稱>/      寄信人正在寫、或正在撤回／丟掉的信；處理者永遠不看這格
//     new/<信件名稱>/      寄好了、排隊中（寄信人寫好才 rename 進來，所以看到就是完整的）
//     cur/<信件名稱>/      被處理者認領、處理中（rename new→cur，只有一個人會成功）；take 發現沒有就建
//     archive/<信件名稱>/  選用：done 時 keep＝留在這裡（沒有就建）；aos-post 永遠不讀它
//   new/、cur/ 裡 . 開頭的名字不算信（N-05）。
//   信＝一個資料夾，名字＝信件名稱，裡面必有 letter.json：{"sender": 寄信人身分, "sent_at": ISO 8601 UTC 到毫秒,
//     "reply_to"?: 信箱路徑, "in_reply_to"?: 原信的信件名稱, "body": 內容（形狀由收信的程式定）}。沒有 kind（11-03 拿掉；讀到也忽略）
//
//   信件名稱兩種形狀（thinking 11-03 aos-post § 2）：
//     有序＝<12 位序號>.<尾名>（名字匹配 ^[0-9]{12}\.），無序＝<尾名>（其他）
//     尾名＝寄信人自己給的（SendOpts::name），不給＝aos-util 的 aos::unique_id：<UTC 奈秒 20 位>.<pid>.<started_at_ticks>（時間開頭）
//   處理順序（sort_letters；take、take_all、first_in_cur、aos-daemon 排 cur/ 殘骸都用它）：
//     有序全部在前、照名字排（12 位同寬＝照序號）；無序全部在後、照名字排（預設名＝寄出先後；自己給的照字面）。
//     缺號不等、不讀 order.json、不逐號探：列出、排好、從頭 rename，第一個成功的就是
//   有順序的投遞（SendOpts::ordered；N-16、medium-plan § 三）：信箱多 order.lock/（aos-lock 的鎖）與 order.json
//     （{"counter_letters": N}，沒有＝0）；new/ 裡的名字＝<N+1 零填 12 位>.<尾名>。寄信人死在中間只會留下缺號、不會重號
//     （先寫 order.json 再 rename，見 send.cpp）。同一個信箱有序、無序都收
//
//   init          建信箱（mkdir -p 信箱、tmp/ new/ cur/）；已經有＝沒事。建不了丟 MkdirFailed。archive/ 不建
//   open          拿一個信箱：信箱不是資料夾丟 MailboxMissing（格由各函式自己驗）
//   send          寄一封：驗信箱（tmp/、new/ 是資料夾＝不然 MailboxMissing；對自己可寫 access W_OK|X_OK＝不然 MailboxBad）、
//                 reply_to（轉絕對、同一套驗法）、in_reply_to（check_name）、name（check_name＋不得像有序名，不合 ArgumentsBad）→
//                 mkdir tmp/<名>（預設名撞名換一個；自己給的撞名 LetterExists）→ 複製 opts.files → 寫 letter.json → rename 進 new/
//                 （自己給的撞名 LetterExists）。sender＝aos-util 的 aos::identity()。回 new/ 裡的名字
//   take          認領一封：new/ 照處理順序，第一個 rename 進 cur/ 成功的；沒有＝nullopt。cur/ 沒有就建（MkdirFailed）
//   take_all      認領 new/ 裡全部，回認領到的（照處理順序）；沒有＝空。cur/ 沒有就建
//   first_in_cur  cur/ 裡照處理順序第一封；cur/ 空＝nullopt（see、done 不給信件名稱時用）
//   see           讀 cur/<名>/letter.json、驗信封：好信 ok＝true、letter＝整份；壞信 ok＝false、reason＝原因。不在 cur/ 丟 LetterMissing。
//                 壞信＝讀不了或不是 JSON 物件、sender／sent_at 不是字串、沒有 body、reply_to／in_reply_to 有但不是字串
//   reply         照 cur/<名> 那封的 reply_to 投一封回信（in_reply_to＝原信件名稱、body＝給的）；
//                 那封沒寫 reply_to 或是壞信＝不回、回 nullopt；寄得出去回回信的名字（寄不出去照 send 丟）
//   done          處理完：keep＝rename cur→archive（archive/ 沒有就建），否則 rename cur→tmp 再刪；壞信一律丟掉（不管 keep）。
//                 不在 cur/ 丟 LetterMissing
//   regret        撤回：rename new→tmp 再刪；回 true。不在 new/（已被認領、或本來就沒有）回 false
//   check_name    信件名稱是不是一個單純的名字：不空、不含 /、不以 . 開頭；不是丟 ArgumentsBad
//   is_ordered    名字是不是有序名（^[0-9]{12}\.）
//   sort_letters  照處理順序排
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
inline constexpr const char* RegretFailed = "RegretFailed";     // 命令列 regret：信不在 new/（已被認領，或本來就沒有）
inline constexpr const char* OrderBad = "OrderBad";             // ordered：order.json 在但讀不懂（不是 {"counter_letters": 非負整數}）
inline constexpr const char* LetterExists = "LetterExists";     // send 自己給的信件名稱已經有同名的（tmp/ 或 new/）
inline constexpr const char* MailboxBad = "MailboxBad";         // send：信箱的 tmp/ 或 new/ 對自己不可寫
}  // namespace code

// 信箱各格的路徑。
struct Mailbox {
    std::string root;   // 絕對路徑
    std::string tmp() const;
    std::string fresh() const;   // new/（new 是 C++ 關鍵字）
    std::string cur() const;
    std::string archive() const;
};

struct SendOpts {
    std::optional<std::string> name;          // 自己給的信件名稱（ordered 時是尾名）；不給＝aos::unique_id
    std::optional<std::string> reply_to;      // 信箱路徑（存成絕對路徑；照 send 的信箱驗法驗）
    std::optional<std::string> in_reply_to;   // 原信的信件名稱（check_name；不驗那封在不在）
    bool ordered = false;                     // 有順序的投遞（order.lock/＋order.json）；拿不到鎖就一直等
    // 信裡另放的檔（N-16「其他檔隨意」）：{信裡的名字, 來源檔路徑}，在寫 letter.json 之前複製進去；複製不了丟 WriteFailed。
    // 名字要是單純的檔名、不能叫 letter.json（ArgumentsBad）。aos-llm-kernel 的回信用它附 stdout.txt、stderr.txt（10-30）
    std::vector<std::pair<std::string, std::string>> files;
};

struct Seen {
    bool ok = false;
    Json letter;          // 好信：整份 letter.json
    std::string reason;   // 壞信：原因
};

void init(const std::string& root);
Mailbox open(const std::string& root);
std::string send(const Mailbox& mb, const Json& body, const SendOpts& opts);
std::optional<std::string> take(const Mailbox& mb);
std::vector<std::string> take_all(const Mailbox& mb);
std::optional<std::string> first_in_cur(const Mailbox& mb);
Seen see(const Mailbox& mb, const std::string& name);
std::optional<std::string> reply(const Mailbox& mb, const std::string& name, const Json& body);
void done(const Mailbox& mb, const std::string& name, bool keep);
bool regret(const Mailbox& mb, const std::string& name);

void check_name(const std::string& name);
bool is_ordered(const std::string& name);
void sort_letters(std::vector<std::string>& names);

}  // namespace aos::post
