// table.hpp：【table】fsm.json——`{"start": 狀態名, "states": {名: {"val": aos-exec 的目標或 [目標, 參數...], "next": 下一個狀態名}}}`。內部標頭。
//
//   table.cpp   read_table：讀設定檔（`檔` 或 `檔#/指標`）、驗 start／states；check：開跑時查整張表（10-22）；
//               pick：狀態名 → 那格（照 Python 版 proto8/bin/aos-fsm）
//
// 表一定明寫、next 只在表上（N-36）。val 只收目標（10-21 plan F2；傍晚 ideas § 9 加陣列）：要內嵌單子寫
// `fsm.json#/states/<名>/body`、單子放在同一格的 body，由 aos-exec 跑。表裡其他 key（body、_entry…）忽略（C-48）。
#pragma once

#include "common/common.hpp"

#include <map>
#include <string>

namespace aos::fsm {

struct Table {
    std::string start;
    Json states;   // 物件
};

struct Cell {
    aos::loop::Target val;
    std::string next;
};

// 檔不在、`#/` 指不到 CfgMissing；讀不了、不是 JSON、# 寫錯、不是 {"start": 字串, "states": 物件} CfgBad。
// 指示詞（10-23 晚）：整份、states、每一格先換一層，start、val、next 整個解（相對 $ref 從 fsm.json 的資料夾算）；解不開 DirectiveBad。
Table read_table(const std::string& spec);

// 開跑時（讀表後、跑格前）查整張表（使用者 10-22「b、c 開跑時查整張表」）：start 要在表上；每一格要是 {"val", "next"}、
// val 合法（字串或 [目標, 參數...]；物件＝錯）、next 是表上的狀態名、不是空字串、頭尾沒空白、沒換行（state 檔是純文字一行、
// 讀回來會去頭尾空白）。哪一格不合都＝表壞 CfgBad、不跑格。回每一格解好的樣子。
std::map<std::string, Cell> check(const Table& t);

// 狀態名 → 那格；state 檔裡的狀態不在表上 StateUnknown（where＝state 檔的路徑，寫進原因）。
Cell pick(const std::map<std::string, Cell>& cells, const std::string& state, const std::string& where);

}  // namespace aos::fsm
