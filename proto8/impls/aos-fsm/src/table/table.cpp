// table.cpp：【table】read_table、check、pick、next_for（說明見 table.hpp；10-22；next 分岔 10-30）。
#include "table/table.hpp"

#include "aos/cli.hpp"
#include "aos/files.hpp"
#include "aos/loop.hpp"
#include "aos/text.hpp"

namespace aos::fsm {

// 指示詞（10-23 晚：aos 讀的 JSON 都解；只解 fsm 自己讀的格，C-52）：整份、states、每一格先換一層，start、格的 exec、next 整個解；
// 格裡其他 key（body…）原封不動，留給跑那格的 aos-exec。相對 $ref 從 fsm.json 所在的資料夾算（換過 $ref 的從那份檔的；
// fsm.json 是捷徑＝實際的資料夾，同 aos-exec，10-24 審後 aos::loop::config_file）。
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
        doc = resolve_table(doc, aos::dirname(aos::loop::config_file(spec)), t.exec_bases);   // 捷徑解開（10-24 審後）
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

// next 裡的一個狀態名（字串 next 本身，或物件 next 的一個值）：不是空字串、頭尾沒空白、沒換行、要在表上。what＝報錯時的稱呼。
static void check_next_name(const Table& t, const std::string& name, const std::string& what, const std::string& next) {
    if (next.empty() || next != aos::strip(next) || next.find('\n') != std::string::npos) {
        throw Error{code::CfgBad,
                    "狀態 " + name + " 的 " + what + " " + aos::dumps(Json(next)) + " 不能是空字串、頭尾不能有空白、不能有換行"};
    }
    if (!t.states.contains(next)) {
        throw Error{code::CfgBad, "狀態 " + name + " 的 " + what + " " + next + " 不在表上"};
    }
}

// 物件 next 的 key：「*」或結束碼 0～255 的十進位寫法（沒有正負號、空白、前導 0——寫成 "010" 永遠查不到，當表壞）。
static bool code_key_ok(const std::string& key) {
    if (key == "*") {
        return true;
    }
    if (key.empty() || key.size() > 3 || (key.size() > 1 && key[0] == '0')) {
        return false;
    }
    for (char ch : key) {
        if (ch < '0' || ch > '9') {
            return false;
        }
    }
    return std::stoi(key) <= 255;
}

std::map<std::string, Cell> check(const Table& t) {
    if (!t.states.contains(t.start)) {
        throw Error{code::CfgBad, "start 的 " + t.start + " 不在表上"};
    }
    std::map<std::string, Cell> cells;
    for (auto& [name, c] : t.states.items()) {   // 照表上的順序查，第一個壞的報出來
        if (!c.is_object() || !c.contains("exec") || !c.contains("next") ||
            !(c["next"].is_string() || c["next"].is_object())) {
            throw Error{code::CfgBad, "狀態 " + name + " 要是 {\"exec\", \"next\"}（next 是狀態名字串或 {結束碼: 狀態名}）"};
        }
        Cell cell;
        if (c["next"].is_string()) {
            std::string next = c["next"].get<std::string>();
            check_next_name(t, name, "next", next);
            cell.next = next;
        } else {   // 10-30 N-36 分岔：{結束碼: 狀態名}
            std::map<std::string, std::string> by_code;
            for (auto& [key, v] : c["next"].items()) {
                if (!code_key_ok(key)) {
                    throw Error{code::CfgBad, "狀態 " + name + " 的 next 的 key " + aos::dumps(Json(key)) +
                                                  " 要是結束碼（0～255 的十進位整數字串）或 \"*\""};
                }
                std::string what = "next[" + aos::dumps(Json(key)) + "]";
                if (!v.is_string()) {
                    throw Error{code::CfgBad, "狀態 " + name + " 的 " + what + " 要是狀態名字串"};
                }
                check_next_name(t, name, what, v.get<std::string>());
                by_code[key] = v.get<std::string>();
            }
            if (!by_code.count("0") && !by_code.count("*")) {
                throw Error{code::CfgBad, "狀態 " + name + " 的 next 至少要有 \"0\" 或 \"*\"（退 0 不能查不到）"};
            }
            cell.next = by_code;
        }
        cell.exec = aos::loop::parse_target(c["exec"], "狀態 " + name + " 的 exec");
        auto base = t.exec_bases.find(name);
        aos::loop::place_inline(cell.exec, t.spec, "/states/" + aos::loop::pointer_escape(name) + "/exec",
                                base == t.exec_bases.end() ? std::string() : base->second);
        cells[name] = cell;
    }
    return cells;
}

std::optional<std::string> next_for(const Cell& cell, int code) {
    if (const auto* s = std::get_if<std::string>(&cell.next)) {
        if (code == 0) {
            return *s;
        }
        return std::nullopt;
    }
    const auto& by_code = std::get<std::map<std::string, std::string>>(cell.next);
    auto it = by_code.find(std::to_string(code));
    if (it == by_code.end()) {
        it = by_code.find("*");
    }
    if (it == by_code.end()) {
        return std::nullopt;
    }
    return it->second;
}

Cell pick(const std::map<std::string, Cell>& cells, const std::string& state, const std::string& where) {
    auto it = cells.find(state);
    if (it == cells.end()) {
        throw Error{code::StateUnknown, "查不到狀態 " + state + "（" + where + " 裡的狀態不在表上）"};
    }
    return it->second;
}

}  // namespace aos::fsm
