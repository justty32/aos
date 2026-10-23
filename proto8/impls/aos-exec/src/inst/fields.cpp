// fields.cpp：【inst】單子（$env 已解）→ Inst：認得 10 個 key、驗型別。
//
// 10 個 key 與檢查順序（10-19 版）：
//   argv（非空字串陣列，必填）→ envs（{名: 字串}）→ cwd／stdin／stdout／stderr（字串或 null）→
//   stdout_append／stderr_append（true／false）→ timeout_ms（正整數或 null）→ grace_ms（非負整數，沒寫 2000）
// 其他 key 一律忽略（包括 impls/aos-inst 認得的 id、envs_clear、cwd_mkdir、stdout_mkdir、stderr_mkdir、stderr_merge）。
// 驗不過一律 EntryBad（單子就是入口，寫壞＝入口壞）。
#include "inst/inst.hpp"

namespace aos::exec {

static std::string shown(const Json& v) {
    return v.dump(-1, ' ', false, Json::error_handler_t::replace);
}

[[noreturn]] static void bad(const std::string& key, const std::string& want, const Json& v) {
    throw Error{code::EntryBad, "單子的 " + key + " 要是" + want + "，不是 " + shown(v)};
}

// 整數（不含 bool、小數）且 >= min。
static bool is_int_at_least(const Json& v, unsigned long long min) {
    if (v.is_number_unsigned()) {
        return v.get<unsigned long long>() >= min;
    }
    if (v.is_number_integer()) {
        long long n = v.get<long long>();
        return n >= 0 && (unsigned long long)n >= min;
    }
    return false;
}

Inst parse_inst(const Json& doc, const std::vector<std::string>& args) {
    if (!doc.is_object()) {
        throw Error{code::EntryBad, "單子要是 JSON 物件，不是 " + shown(doc)};
    }
    Inst inst;

    Json argv = doc.value("argv", Json());
    if (!argv.is_array() || argv.empty()) {
        bad("argv", "非空的字串陣列", argv);
    }
    for (const Json& a : argv) {
        if (!a.is_string()) {
            bad("argv", "非空的字串陣列", argv);
        }
        inst.argv.push_back(a.get<std::string>());
    }
    inst.argv.insert(inst.argv.end(), args.begin(), args.end());

    if (doc.contains("envs")) {
        const Json& envs = doc["envs"];
        if (!envs.is_object()) {
            bad("envs", "{名字: 字串}", envs);
        }
        for (auto& [k, v] : envs.items()) {
            if (!v.is_string()) {
                bad("envs", "{名字: 字串}", envs);
            }
            inst.envs[k] = v.get<std::string>();
        }
    }

    const char* path_keys[4] = {"cwd", "stdin", "stdout", "stderr"};
    for (int i = 0; i < 4; ++i) {
        Json v = doc.value(path_keys[i], Json());
        if (v.is_null()) {
            continue;
        }
        if (!v.is_string()) {
            bad(path_keys[i], "字串路徑", v);
        }
        if (i == 0) {
            inst.cwd = v.get<std::string>();
        } else {
            inst.paths[i - 1] = v.get<std::string>();
        }
    }

    const char* append_keys[3] = {nullptr, "stdout_append", "stderr_append"};
    for (int i = 1; i < 3; ++i) {
        Json v = doc.value(append_keys[i], Json(false));
        if (!v.is_boolean()) {
            bad(append_keys[i], " true／false", v);
        }
        inst.appends[i] = v.get<bool>();
    }

    Json t = doc.value("timeout_ms", Json());
    if (!t.is_null()) {
        if (!is_int_at_least(t, 1)) {
            bad("timeout_ms", "正整數或 null", t);
        }
        inst.timeout_ms = t.get<unsigned long long>();
    }
    if (doc.contains("grace_ms")) {
        const Json& g = doc["grace_ms"];
        if (!is_int_at_least(g, 0)) {
            bad("grace_ms", "非負整數", g);
        }
        inst.grace_ms = g.get<unsigned long long>();
    }
    return inst;
}

}  // namespace aos::exec
