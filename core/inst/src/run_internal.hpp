#pragma once

#include <cstdint>
#include <string>

namespace aos::detail {

int run_exec_once(const char *folder, bool &did_work);
int run_exec_loop(const char *folder, std::uint64_t interval);
int run_init_world(const char *folder);
int run_deliver_world(const char *folder, const std::string &document);

// `.aos/turn` 遞增（§B-3）。只在 release_instruction 成功之後呼叫一次；
// 實作在 run_turn.cpp。失敗時 error 是 errno（含 EINVAL＝內容壞、ERANGE＝溢位）。
bool advance_turn(int &error);

}  // namespace aos::detail
