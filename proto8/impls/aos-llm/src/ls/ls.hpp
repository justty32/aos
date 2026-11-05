// ls.hpp：【ls】aos-llm ls——讀 kernel 的窗 <stack>/endpoints.json（包的屬性表，11-05 feat-proto），一行一包印出。
//
//   ls_window  讀 <kernel 的 stack>/endpoints.json；不在、讀不懂、不是物件＝EndpointsMissing（kernel 沒跑過，或太舊還沒寫窗）
//   ls_print   json＝false：一行一包 `代號 speed cost context slots summary`（欄位缺＝`-`；summary 在最後、可含空白；
//              `{"error": ...}` 的包印 `代號 error: <原因>`）；json＝true：整份窗原樣（多行縮排）
#pragma once

#include "common/common.hpp"

namespace aos::llm {

Json ls_window(const Mailbox& mb);
void ls_print(const Json& window, bool json);

}  // namespace aos::llm
