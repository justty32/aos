// table.cpp：【table】read_table、check、pick（說明見 table.hpp）。照 proto8/bin/aos-fsm 的 main 開頭與 check（10-22）。
#include "table/table.hpp"

#include "aos/cli.hpp"
#include "aos/text.hpp"

namespace aos::fsm {

Table read_table(const std::string& spec) {
    Json doc = aos::load_cfg(spec);   // `檔` 或 `檔#/指標`（10-21 傍晚 ideas § 9）
    if (!doc.is_object() || !doc.contains("states") || !doc["states"].is_object() || !doc.contains("start") ||
        !doc["start"].is_string()) {
        throw Error{code::CfgBad, "fsm.json 要是 {\"start\": 狀態名, \"states\": {名: {\"val\", \"next\"}}}"};
    }
    Table t;
    t.start = doc["start"].get<std::string>();
    t.states = doc["states"];
    return t;
}

std::map<std::string, Cell> check(const Table& t) {
    if (!t.states.contains(t.start)) {
        throw Error{code::CfgBad, "start 的 " + t.start + " 不在表上"};
    }
    std::map<std::string, Cell> cells;
    for (auto& [name, c] : t.states.items()) {   // 照表上的順序查，第一個壞的報出來（同 bin）
        if (!c.is_object() || !c.contains("val") || !c.contains("next") || !c["next"].is_string()) {
            throw Error{code::CfgBad, "狀態 " + name + " 要是 {\"val\", \"next\"}（next 是狀態名字串）"};
        }
        std::string next = c["next"].get<std::string>();
        if (next.empty() || next != aos::strip(next) || next.find('\n') != std::string::npos) {
            throw Error{code::CfgBad,
                        "狀態 " + name + " 的 next " + aos::dumps(Json(next)) + " 不能是空字串、頭尾不能有空白、不能有換行"};
        }
        if (!t.states.contains(next)) {
            throw Error{code::CfgBad, "狀態 " + name + " 的 next " + next + " 不在表上"};
        }
        if (c["val"].is_object()) {
            throw Error{code::CfgBad, "狀態 " + name + " 的 val 要是 aos-exec 的目標（字串或字串陣列）；要內嵌單子寫 fsm.json#/states/" +
                                             name + "/body"};
        }
        Cell cell;
        cell.val = aos::loop::parse_target(c["val"], "狀態 " + name + " 的 val");
        cell.next = next;
        cells[name] = cell;
    }
    return cells;
}

Cell pick(const std::map<std::string, Cell>& cells, const std::string& state, const std::string& where) {
    auto it = cells.find(state);
    if (it == cells.end()) {
        throw Error{code::StateUnknown, "查不到狀態 " + state + "（" + where + " 裡的狀態不在表上）"};
    }
    return it->second;
}

}  // namespace aos::fsm
