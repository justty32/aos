// config.cpp：【engine】Loop 的建構子——讀設定檔（`檔` 或 `檔#/指標`）、解指示詞（resolve_keys，10-23 晚）、旗標蓋上、驗 key（說明見 aos/loop.hpp 的 Loop）；
// 還有 parse_target（exec 的寫法）、resolve_exec、place_inline（內嵌單子在哪，10-24）、loop_cli（命令列）
// （10-21 傍晚 ideas § 9）；錯誤分代號。
#include "engine/engine.hpp"

#include "aos/files.hpp"

#include <cerrno>
#include <climits>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <limits>
#include <system_error>

namespace aos::loop {

bool is_nat(const Json& v) {
    if (v.is_number_unsigned()) {
        return true;
    }
    return v.is_number_integer() && v.get<long long>() >= 0;
}

static long long as_ll(const Json& v) {
    if (v.is_number_unsigned()) {
        unsigned long long u = v.get<unsigned long long>();
        if (u > (unsigned long long)std::numeric_limits<long long>::max()) {
            return std::numeric_limits<long long>::max();
        }
        return (long long)u;
    }
    return v.get<long long>();
}

Target parse_target(const Json& v, const std::string& what) {
    Target t;
    if (v.is_object()) {   // 內嵌單子（10-24）：形狀跑的時候由 run_inst 驗
        t.inst = v;
        return t;
    }
    if (v.is_string()) {
        t.target = v.get<std::string>();
        return t;
    }
    bool ok = v.is_array() && !v.empty();
    if (ok) {
        for (const Json& a : v) {
            if (!a.is_string()) {
                ok = false;
            }
        }
    }
    if (!ok) {
        throw Error{code::CfgBad, what + " 要是 aos-exec 的目標（字串）、[目標, 參數...]（非空字串陣列）或單子（物件）"};
    }
    t.target = v[0].get<std::string>();
    for (size_t i = 1; i < v.size(); ++i) {
        t.args.push_back(v[i].get<std::string>());
    }
    return t;
}

std::string Target::label() const {
    if (!inst) {
        return target;
    }
    return cf.substr(cf.rfind('/') + 1) + "#" + co;
}

std::string pointer_escape(const std::string& key) {
    std::string out;
    for (char c : key) {
        if (c == '~') {
            out += "~0";
        } else if (c == '/') {
            out += "~1";
        } else {
            out += c;
        }
    }
    return out;
}

aos::Resolved resolve_exec(const Json& v, const std::string& base_dir) {
    aos::Resolved r = aos::resolve_shallow(v, base_dir);
    if (!r.value.is_object()) {
        r.value = aos::resolve(r.value, r.base_dir);
    }
    return r;
}

void place_inline(Target& t, const std::string& spec, const std::string& sub, const std::string& ref_base) {
    if (!t.inst) {
        return;
    }
    t.cf = config_file(spec);
    t.co = aos::split_hash(spec).pointer + sub;
    t.ref_base = ref_base;
}

std::string config_file(const std::string& spec) {
    std::string path = aos::split_hash(spec).path;
    std::error_code ec;
    std::filesystem::path real = std::filesystem::canonical(path, ec);   // 解開捷徑（同 aos-exec 的 AOS_CF）
    return ec ? aos::abspath(path) : real.string();
}

aos::Cli loop_cli(const std::vector<std::string>& argv, const std::string& prog) {
    std::string usage = "usage: " + prog + " [--max N] [--interval-ms N] [--ctl 檔] [--state 檔] 設定檔.json";
    aos::Cli cli;
    try {
        cli = aos::parse_cli(argv, {{"--max", "max"}, {"--interval-ms", "interval_ms"}, {"--ctl", "ctl"}, {"--state", "state"}});
    } catch (const Error& e) {
        throw Error{e.code, usage + "（" + e.msg + "）"};   // FlagUnknown／ArgumentsBad
    }
    if (cli.rest.empty()) {
        throw Error{code::ArgumentsBad, usage + "（沒有設定檔）"};
    }
    if (cli.rest.size() > 1) {
        throw Error{code::ArgumentsBad, usage + "（設定檔只能一個，多給了 " + cli.rest[1] + "）"};
    }
    return cli;
}

// 旗標的數字：只收 [0-9]+；太大就夾在 long long 的上限。
static bool flag_nat(const std::string& s, long long& out) {
    if (s.empty()) {
        return false;
    }
    out = 0;
    for (char c : s) {
        if (c < '0' || c > '9') {
            return false;
        }
        if (out > (std::numeric_limits<long long>::max() - (c - '0')) / 10) {
            out = std::numeric_limits<long long>::max();
        } else {
            out = out * 10 + (c - '0');
        }
    }
    return true;
}

aos::Resolved resolve_keys(const Json& doc, const std::string& base_dir, const std::vector<std::string>& keys) {
    aos::Resolved r = aos::resolve_shallow(doc, base_dir);
    if (!r.value.is_object()) {
        return r;
    }
    for (const std::string& k : keys) {
        if (r.value.contains(k)) {
            r.value[k] = aos::resolve(r.value[k], r.dir_of(k));
        }
    }
    return r;
}

Loop::Loop(const std::map<std::string, std::string>& opts, const std::string& spec, const Defaults& d) : d_(d) {
    cfg_ = aos::load_cfg(spec);
    std::string exec_base;   // exec 那格裡相對 $ref 的起點（內嵌單子用）
    try {   // 指示詞（10-23 晚）：相對 $ref 從設定檔所在的資料夾算（N-45；捷徑解開，10-24 審後，config_file）
        aos::Resolved r = resolve_keys(cfg_, aos::dirname(config_file(spec)),
                                       {"max", "interval_ms", "ctl", "state"});
        if (r.value.is_object() && r.value.contains("exec")) {   // exec 是單子時裡面不解（10-24，resolve_exec）
            aos::Resolved ex = resolve_exec(r.value["exec"], r.dir_of("exec"));
            r.value["exec"] = std::move(ex.value);
            exec_base = ex.base_dir;
        }
        cfg_ = std::move(r.value);
        cfg_dirs_ = std::move(r);
        cfg_dirs_.value = nullptr;
    } catch (const Error& e) {
        throw Error{e.code, "設定檔 " + spec + " 的指示詞解不開：" + e.msg};
    }
    if (!cfg_.is_object()) {
        throw Error{code::CfgBad, "設定檔要是 JSON 物件：" + spec};
    }
    const char* nums[2] = {"max", "interval_ms"};   // 旗標 ＞ 設定檔 ＞ 預設（10-21 plan L5）
    for (const char* k : nums) {
        auto it = opts.find(k);
        if (it == opts.end()) {
            continue;
        }
        long long n = 0;
        if (!flag_nat(it->second, n)) {
            std::string flag = k;
            if (flag == "interval_ms") {
                flag = "interval-ms";
            }
            throw Error{code::CfgBad, "--" + flag + " 要是非負整數"};
        }
        cfg_[k] = n;
    }
    const char* wins[2] = {"ctl", "state"};
    for (const char* k : wins) {
        auto it = opts.find(k);
        if (it != opts.end()) {
            cfg_[k] = it->second;
        }
    }
    Json ex = cfg_.value("exec", Json());
    if (!ex.is_null()) {
        exec_ = parse_target(ex, "exec");
        place_inline(exec_, spec, "/exec", exec_base);
        has_exec_ = true;
    } else if (d_.need_exec) {
        throw Error{code::CfgBad, "沒有東西可跑（設定檔沒有 exec）"};
    }
    max_ = d_.max;
    if (cfg_.contains("max")) {
        if (!is_nat(cfg_["max"])) {
            throw Error{code::CfgBad, "max 要是非負整數"};
        }
        max_ = as_ll(cfg_["max"]);
    }
    interval_ms_ = d_.interval_ms;
    if (cfg_.contains("interval_ms")) {
        if (!is_nat(cfg_["interval_ms"])) {
            throw Error{code::CfgBad, "interval_ms 要是非負整數"};
        }
        interval_ms_ = as_ll(cfg_["interval_ms"]);
    }
    const char* s = std::getenv("AOS_STACK");
    if (s != nullptr) {
        stack_ = s;
    }
    const char* keys[2] = {"ctl", "state"};
    std::string* paths[2] = {&ctl_path_, &state_path_};
    for (int i = 0; i < 2; ++i) {
        Json v = cfg_.value(keys[i], Json());
        if (v.is_null()) {
            continue;
        }
        if (!v.is_string() || v.get<std::string>().empty()) {
            throw Error{code::CfgBad, std::string(keys[i]) + " 要是檔名"};
        }
        if (stack_.empty()) {
            throw Error{code::StackMissing, std::string("寫了 ") + keys[i] + " 卻沒設定 AOS_STACK"};
        }
        *paths[i] = aos::join(stack_, v.get<std::string>());
    }
}

}  // namespace aos::loop
