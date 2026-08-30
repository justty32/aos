#pragma once

#include <filesystem>
#include <string>
#include <string_view>

namespace aos::agent::cli {

/* `aos state`／`aos agent state` 共用的輸出：status.json 的欄位再加上
 * unread（say/ 裡還沒被 step 吃掉的訊息數）與 engine／model。
 * 未讀 > 0 而且 agent 不是停在 error 時，status 會是 pending。 */
std::string state_text(const std::filesystem::path &folder,
                       std::string_view name);
/* 有未讀就在 log 之後印一段「## 未讀 (N)」；沒有就什麼都不印。 */
void print_unread(const std::filesystem::path &folder, std::string_view name);

int run_listen(const std::filesystem::path &folder, std::string_view name,
               bool once);
int run_talk(const std::filesystem::path &folder, std::string_view name);

}  // namespace aos::agent::cli
