// state.hpp：【state】$AOS_STACK 裡 fsm 自己的檔：stage.txt（現在狀態）。內部標頭。
// 11-04 起檔名是 stage.txt（原 state.txt；使用者題 10「fsm改名，嘗試用同義詞」：`state` 撞 loop 的 state.json 窗）；函數名、fsm.json 的 start／states 不改。
// 11-03 起不寫 trace.jsonl（使用者「整個拿掉」，thinking 2026-11-03-trace）。
//
//   state.cpp   read_state、write_state（先寫 .stage.txt 再改名成 stage.txt，N-05）
//
// state 是純文字一行狀態名，跟 shell 版 fsm 同格式（P-07、N-39）；只有 fsm 自己寫。
#pragma once

#include "common/common.hpp"

#include <string>

namespace aos::fsm {

// stack/stage.txt 的內容去掉前後空白（認 Unicode 空白，同 Python 的 str.strip()）；檔不在、空的＝start。
// 10-22：在但讀不了（沒權限、是資料夾、不是 UTF-8…）StateBad（原本當沒有檔、從 start 起）。
std::string read_state(const std::string& stack, const std::string& start);

// stack/.stage.txt 寫 "名\n"，再改名成 stack/stage.txt。寫不了 WriteFailed。
void write_state(const std::string& stack, const std::string& name);

}  // namespace aos::fsm
