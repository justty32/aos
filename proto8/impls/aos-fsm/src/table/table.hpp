// table.hpp：【table】fsm.json——`{"start": 狀態名, "states": {名: {"exec": aos-exec 的目標或 [目標, 參數...], "next": 下一個狀態名}}}`。內部標頭。
//
//   table.cpp   read_table：讀設定檔（`檔` 或 `檔#/指標`）、驗 start／states；check：開跑時查整張表（10-22）；
//               pick：狀態名 → 那格
//
// 表一定明寫、next 只在表上（N-36）。exec＝aos-exec 的目標（字串；傍晚 ideas § 9 加陣列）或內嵌單子（物件；10-21 plan F2 一度只收目標，
// 10-24 使用者「exec本來就應該要可以直接放內嵌單子吧」恢復：行程內 run_inst，AOS_CO＝/states/<名>/exec）。表裡其他 key（_entry…）忽略（C-48）。
#pragma once

#include "common/common.hpp"

#include <map>
#include <string>

namespace aos::fsm {

struct Table {
    std::string spec;                              // 設定檔（`檔` 或 `檔#/指標`；內嵌單子的 AOS_CF／AOS_CO 由它算）
    std::string start;
    Json states;   // 物件
    std::map<std::string, std::string> exec_bases; // 狀態名 → 那格 exec 裡相對 $ref 的起點（內嵌單子用）
};

struct Cell {
    aos::loop::Target exec;
    std::string next;
};

// 檔不在、`#/` 指不到 CfgMissing；讀不了、不是 JSON、# 寫錯、不是 {"start": 字串, "states": 物件} CfgBad。
// 指示詞（10-23 晚）：整份、states、每一格先換一層，start、exec、next 整個解（相對 $ref 從 fsm.json 的資料夾算；exec 是單子時裡面不解，
// 留到跑的時候，10-24 aos::loop::resolve_exec）；解不開 DirectiveBad。
Table read_table(const std::string& spec);

// 開跑時（讀表後、跑格前）查整張表（使用者 10-22「b、c 開跑時查整張表」）：start 要在表上；每一格要是 {"exec", "next"}、
// exec 合法（字串、[目標, 參數...] 或單子物件；單子的形狀不在這裡查，跑那格時才驗）、next 是表上的狀態名、不是空字串、頭尾沒空白、沒換行（state 檔是純文字一行、
// 讀回來會去頭尾空白）。哪一格不合都＝表壞 CfgBad、不跑格。回每一格解好的樣子。
std::map<std::string, Cell> check(const Table& t);

// 狀態名 → 那格；state 檔裡的狀態不在表上 StateUnknown（where＝state 檔的路徑，寫進原因）。
Cell pick(const std::map<std::string, Cell>& cells, const std::string& state, const std::string& where);

}  // namespace aos::fsm
