// procs.cpp：【daemon】解讀 proc 名單、辨認寫法、整理路徑與合併期望表（說明見 daemon.hpp）。
#include "daemon/daemon.hpp"
#include "child/limits.hpp"
#include "aos/util/files.hpp"
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
        if (k != "exec" && k != "ws" && k != "stack" && k != "def" && k != "limits" && k != "auto_restart" && k != "restart_on_stuck") {
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
            vec.emplace_back(name, std::move(t));
        } else if (it.value.is_object()) {
            aos::Resolved r = aos::loop::resolve_keys(it.value, it.base_dir, {"max", "interval_ms", "ctl", "state", "ws", "stack", "def", "limits", "auto_restart", "restart_on_stuck"});
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
