// config.cpp：【serve】讀 kernel 設定、驗 slots 與 high 保留格、解指示詞與 endpoint 函數路徑（說明見 serve.hpp）。
#include "serve/serve.hpp"

#include "aos/util/cli.hpp"
#include "aos/directive.hpp"
#include "aos/util/files.hpp"

namespace aos::llm_kernel {

// aos-exec 目標（資料夾、檔、`檔#/指標`）：相對的從 base 算、轉成絕對（信資料夾裡跑的 aos-exec 才找得到）。
std::string target_abs(const std::string& t, const std::string& base) {
    aos::Spec sp = aos::split_hash(t);
    std::string p = aos::abspath(aos::join(base, sp.path));
    if (sp.pointer.empty()) {
        return p;
    }
    return p + "#" + sp.pointer;
}

Cfg read_cfg(const std::string& spec, const std::string& stack) {
    Json doc = aos::load_cfg(spec);
    std::string base = aos::dirname(aos::abspath(aos::split_hash(spec).path));
    aos::Resolved r = aos::resolve_keys(doc, base, {"slots", "reserved", "aging_ticks", "budget", "exec", "endpoint", "timeout_ms"});
    doc = r.value;
    if (!doc.is_object()) {
        throw Error{code::CfgBad, spec + " must be a JSON object"};
    }
    Cfg c;
    c.base = base;
    c.requests = aos::join(stack, "requests");   // 11-05 固定（AOS_LLM_KERNEL＝kernel 的 stack，寄信的人從 stack 算信箱）
    if (doc.contains("aging_ticks")) {
        const Json& aging = doc["aging_ticks"];
        if (!aos::is_count(aging) || aging.get<long long>() < 1) {
            throw Error{code::CfgBad, "aging_ticks must be a positive integer (ticks per priority level), got " + aos::dumps(aging)};
        }
        c.aging_ticks = aging.get<long long>();
    }
    Json s = doc.value("slots", Json());
    if (!s.is_null()) {
        if (!aos::is_count(s) || s.get<long long>() < 1) {
            throw Error{code::CfgBad, "slots must be a positive integer (letters run at once), got " + aos::dumps(s)};
        }
        c.slots = s.get<long long>();
    }
    if (doc.contains("reserved")) {
        const Json& reserved = doc["reserved"];
        if (!reserved.is_object()) {
            throw Error{code::CfgBad, "reserved must be an object with only an optional high count, got " + aos::dumps(reserved)};
        }
        for (const auto& [key, value] : reserved.items()) {
            if (key != "high") {
                throw Error{code::CfgBad, "reserved has an unknown key: " + key + " (only high is allowed)"};
            }
            if (!aos::is_count(value) || value.get<unsigned long long>() >= static_cast<unsigned long long>(c.slots)) {
                throw Error{code::CfgBad, "reserved.high must be a non-negative integer smaller than slots, got " + aos::dumps(value)};
            }
            c.reserved_high = value.get<long long>();
        }
    }
    c.budget = parse_budget(doc.value("budget", Json()), base, stack);   // senders 從設定檔算位置、以相對 kernel stack 記帳
    Json ex = doc.value("exec", Json());
    if (!ex.is_string() || ex.get<std::string>().empty()) {
        throw Error{code::CfgBad, "exec must be a non-empty string (the endpoint function: a directory, a file or `file#/pointer`, relative to kernel.json's directory), got " + aos::dumps(ex)};
    }
    c.exec = target_abs(ex.get<std::string>(), base);
    if (!doc.contains("endpoints")) {
        throw Error{code::CfgBad, "missing endpoints (name -> llm settings)"};
    }
    aos::Resolved eps = aos::resolve_shallow(doc["endpoints"], r.dir_of("endpoints"));
    if (!eps.value.is_object() || eps.value.empty()) {
        throw Error{code::CfgBad, "endpoints must be a non-empty object (name -> llm settings), got " + aos::dumps(eps.value)};
    }
    c.endpoints = eps.value;
    for (auto& [k, v] : c.endpoints.items()) {
        c.endpoint_dirs[k] = eps.dir_of(k);
    }
    c.packs = read_packs(c.endpoints, c.endpoint_dirs);
    Json ep = doc.value("endpoint", Json());
    if (!ep.is_null()) {
        if (!ep.is_string() || !c.endpoints.contains(ep.get<std::string>())) {
            throw Error{code::CfgBad, "endpoint (the default name) must be a name in endpoints, got " + aos::dumps(ep)};
        }
        c.endpoint = ep.get<std::string>();
    }
    Json t = doc.value("timeout_ms", Json());
    if (!t.is_null()) {
        if (!aos::is_count(t)) {
            throw Error{code::CfgBad, "timeout_ms must be a non-negative integer (time limit for the endpoint function), got " + aos::dumps(t)};
        }
        c.timeout_ms = t.get<long long>();
    }
    return c;
}

}  // namespace aos::llm_kernel
