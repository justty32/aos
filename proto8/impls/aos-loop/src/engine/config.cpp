// config.cpp：【engine】Loop 的建構子——讀設定檔（`檔` 或 `檔#/指標`）、解指示詞（resolve_keys，10-23 晚）、旗標蓋上、驗 key（說明見 aos/loop.hpp 的 Loop）；
// 還有 parse_target（exec 的寫法）、resolve_exec、place_inline（內嵌單子在哪，10-24）、loop_cli（命令列；--enable-logs、--enable-counters 開關、
// 設定檔後面的 `-- 參數...`）、add_args（附加參數接到 exec 後面）
// （10-21 傍晚 ideas § 9）；錯誤分代號。11-11：on_start／on_stop（寫法同 exec）與 on_timeout_ms。
#include "engine/engine.hpp"

#include "aos/util/files.hpp"

#include <cerrno>
#include <climits>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <limits>
#include <system_error>

namespace aos::loop {

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
        throw Error{code::CfgBad, what + " must be an aos-exec target (string), [target, args...] (non-empty array of strings) or an inst (object)"};
    }
    t.target = v[0].get<std::string>();
    for (size_t i = 1; i < v.size(); ++i) {
        t.args.push_back(v[i].get<std::string>());
    }
    return t;
}

std::string Target::label() const {
    if (!inst) {   // 錯誤行裡給人看的：整理成最短寫法（daemon 小格的 $AOS_DAEMON/../../x 這種；只動顯示、照字面不解捷徑，11-05 晚）
        std::string s = std::filesystem::path(target).lexically_normal().string();
        return s.empty() ? target : s;
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

aos::Cli loop_cli(const std::vector<std::string>& argv, const std::string& prog, const std::string& help,
                  const std::string& cfg_name) {
    std::string usage = prog + " [--max N] [--interval-ms N] [--ctl FILE] [--state FILE] [--state-flux FILE] [--enable-logs] [--enable-counters] " + cfg_name +
                        " [-- ARGS...]";
    aos::Cli cli;
    try {
        cli = aos::parse_cli(argv, {{"--max", "max"}, {"--interval-ms", "interval_ms"}, {"--ctl", CtlWindow::config_key}, {"--state", StateWindow::config_key}, {"--state-flux", StateFluxWindow::config_key}},
                             {{"--enable-logs", "enable_logs"}, {"--enable-counters", "enable_counters"}}, help);
    } catch (const Error& e) {
        throw aos::usage_error(e.code, e.msg, usage);   // FlagUnknown／ArgumentsBad
    }
    if (cli.rest.empty()) {
        throw aos::usage_error(code::ArgumentsBad, "missing config file", usage);
    }
    // 11-02 晚（使用者「aos-XXX ... ... -- ...」）：設定檔之後接 `--`＝後面全是附加參數（rest＝[設定檔, 參數...]，`--` 剝掉）；
    // 接別的＝照舊 ArgumentsBad。設定檔之前的 `--` 是 parse_cli 的「旗標結束」，不受影響。
    if (cli.rest.size() > 1 && cli.rest[1] != "--") {
        // 11-05 B 線：設定檔後面接旗標，多半是 `aos-exec 定義 --enable-logs`（aos-exec 把參數接在 _entry 後面）；照舊不收，但別叫人寫到 -- 後面（那是給身體的）
        if (cli.rest[1].size() > 1 && cli.rest[1][0] == '-') {
            throw aos::usage_error(code::ArgumentsBad, "flag " + cli.rest[1] + " must come before the config file; when started via aos-exec, put flags in the definition's _entry before the config file, e.g. [\"" + prog +
                                                           "\", \"--enable-logs\", \"config.json\"]", usage);
        }
        throw aos::usage_error(code::ArgumentsBad, "only one config file allowed, got extra " + cli.rest[1] + "; put extra args after --", usage);
    }
    if (cli.rest.size() > 1) {
        cli.rest.erase(cli.rest.begin() + 1);
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
    return aos::resolve_keys(doc, base_dir, keys);
}

void add_args(Target& t, const std::vector<std::string>& args) {
    if (args.empty()) {
        return;
    }
    if (!t.inst) {   // 字串＝[目標, 參數...]、陣列＝接在最後
        t.args.insert(t.args.end(), args.begin(), args.end());
        return;
    }
    // 內嵌單子：接在單子 argv 的最後（argv 要是陣列；是指示詞或沒寫＝CfgBad，跑之前接不上）。字串不是指示詞，原樣接
    Json& inst = *t.inst;
    if (!inst.is_object() || !inst.contains("argv") || !inst["argv"].is_array()) {
        throw Error{code::CfgBad, "with extra args after --, the argv of the exec inst must be a literal array (to append them)"};
    }
    for (const std::string& a : args) {
        inst["argv"].push_back(a);
    }
}

Loop::Loop(const std::map<std::string, std::string>& opts, const std::string& spec, const Defaults& d,
           const std::vector<std::string>& args) : d_(d) {
    log_ = opts.count("enable_logs") > 0;   // 11-02 晚：log 預設不印（使用者「應該要改成默認不印」），--enable-logs 才印到 stdout
    counters_ = opts.count("enable_counters") > 0;
    cfg_ = aos::load_cfg(spec);
    std::string exec_base;   // exec 那格裡相對 $ref 的起點（內嵌單子用）
    std::map<std::string, std::string> side_base;   // 11-11 on_start／on_stop 同 exec
    try {   // 指示詞（10-23 晚）：相對 $ref 從設定檔所在的資料夾算（N-45；捷徑解開，10-24 審後，config_file）
        aos::Resolved r = resolve_keys(cfg_, aos::dirname(config_file(spec)),
                                       {"max", "interval_ms", "on_timeout_ms", CtlWindow::config_key, StateWindow::config_key, StateFluxWindow::config_key});
        for (const char* k : {"exec", "on_start", "on_stop"}) {   // 是單子時裡面不解（10-24，resolve_exec；11-11 起停兩格同 exec）
            if (r.value.is_object() && r.value.contains(k) && !r.value[k].is_null()) {
                aos::Resolved ex = resolve_exec(r.value[k], r.dir_of(k));
                r.value[k] = std::move(ex.value);
                side_base[k] = ex.base_dir;
            }
        }
        exec_base = side_base["exec"];
        cfg_ = std::move(r.value);
        cfg_dirs_ = std::move(r);
        cfg_dirs_.value = nullptr;
    } catch (const Error& e) {
        throw Error{e.code, "config " + spec + ": cannot resolve directives: " + e.msg};
    }
    if (!cfg_.is_object()) {
        throw Error{code::CfgBad, "config must be a JSON object: " + spec};
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
            throw Error{code::ArgumentsBad, "--" + flag + " must be a non-negative integer"};   // 11-05 第二輪：旗標的值錯＝命令列用錯（原本 CfgBad）
        }
        cfg_[k] = n;
    }
    const char* wins[3] = {CtlWindow::config_key, StateWindow::config_key, StateFluxWindow::config_key};
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
        add_args(exec_, args);
    } else if (d_.need_exec) {
        throw Error{code::CfgBad, "nothing to run (config has no exec)"};
    } else if (!args.empty()) {
        throw Error{code::ArgumentsBad, "no exec (body), so the extra args after -- have nowhere to go"};   // daemon 純監工（11-02 晚代定）
    }
    // 11-11（使用者選「aos-loop 自己加」）：起來、要退時各跑一次；寫法同 exec，null＝沒有
    std::optional<Target>* sides[2] = {&on_start_, &on_stop_};
    const char* side_keys[2] = {"on_start", "on_stop"};
    for (int i = 0; i < 2; ++i) {
        Json v = cfg_.value(side_keys[i], Json());
        if (v.is_null()) {
            continue;
        }
        Target t = parse_target(v, side_keys[i]);
        place_inline(t, spec, std::string("/") + side_keys[i], side_base[side_keys[i]]);
        *sides[i] = std::move(t);
    }
    if (cfg_.contains("on_timeout_ms")) {
        if (!aos::is_count(cfg_["on_timeout_ms"]) || as_ll(cfg_["on_timeout_ms"]) <= 0) {
            throw Error{code::CfgBad, "on_timeout_ms must be a positive integer"};
        }
        on_timeout_ms_ = as_ll(cfg_["on_timeout_ms"]);
    }
    max_ = d_.max;
    if (cfg_.contains("max")) {
        if (!aos::is_count(cfg_["max"])) {
            throw Error{code::CfgBad, "max must be a non-negative integer"};
        }
        max_ = as_ll(cfg_["max"]);
    }
    interval_ms_ = d_.interval_ms;
    if (cfg_.contains("interval_ms")) {
        if (!aos::is_count(cfg_["interval_ms"])) {
            throw Error{code::CfgBad, "interval_ms must be a non-negative integer"};
        }
        interval_ms_ = as_ll(cfg_["interval_ms"]);
    }
    const char* s = std::getenv("AOS_STACK");
    if (s != nullptr) {
        stack_ = s;
    }
    // 11-04（使用者題 5「留 key、沒寫時預設就是這組名」）：沒寫＝ctl.json／state.json／state_flux.json；寫 null＝不開
    const char* keys[3] = {CtlWindow::config_key, StateWindow::config_key, StateFluxWindow::config_key};
    const char* default_names[3] = {CtlWindow::default_name, StateWindow::default_name, StateFluxWindow::default_name};
    std::string* paths[3] = {&ctl_path_, &state_path_, &state_flux_path_};
    for (int i = 0; i < 3; ++i) {
        Json v = cfg_.contains(keys[i]) ? cfg_[keys[i]] : Json(default_names[i]);
        if (v.is_null()) {
            continue;
        }
        if (!v.is_string() || v.get<std::string>().empty()) {
            throw Error{code::CfgBad, std::string(keys[i]) + " must be a file name"};
        }
        if (stack_.empty()) {
            throw Error{code::StackMissing, std::string("the ") + keys[i] + " window needs AOS_STACK, which is not set (write null to turn it off)"};
        }
        *paths[i] = aos::join(stack_, v.get<std::string>());
    }
}

}  // namespace aos::loop
