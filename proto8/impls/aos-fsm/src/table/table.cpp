// table.cpp：【table】read_table、check、pick（說明見 table.hpp；10-22）。
#include "table/table.hpp"

#include "aos/cli.hpp"
#include "aos/files.hpp"
#include "aos/loop.hpp"
#include "aos/text.hpp"

namespace aos::fsm {

// 指示詞（10-23 晚：aos 讀的 JSON 都解；只解 fsm 自己讀的格，C-52）：整份、states、每一格先換一層，start、格的 exec、next 整個解；
// 格裡其他 key（body…）原封不動，留給跑那格的 aos-exec。相對 $ref 從 fsm.json 所在的資料夾算（換過 $ref 的從那份檔的）。
// exec 是單子（物件）時裡面不解、記下它的起點（10-24，aos::loop::resolve_exec）。
static Json resolve_table(const Json& raw, const std::string& base, std::map<std::string, std::string>& exec_bases) {
    aos::Resolved top = aos::loop::resolve_keys(raw, base, {"start"});
    Json doc = top.value;
    if (!doc.is_object() || !doc.contains("states")) {
        return doc;
    }
    aos::Resolved states = aos::resolve_shallow(doc["states"], top.dir_of("states"));
    if (states.value.is_object()) {
        for (auto& [name, c] : states.value.items()) {
            aos::Resolved cell = aos::loop::resolve_keys(c, states.dir_of(name), {"next"});
            if (cell.value.is_object() && cell.value.contains("exec")) {
                aos::Resolved ex = aos::loop::resolve_exec(cell.value["exec"], cell.dir_of("exec"));
                cell.value["exec"] = std::move(ex.value);
                exec_bases[name] = ex.base_dir;
            }
            c = std::move(cell.value);
        }
    }
    doc["states"] = states.value;
    return doc;
}

Table read_table(const std::string& spec) {
    Json doc = aos::load_cfg(spec);   // `檔` 或 `檔#/指標`（10-21 傍晚 ideas § 9）
    Table t;
    try {
        doc = resolve_table(doc, aos::dirname(aos::abspath(aos::split_hash(spec).path)), t.exec_bases);
    } catch (const Error& e) {
        throw Error{e.code, "設定檔 " + spec + " 的指示詞解不開：" + e.msg};
    }
    if (!doc.is_object() || !doc.contains("states") || !doc["states"].is_object() || !doc.contains("start") ||
        !doc["start"].is_string()) {
        throw Error{code::CfgBad, "fsm.json 要是 {\"start\": 狀態名, \"states\": {名: {\"exec\", \"next\"}}}"};
    }
    t.spec = spec;
    t.start = doc["start"].get<std::string>();
    t.states = doc["states"];
    return t;
}

std::map<std::string, Cell> check(const Table& t) {
    if (!t.states.contains(t.start)) {
        throw Error{code::CfgBad, "start 的 " + t.start + " 不在表上"};
    }
    std::map<std::string, Cell> cells;
    for (auto& [name, c] : t.states.items()) {   // 照表上的順序查，第一個壞的報出來
        if (!c.is_object() || !c.contains("exec") || !c.contains("next") || !c["next"].is_string()) {
            throw Error{code::CfgBad, "狀態 " + name + " 要是 {\"exec\", \"next\"}（next 是狀態名字串）"};
        }
        std::string next = c["next"].get<std::string>();
        if (next.empty() || next != aos::strip(next) || next.find('\n') != std::string::npos) {
            throw Error{code::CfgBad,
                        "狀態 " + name + " 的 next " + aos::dumps(Json(next)) + " 不能是空字串、頭尾不能有空白、不能有換行"};
        }
        if (!t.states.contains(next)) {
            throw Error{code::CfgBad, "狀態 " + name + " 的 next " + next + " 不在表上"};
        }
        Cell cell;
        cell.exec = aos::loop::parse_target(c["exec"], "狀態 " + name + " 的 exec");
        auto base = t.exec_bases.find(name);
        aos::loop::place_inline(cell.exec, t.spec, "/states/" + aos::loop::pointer_escape(name) + "/exec",
                                base == t.exec_bases.end() ? std::string() : base->second);
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
