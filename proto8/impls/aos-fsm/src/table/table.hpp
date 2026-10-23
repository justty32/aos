// table.hpp：【table】fsm.json——`{"start": 狀態名, "states": {名: {"val": aos-exec 的目標或 [目標, 參數...], "next": 下一個狀態名}}}`。內部標頭。
//
//   table.cpp   read_table：讀設定檔（`檔` 或 `檔#/指標`）、驗 start／states；pick：狀態名 → 那格（照 Python 版 proto8/bin/aos-fsm）
//
// 表一定明寫、next 只在表上（N-36）。val 只收目標（10-21 plan F2；傍晚 ideas § 9 加陣列）：要內嵌單子寫
// `fsm.json#/states/<名>/body`、單子放在同一格的 body，由 aos-exec 跑。表裡其他 key（body、_exec…）忽略（C-48）。
#pragma once

#include "common/common.hpp"

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

// 讀不到 ReadFailed、不是 JSON JsonSyntax、# 寫錯或指不到、不是 {"start": 字串, "states": 物件} FieldType。
Table read_table(const std::string& spec);

// 查不到、或不是 {"val", "next": 字串} StateUnknown；val 是物件或不是目標 FieldType。
Cell pick(const Table& t, const std::string& state);

}  // namespace aos::fsm
