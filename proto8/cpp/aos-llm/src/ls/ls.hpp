// ls.hpp：【ls】aos-llm ls——讀 kernel 的窗 <stack>/endpoints.json（包的屬性表，11-05 feat-proto），一行一包印出。
//
//   ls_window  讀 <kernel 的 stack>/endpoints.json；不在、讀不懂、不是物件＝EndpointsMissing（kernel 沒跑過，或太舊還沒寫窗）
//   ls_print   json＝false：一行一包 `代號 speed cost context slots backend summary`（TAB 分欄，欄位缺＝`-`；summary 在最後、可含空白；
//              `{"error": ...}` 的包印 `代號<TAB>error:<TAB><原因>`），最後一行整台的
//              `# kernel: slots N, reserved for high R, in flight F, queued Q`；json＝true：整份窗一行 JSON（不含整台那行）
//   ls_whole   整台的：slots、reserved_high 讀窗 <stack>/slots.json（kernel 每拍寫；不在或讀不懂＝缺、印 -），
//              in_flight＝requests/cur/、queued＝requests/new/ 裡的信數（當下數資料夾，. 開頭的不算）
#pragma once

#include "common/common.hpp"

namespace aos::llm {

// ls 專用定位：--kernel（列名或含 / 的 stack 路徑）＞AOS_LLM_KERNEL＞AOS_DAEMON 表的唯一 llm kernel。
Mailbox ls_kernel(const std::optional<std::string>& selection);
Json ls_window(const Mailbox& mb);
Json ls_whole(const Mailbox& mb);
void ls_print(const Json& window, bool json, const Json& whole);

}  // namespace aos::llm
