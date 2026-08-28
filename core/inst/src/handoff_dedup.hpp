#pragma once

// handoff 層內部標頭：不對外，只給 handoff*.cpp 看。
// 這裡是 SPEC §D-6「批 id 與去重」那一整件事——讀現任 header、找 roll-forward 的
// 錨、清完投遞之後把 header 標成 swept。跟 §D-4／§D-5 的「掃收件匣 → 發布」是
// 兩件不同的事，所以分開住（見 handoff_aggregate.cpp）。
//
// 與 handoff_header.* 的分工：那個檔是**純字串運算**（編碼／解碼／摘要），刻意
// 不碰檔案系統；這個檔碰檔案系統與 HandoffResult，是 header 的**讀寫與決策**面。
// 不要把這裡的東西塞回 handoff_header.*，那會破掉它「不碰 fs」的性質。

#include <aos/inst.hpp>

#include "handoff_header.hpp"

#include <string>

namespace aos::detail {

// 現任 header 的兩個欄位。沒有 header、讀不到或讀不懂都回 false（後兩者記
// HeaderInvalid issue），呼叫端一律當作「沒有可比對的 id」，照常發布。
bool current_header(const std::string &path, HeaderFields &fields,
                    HandoffResult &result);

// roll-forward 的錨：掃 base 所在目錄，找出**位元組跟本輪 output 完全相同**的
// 兄弟唯一暫存。兄弟＝檔名以 `<stem>-` 開頭、以 `.json.temp` 結尾（base 是
// `.aos/inst.json` 時 stem ＝ `inst`，所以找 `.aos/inst-*.json.temp`）；
// `<stem>-head-` 開頭的跳過——那是 header 的唯一 temp，位元組比對本來也會擋掉，
// 明著跳過比較便宜也比較好讀。名字排序後逐一讀，第一個對上的就是錨。
//
// **身分由內容決定，名字只是找得到它的索引**（跟 #21 的逐位元比對同一個原則）。
// 能通過比對的檔，內容就一定是「本輪這組投遞的 canonical 批」——不管它是我們自己
// 上一次崩掉留下的，還是併發同儕正在飛的：兩者是同一串位元組，誰把它 rename 到
// base 都是同一個結果，輸的那一邊拿 EEXIST 乾淨放棄。
//
// 這是刻意不用「固定 `.temp` 槽位」的原因：共用可變狀態會讓兩個彙整者互相覆蓋
// 對方寫進槽位的批，於是 A 可能發布 B 的批、卻只清掉 A 自己看到的那幾份投遞，
// 剩下的在下一輪被重新彙整＝重複執行。詳見 docs/handoff.md。
bool find_rollforward_anchor(const std::string &directory,
                             const std::string &stem, const std::string &output,
                             std::string &anchor);

// 把 header 改寫成 swept:true（§C-8）：上一批的清理已經走完，去重 MUST NOT 再擋
// 任何投遞——同名同內容的**全新**投遞照常發布。
// 寫不成只記 HeaderWriteFailed issue（不致命）：代價是下一輪少一次去重保證，
// 跟 header 本身寫不成同一個等級。
void mark_header_swept(const HeaderPaths &header, const std::string &id,
                       const std::string &directory, HandoffResult &result);

}  // namespace aos::detail
