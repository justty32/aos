// state.hpp：【state】$AOS_STACK 裡 fsm 自己的兩個檔：state（現在狀態）與 trace.jsonl（每次一行）。內部標頭。
//
//   state.cpp   read_state、write_state（先寫 .state.txt 再改名成 state.txt，N-05）、append_trace（時間用 aos-util 的 utc_now_ms）
//
// state 是純文字一行狀態名，跟 shell 版 fsm 同格式（P-07、N-39）；只有 fsm 自己寫。
#pragma once

#include "common/common.hpp"

#include <string>

namespace aos::fsm {

// stack/state.txt 的內容去掉前後空白（認 Unicode 空白，同 bin 的 str.strip()）；檔不在、空的＝start。
// 10-22：在但讀不了（沒權限、是資料夾、不是 UTF-8…）StateBad（原本當沒有檔、從 start 起）。
std::string read_state(const std::string& stack, const std::string& start);

// stack/.state.txt 寫 "名\n"，再改名成 stack/state.txt。寫不了 WriteFailed。
void write_state(const std::string& stack, const std::string& name);

// stack/trace.jsonl 追加一行（dumps，排版同 Python json.dumps）。寫不了 WriteFailed。
void append_trace(const std::string& stack, const Json& line);

}  // namespace aos::fsm
