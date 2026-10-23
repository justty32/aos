// table.cpp：【table】read_table、pick（說明見 table.hpp）。
#include "table/table.hpp"

#include "aos/cli.hpp"

namespace aos::fsm {

Table read_table(const std::string& spec) {
    Json doc = aos::load_cfg(spec);   // `檔` 或 `檔#/指標`（10-21 傍晚 ideas § 9）
    if (!doc.is_object() || !doc.contains("states") || !doc["states"].is_object() || !doc.contains("start") ||
        !doc["start"].is_string()) {
        throw Error{code::FieldType, "fsm.json 要是 {\"start\": 狀態名, \"states\": {名: {\"val\", \"next\"}}}"};
    }
    Table t;
    t.start = doc["start"].get<std::string>();
    t.states = doc["states"];
    return t;
}

Cell pick(const Table& t, const std::string& state) {
    if (!t.states.contains(state)) {
        throw Error{code::StateUnknown, "查不到狀態 " + state};
    }
    const Json& c = t.states[state];
    if (!c.is_object() || !c.contains("val") || !c.contains("next") || !c["next"].is_string()) {
        throw Error{code::StateUnknown, "狀態 " + state + " 不是 {\"val\", \"next\"}"};
    }
    if (c["val"].is_object()) {
        throw Error{code::FieldType, "狀態 " + state + " 的 val 要是 aos-exec 的目標（字串或字串陣列）；要內嵌單子寫 fsm.json#/states/" +
                                         state + "/body"};
    }
    Cell cell;
    cell.val = aos::loop::parse_target(c["val"], "狀態 " + state + " 的 val");
    cell.next = c["next"].get<std::string>();
    return cell;
}

}  // namespace aos::fsm
