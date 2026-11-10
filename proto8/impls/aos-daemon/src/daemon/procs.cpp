// procs.cpp：【daemon】解讀 proc 名單、辨認寫法、整理路徑與合併期望表（說明見 daemon.hpp）。
#include "daemon/daemon.hpp"
#include "child/limits.hpp"
#include "aos/util/files.hpp"
#include <limits>
#include <unordered_map>
#include <unordered_set>

namespace aos::daemon {

static void check_name(const std::string& name, const std::string& key) {
    if (name.empty() || name.find('/') != std::string::npos || name.find('#') != std::string::npos || name[0] == '.') {
        throw Error{code::CfgBad, key + ": name " + aos::dumps(Json(name)) + " cannot be a directory name"};
    }
}

Json abs_refs(const Json& v, const std::string& base) {
    if (v.is_array()) {
        Json out = Json::array();
        for (const Json& x : v) {
            out.push_back(abs_refs(x, base));
        }
        return out;
    }
    if (!v.is_object()) {
        return v;
    }
    Json out = v;
    if (v.contains("$ref")) {   // 指示詞：只動 $ref 的檔名（其他 key 指示詞不看，不往裡面走）
        auto fix = [&](Json& s) {
            if (!s.is_string()) {
                return;
            }
            std::string r = s.get<std::string>();
            size_t hash = r.find('#');
            std::string file = r.substr(0, hash);
            if (!file.empty() && file[0] != '/') {
                s = aos::join(base, file) + (hash == std::string::npos ? "" : r.substr(hash));
            }
        };
        Json& ref = out["$ref"];
        if (ref.is_array()) {
            for (Json& s : ref) {
                fix(s);
            }
        } else {
            fix(ref);
        }
        return out;
    }
    for (auto& [k, x] : out.items()) {
        x = abs_refs(x, base);
    }
    return out;
}

// proc 物件的 ws、stack（eca 10-30；stack 11-03 procs § 2b）：要是非空字串（null＝當沒寫、拿掉），相對路徑從 daemon 的 cwd 轉絕對（abspath 從行程的 cwd 算；
// daemon 自己不 cd，所以就是 daemon 的 cwd——信、procs_ctl、daemon.json 裡寫的都一樣，同相對 exec）；abspath 結尾不帶 /。不驗在不在
// （ws：aos-exec 會報 WsMissing，寫在小格 stderr.txt；stack：起的時候不在就建）。
static void fix_path(Json& c, const std::string& name, const std::string& key, const char* k, const char* what) {
    if (!c.contains(k)) {
        return;
    }
    const Json& w = c[k];
    if (w.is_null()) {
        c.erase(k);
        return;
    }
    if (!w.is_string() || w.get<std::string>().empty()) {
        throw Error{code::CfgBad, key + "[" + name + "]." + k + " must be a " + what + " path (non-empty string)"};
    }
    c[k] = aos::abspath(w.get<std::string>());
}

// 11-10 two-machines（使用者「兩台各自設一次...不要限制只設一次」）：寫成指示詞的值（有 $env 或 $ref 的物件）。
static bool is_directive(const Json& v) {
    return v.is_object() && (v.contains("$env") || v.contains("$ref"));
}

// 解開之前記下路徑欄的指示詞原形（$ref 的檔名照寫它的檔轉絕對）：ws、stack、def，與目標（exec 本身、或 exec 陣列的第一個）。
// 只記解完是字串目標的 exec（單子、陣列整個是指示詞的不記）。沒有＝空物件。
static Json written_of(const Json& raw, const Json& resolved, const std::string& base) {
    Json w = Json::object();
    if (!raw.is_object()) {
        if (raw.is_array() && !raw.empty() && is_directive(raw[0])) {
            w["exec"] = abs_refs(raw[0], base);
        }
        return w;
    }
    for (const char* k : {"ws", "stack", "def"}) {
        if (raw.contains(k) && is_directive(raw[k])) {
            w[k] = abs_refs(raw[k], base);
        }
    }
    Json ex = raw.value("exec", Json());
    Json got = resolved.is_object() ? resolved.value("exec", Json()) : Json();
    if (is_directive(ex) && got.is_string()) {
        w["exec"] = abs_refs(ex, base);
    } else if (ex.is_array() && !ex.empty() && is_directive(ex[0]) && got.is_array() && !got.empty() && got[0].is_string()) {
        w["exec"] = abs_refs(ex[0], base);
    }
    return w;
}

// 11-10 晚 two-machines B01（使用者選「絕對路徑原樣存」：「add xxx 會換算(除了絕對路徑)」）：寫的人在 proc 物件裡給的
// "as_written": {ws?, stack?, def?, exec?}，值只收絕對路徑字串（`檔#/…` 的 # 前面要絕對）＝表上照原樣記、每次起照它（不換算成相對 daemon 的 stack）。
// 指示詞原形由 written_of 從各格自己認，這裡不收；別的寫法＝CfgBad（不默默丟掉）。沒寫＝空物件。
static Json kept_of(const Json& raw, const std::string& name, const std::string& key) {
    Json out = Json::object();
    if (!raw.is_object() || !raw.contains("as_written") || raw["as_written"].is_null()) {
        return out;
    }
    const Json& h = raw["as_written"];
    const std::string where = key + "[" + name + "].as_written";
    if (!h.is_object()) {
        throw Error{code::CfgBad, where + " must be {ws?, stack?, def?, exec?} of absolute paths"};
    }
    for (auto& [k, x] : h.items()) {
        if (k != "ws" && k != "stack" && k != "def" && k != "exec") {
            throw Error{code::CfgBad, where + ": unknown key " + aos::dumps(Json(k)) + " (keys: ws, stack, def, exec)"};
        }
        if (!x.is_string() || x.get<std::string>().empty() || x.get<std::string>()[0] != '/') {
            throw Error{code::CfgBad, where + "." + k + " must be an absolute path (kept as written), got " + aos::dumps(x)};
        }
        out[k] = x;
    }
    return out;
}

static bool is_target(const Json& t) {   // aos-exec 的目標：字串或 [目標, 參數...]（非空字串陣列）
    if (t.is_string()) {
        return true;
    }
    if (!t.is_array() || t.empty()) {
        return false;
    }
    for (const Json& a : t) {
        if (!a.is_string()) {
            return false;
        }
    }
    return true;
}

Json exec_of(const Json& spec, const std::string& cwd) {
    Json t = spec.is_object() ? spec.value("exec", Json()) : spec;
    if (t.is_array() && !t.empty()) {
        t = Json(t[0]);
    }
    if (!t.is_string()) {
        return Json();   // 內嵌單子、null（只留名）、設定沒寫 exec
    }
    std::string v = t.get<std::string>();
    if (v.empty() || v[0] == '#') {
        return Json(v);
    }
    size_t hash = v.find('#');   // 11-05：整理掉 ..（表上存相對 daemon 的 stack，`daemon/../kernel` 這種要先收掉）
    return Json(aos::abspath(aos::join(cwd, v.substr(0, hash))) + (hash == std::string::npos ? "" : v.substr(hash)));
}

// 保存再起所需的設定；入口路徑先照 daemon cwd 固定，參數不改。
Json launch_of(const Json& spec, const std::string& cwd) {
    if (spec.is_null()) {
        return Json();
    }
    Json out = spec.is_object() ? spec : Json::object({{"exec", spec}});
    Json target = out.value("exec", Json());
    if (target.is_string()) {
        out["exec"] = exec_of(spec, cwd);
    } else if (target.is_array() && !target.empty()) {
        out["exec"][0] = exec_of(spec, cwd);
    }
    return out;
}

Json def_of(const Json& spec) {
    return spec.is_object() ? spec.value("def", Json()) : Json();   // read_procs 已轉絕對（fix_path）；不驗在不在
}

bool auto_restart_of(const Json& spec) {
    return spec.is_object() && spec.value("auto_restart", Json()) == Json(true);
}

bool ros_of(const Json& spec) {
    return spec.is_object() && spec.value("restart_on_stuck", Json()) == Json(true);
}

bool is_once(const Json& spec) {
    if (spec.is_string() || spec.is_array()) {
        return true;
    }
    if (!spec.is_object() || !spec.contains("exec")) {
        return false;
    }
    for (auto& [k, v] : spec.items()) {
        if (k != "exec" && k != "ws" && k != "stack" && k != "def" && k != "limits" && k != "auto_restart" && k != "restart_on_stuck" && k != "stuck_after_cycles" && k != "stuck_after_ms" && k != "as_written") {
            return false;   // 多了任何一個 key＝loop 設定（procs § 2 第 3 條）
        }
    }
    return true;
}

Json read_procs(const Json& v, const std::string& base, const std::string& key) {
    aos::Resolved top = aos::resolve_shallow(v, base);   // 拆成好幾份檔＝{"$ref": [檔, …]}，合好的每個子項記著它來自哪份檔
    if (!top.value.is_object()) {
        throw Error{code::CfgBad, key + " must be {name: proc}"};
    }
    Json out = Json::object();   // 名字本來就不重複（JSON 物件；$ref 陣列合的同名後面的蓋前面的），直接接在尾巴
    auto& vec = static_cast<std::vector<std::pair<const std::string, Json>>&>(out.get_ref<Json::object_t&>());
    vec.reserve(top.value.size());
    const std::string bad_target = " must be an aos-exec target (string or [target, args...]), {\"exec\": target or inst} or a loop config";
    for (auto& [name, c] : top.value.items()) {
        check_name(name, key);
        aos::Resolved it = aos::resolve_shallow(c, top.dir_of(name));
        if (it.value.is_string() || it.value.is_array()) {   // exec 型（procs § 2 第 1 條）
            Json t = aos::resolve(it.value, it.base_dir);
            if (!is_target(t)) {
                throw Error{code::CfgBad, key + "[" + name + "]" + bad_target};
            }
            Json w = written_of(it.value, t, it.base_dir);
            if (!w.empty()) {   // 11-10：目標寫成指示詞＝改寫成 {"exec": 目標, "as_written": …}（同一種 exec 型）
                t = Json::object({{"exec", std::move(t)}, {"as_written", std::move(w)}});
            }
            vec.emplace_back(name, std::move(t));
        } else if (it.value.is_object()) {
            aos::Resolved r = aos::loop::resolve_keys(it.value, it.base_dir, {"max", "interval_ms", aos::loop::CtlWindow::config_key, aos::loop::StateWindow::config_key, aos::loop::StateFluxWindow::config_key, "ws", "stack", "def", "limits", "auto_restart", "restart_on_stuck", "stuck_after_cycles", "stuck_after_ms"});
            if (r.value.is_object() && r.value.contains("exec")) {   // exec 是單子時裡面不解、相對 $ref 轉成絕對（10-24）
                aos::Resolved ex = aos::loop::resolve_exec(r.value["exec"], r.dir_of("exec"));
                if (ex.value.is_object()) {
                    ex.value = abs_refs(ex.value, ex.base_dir);
                }
                r.value["exec"] = std::move(ex.value);
            }
            if (!r.value.is_object()) {
                throw Error{code::CfgBad, key + "[" + name + "]" + bad_target};
            }
            r.value.erase("as_written");   // daemon 自己記的 key（11-10）；寫的人給的只收「原樣存的絕對路徑」（kept_of，11-10 晚 B01）
            Json w = written_of(it.value, r.value, it.base_dir);
            Json kept = kept_of(it.value, name, key);
            for (auto& [k, x] : kept.items()) {
                if (!w.contains(k)) {   // 同一格寫成指示詞的以指示詞為準
                    w[k] = x;
                }
            }
            if (!w.empty()) {
                r.value["as_written"] = std::move(w);
            }
            if (r.value.contains("stuck_after_cycles") && r.value.contains("stuck_after_ms")) {
                throw Error{code::CfgBad, key + "[" + name + "]: stuck_after_cycles and stuck_after_ms must not both be set"};
            }
            if (r.value.contains("stuck_after_cycles") && (!aos::is_count(r.value["stuck_after_cycles"]) || r.value["stuck_after_cycles"].get<long long>() <= 0)) {
                throw Error{code::CfgBad, key + "[" + name + "].stuck_after_cycles must be a positive integer"};
            }
            if (r.value.contains("stuck_after_ms")) {
                const Json& ms = r.value["stuck_after_ms"];
                if (!aos::is_count(ms) || ms == Json(0) ||
                    (ms.is_number_unsigned() && ms.get<unsigned long long>() >
                     static_cast<unsigned long long>(std::numeric_limits<long long>::max()))) {
                    throw Error{code::CfgBad, key + "[" + name + "].stuck_after_ms must be a positive integer within signed 64-bit range"};
                }
            }
            fix_path(r.value, name, key, "ws", "workspace");
            fix_path(r.value, name, key, "stack", "stack");
            fix_path(r.value, name, key, "def", "definition directory");   // 11-04（aos-agent，使用者「那就b。」）：只記、不驗在不在
            for (const char* k : {"auto_restart", "restart_on_stuck"}) {
                if (!r.value.contains(k)) {
                    continue;
                }
                if (r.value[k].is_null()) {
                    r.value.erase(k);
                } else if (!r.value[k].is_boolean()) {
                    throw Error{code::CfgBad, key + "[" + name + "]." + k + " must be a boolean or null"};
                }
            }
            if (r.value.contains("limits")) {   // 11-05（feat-proto 件 5）：份額；null＝當沒寫（用 daemon 的預設）、{}＝不限，壞＝同 stack
                if (r.value["limits"].is_null()) {
                    r.value.erase("limits");
                } else {
                    check_limits(r.value["limits"], key + "[" + name + "].limits");
                }
            }
            if (is_once(r.value) && !is_target(r.value["exec"]) && !r.value["exec"].is_object()) {   // exec 型的物件（procs § 2 第 2 條）
                throw Error{code::CfgBad, key + "[" + name + "]" + bad_target};
            }
            vec.emplace_back(name, std::move(r.value));   // loop 設定：daemon 認的格以外不驗，交給子 loop
        } else {
            throw Error{code::CfgBad, key + "[" + name + "]" + bad_target};
        }
    }
    return out;
}

const Json& merge_want(const Json& base, const Json& ctl, const char* added_key, const char* removed_key, Json& merged) {
    if (!ctl.contains(added_key) && !ctl.contains(removed_key)) {
        return base;
    }
    std::unordered_map<std::string, const Json*> added;
    if (ctl.contains(added_key)) {
        for (auto& [n, spec] : ctl[added_key].items()) {
            added[n] = &spec;
        }
    }
    std::unordered_set<std::string> removed;
    if (ctl.contains(removed_key)) {
        for (const Json& n : ctl[removed_key]) {
            removed.insert(n.get<std::string>());
        }
    }
    merged = Json::object();   // 名字不重複，直接接在尾巴（ordered_json 的 [] 逐個比對，N 個就 N×N）
    auto& vec = static_cast<std::vector<std::pair<const std::string, Json>>&>(merged.get_ref<Json::object_t&>());
    for (auto& [n, spec] : base.items()) {
        if (removed.count(n) == 0) {   // 先加後減：同一個名字兩邊都寫＝不要
            auto a = added.find(n);    // 已在名單上的：設定換成 added 的（已在跑的不看設定變了沒，同 N-54）
            vec.emplace_back(n, a == added.end() ? spec : *a->second);
            if (a != added.end()) {
                added.erase(a);
            }
        }
    }
    if (ctl.contains(added_key)) {
        for (auto& [n, spec] : ctl[added_key].items()) {
            if (added.count(n) > 0 && removed.count(n) == 0) {   // 名單上本來沒有的：接在後面
                vec.emplace_back(n, spec);
            }
        }
    }
    return merged;
}


}  // namespace aos::daemon
