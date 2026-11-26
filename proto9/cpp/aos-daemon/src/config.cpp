// config.cpp：讀 start 的設定檔（json）與天空的每一行，展開成預定的掛載表。
#include "common.hpp"

#include "nlohmann/json.hpp"

#include <sstream>
#include <stdexcept>

namespace d2 {

const char* const DEV_NODES[5] = {"null", "zero", "full", "random", "urandom"};
const char* const DEFAULT_DAEMON_PATH = "/aos";

namespace {

[[noreturn]] void bad(const std::string& why) { throw std::runtime_error("ConfigBad " + why); }

// 絕對路徑、沒有 . 與 ..、沒有空的段；尾巴的 / 拿掉
std::string clean_path(const std::string& p, const std::string& what) {
    if (p.empty() || p[0] != '/') bad(what + " must be an absolute path: " + p);
    std::string out;
    std::istringstream in(p);
    for (std::string part; std::getline(in, part, '/');) {
        if (part.empty()) continue;
        if (part == "." || part == "..") bad(what + " must not contain . or ..: " + p);
        for (char c : part)
            if (c == '\n' || c == '\0') bad(what + " has a control character");
        out += "/" + part;
    }
    return out.empty() ? "/" : out;
}

// tmpfs 的大小：字串「數字＋可選的 k／m／g」（大小寫都行），或正整數（位元組）；0 拒（tmpfs 的 size=0 是不限，跟「不寫」意思不同，免得看錯）
std::string size_value(const nlohmann::json& v, const std::string& what) {
    std::string s;
    if (v.is_number_unsigned() || (v.is_number_integer() && v.get<long long>() > 0)) s = std::to_string(v.get<unsigned long long>());
    else if (v.is_string()) s = v.get<std::string>();
    else bad(what + " must be a size like \"64m\" (digits with an optional k, m or g) or a number of bytes, not " + v.dump());
    size_t n = 0;
    while (n < s.size() && isdigit(static_cast<unsigned char>(s[n]))) ++n;
    bool ok = n > 0 && n <= 18 && (n == s.size() || (n + 1 == s.size() && std::string("kmgKMG").find(s[n]) != std::string::npos));
    if (!ok) bad(what + " must be a size like \"64m\" (digits with an optional k, m or g) or a number of bytes, not " + v.dump());
    if (s.find_first_not_of("0kmgKMG") == std::string::npos)
        bad(what + " must not be 0 (leave it out for no size option)");
    return s;
}

bool name_ok(const std::string& n) {
    if (n.empty() || n.size() > 64 || n[0] == '.') return false;
    for (char c : n)
        if (!isalnum(static_cast<unsigned char>(c)) && c != '_' && c != '-' && c != '.') return false;
    return true;
}

}  // namespace

bool json_depth_ok(const std::string& text) {
    int depth = 0;
    bool in_str = false, esc = false;
    for (char c : text) {
        if (in_str) {
            if (esc) esc = false;
            else if (c == '\\') esc = true;
            else if (c == '"') in_str = false;
            continue;
        }
        if (c == '"') in_str = true;
        else if (c == '[' || c == '{') {
            if (++depth > JSON_MAX_DEPTH) return false;
        } else if (c == ']' || c == '}') {
            --depth;
        }
    }
    return true;
}

bool abs_path_ok(const std::string& p) {
    try {
        return clean_path(p, "path") == p;
    } catch (...) {
        return false;
    }
}

// 設定的 ns 每條是一個 json 物件：{"type": "bind", "src", "dst", "rw"?, "beneath"?}、{"type": "tmpfs", "dst", "size"?}、
// {"type": "proc"|"dev", "dst"}、
// {"type": "symlink", "target", "dst"}、{"type": "overlay", "lower": [...], "dst"}。不認得的鍵、缺的鍵、型別不對、不認得的 type 都拒。
NsEntry parse_ns_entry(const nlohmann::json& j) {
    if (!j.is_object()) bad("ns entry must be an object like {\"type\": \"bind\", \"src\": \"/usr\", \"dst\": \"/usr\"}, not " + j.dump());
    auto it = j.find("type");
    if (it == j.end()) bad("ns entry has no \"type\" (bind, tmpfs, proc, dev, symlink, overlay): " + j.dump());
    if (!it->is_string()) bad("ns entry \"type\" must be a string: " + j.dump());
    NsEntry e;
    e.kind = it->get<std::string>();
    std::vector<std::string> allowed{"type", "dst"};
    if (e.kind == "bind") {
        allowed.push_back("src");
        allowed.push_back("rw");
        allowed.push_back("beneath");
    } else if (e.kind == "tmpfs") {
        allowed.push_back("size");
    } else if (e.kind == "symlink") {
        allowed.push_back("target");
    } else if (e.kind == "overlay") {
        allowed.push_back("lower");
    } else if (e.kind != "proc" && e.kind != "dev") {
        bad("unknown ns entry type " + e.kind + " (bind, tmpfs, proc, dev, symlink, overlay)");
    }
    for (const auto& [k, v] : j.items()) {
        (void)v;
        bool ok = false;
        for (const auto& a : allowed) ok = ok || a == k;
        if (!ok) bad("unknown key \"" + k + "\" in ns entry of type " + e.kind + " (allowed: " + [&] {
            std::string l;
            for (const auto& a : allowed) l += (l.empty() ? "" : ", ") + a;
            return l;
        }() + ")");
    }
    auto need = [&](const char* key) {
        auto f = j.find(key);
        if (f == j.end()) bad(std::string("ns entry of type ") + e.kind + " needs \"" + key + "\": " + j.dump());
        if (!f->is_string()) bad(std::string("ns entry \"") + key + "\" must be a string: " + j.dump());
        return f->get<std::string>();
    };
    e.dst = clean_path(need("dst"), e.kind + " dst");
    if (e.kind == "bind") {
        e.src = clean_path(need("src"), "bind src");
        auto f = j.find("rw");
        if (f != j.end()) {
            if (!f->is_boolean()) bad("ns entry \"rw\" must be true or false: " + j.dump());
            e.rw = f->get<bool>();
        }
        // beneath：src 從這個夾往下開（RESOLVE_BENEATH）；src 要是它本身或它底下（照字串比，兩個都是乾淨的絕對路徑）
        if (j.find("beneath") != j.end()) {
            e.beneath = clean_path(need("beneath"), "bind beneath");
            bool inside = e.beneath == "/" || e.src == e.beneath || e.src.rfind(e.beneath + "/", 0) == 0;
            if (!inside) bad("bind src " + e.src + " is not under its \"beneath\" " + e.beneath);
        }
    } else if (e.kind == "tmpfs") {
        auto f = j.find("size");
        if (f != j.end()) e.size = size_value(*f, "tmpfs \"size\"");
    } else if (e.kind == "symlink") {
        e.src = need("target");
        if (e.src.empty()) bad("symlink \"target\" must not be empty");
    } else if (e.kind == "overlay") {
        // 唯讀的 overlay（沒有 upper）：Linux 要至少兩層 lower；起動時疊好，之後不能加層
        auto f = j.find("lower");
        if (f == j.end()) bad("ns entry of type overlay needs \"lower\" (an array of at least 2 absolute paths, top first): " + j.dump());
        if (!f->is_array() || f->size() < 2)
            bad("overlay \"lower\" must be an array of at least 2 absolute paths (a read-only overlay needs 2 layers), top first: " + j.dump());
        for (const auto& l : *f) {
            if (!l.is_string()) bad("overlay \"lower\" items must be strings: " + j.dump());
            e.lower.push_back(clean_path(l.get<std::string>(), "overlay lower"));
        }
    }
    if (e.dst == "/") bad("the root is always a fresh tmpfs; an entry with dst / is not allowed");
    return e;
}

std::vector<Mount> plan_mounts(const ProcConfig& c) {
    const std::vector<NsEntry>& ns = c.ns;
    std::vector<Mount> out{{"tmpfs", "-", "/", false}};
    out[0].size = c.root_size;
    for (const auto& e : ns) {
        if (e.kind == "bind") {
            Mount m{"bind", e.src, e.dst, e.rw};
            m.beneath = e.beneath;
            out.push_back(m);
        } else if (e.kind == "tmpfs") {
            Mount m{"tmpfs", "-", e.dst, true};
            m.size = e.size;
            out.push_back(m);
        } else if (e.kind == "proc") out.push_back({e.kind, "-", e.dst, true});
        else if (e.kind == "overlay") {
            std::string joined;
            for (const auto& l : e.lower) joined += (joined.empty() ? "" : ":") + l;
            Mount m{"overlay", joined, e.dst, false};
            m.lower = e.lower;
            out.push_back(m);
        }
        else if (e.kind == "dev") {
            out.push_back({"dev", "-", e.dst, false});
            for (const char* n : DEV_NODES) out.push_back({"bind", std::string("/dev/") + n, e.dst + "/" + n, true});
        }
    }
    return out;
}

std::string init_daemon_path(const ProcConfig& c) { return c.daemon_path.empty() ? DEFAULT_DAEMON_PATH : c.daemon_path; }

std::string init_cgroup_path(const ProcConfig& c) {
    std::string dp = init_daemon_path(c);
    std::string up = dp.substr(0, dp.rfind('/'));
    return up + "/cgroup";
}

std::string init_ns_conflict(const ProcConfig& c, bool cgroup_on) {
    std::string dp = init_daemon_path(c), cp = init_cgroup_path(c);
    auto under = [](const std::string& p, const std::string& top) { return p == top || p.rfind(top + "/", 0) == 0; };
    for (const auto& e : c.ns) {
        if (under(e.dst, dp) || (cgroup_on && under(e.dst, cp)))
            return "ConfigBad ns entry for " + e.dst + ": " + dp + (cgroup_on ? " and " + cp : std::string()) +
                   " are where the daemon puts its directory in init's ns (choose another \"daemon_path\")";
    }
    return "";
}

ProcConfig parse_config(const std::string& text, const std::string& path) {
    if (!json_depth_ok(text)) bad("nested deeper than " + std::to_string(JSON_MAX_DEPTH) + " levels of [ ] or { }");
    nlohmann::json j;
    try {
        j = nlohmann::json::parse(text);
    } catch (const std::exception& e) {
        bad(std::string("not json: ") + e.what());
    }
    if (!j.is_object()) bad("top level must be an object");
    ProcConfig c;
    c.path = path;
    auto str = [&](const nlohmann::json& v, const std::string& what) {
        if (!v.is_string()) bad(what + " must be a string");
        return v.get<std::string>();
    };
    for (const auto& [k, v] : j.items()) {
        if (k == "name") {
            c.name = str(v, "name");
            if (!name_ok(c.name)) bad("name must be 1-64 of letters, digits, _ - . and not start with .");
        } else if (k == "argv") {
            if (!v.is_array() || v.empty()) bad("argv must be a non-empty array of strings");
            for (const auto& a : v) c.argv.push_back(str(a, "argv item"));
            if (c.argv[0].empty() || c.argv[0][0] != '/') bad("argv[0] must be an absolute path inside the ns");
        } else if (k == "env") {
            if (!v.is_object()) bad("env must be an object of strings");
            for (const auto& [ek, ev] : v.items()) {
                if (ek.empty() || ek.find('=') != std::string::npos) bad("env name " + ek);
                c.env.push_back(ek + "=" + str(ev, "env value"));
            }
        } else if (k == "cwd") {
            c.cwd = clean_path(str(v, "cwd"), "cwd");
        } else if (k == "ns") {
            if (!v.is_array()) bad("ns must be an array of objects");
            for (const auto& l : v) c.ns.push_back(parse_ns_entry(l));
        } else if (k == "root_size") {
            c.root_size = size_value(v, "root_size");
        } else if (k == "uid") {
            if (!v.is_number_integer() || v.get<long long>() < 0 || v.get<long long>() > 65535)
                bad("uid must be an integer 0..65535");
            c.uid = v.get<int>();
        } else if (k == "locks") {
            if (!v.is_object()) bad("locks must be an object");
            for (const auto& [lk, lv] : v.items()) {
                if (lk == "landlock") {
                    if (lv != true) bad("locks.landlock cannot be turned off (only init runs without it, and init only when it does not ask for it)");
                    c.landlock = true;
                } else if (lk == "cgroup") {
                    if (!lv.is_object()) bad("locks.cgroup must be an object of file -> value");
                    for (const auto& [ck, cv] : lv.items()) {
                        bool ok = ck.find('/') == std::string::npos && ck.find('.') != std::string::npos &&
                                  ck.rfind("cgroup.", 0) != 0 && ck[0] != '.';
                        if (!ok) bad("locks.cgroup key " + ck + " (a limit file like memory.max; not cgroup.*)");
                        std::string val = cv.is_string() ? cv.get<std::string>() : cv.dump();
                        if (val.find('\n') != std::string::npos) bad("locks.cgroup value has a newline");
                        c.cgroup.emplace_back(ck, val);
                    }
                } else if (lk == "seccomp") {
                    // 不寫＝內建的擋單；"off"＝不上；絕對路徑＝外面的名單檔（讀檔在 load_seccomp_list）
                    if (!lv.is_string()) bad("locks.seccomp must be \"off\", \"builtin\" or an absolute path to a list file");
                    c.seccomp = lv.get<std::string>();
                    if (c.seccomp != "off" && c.seccomp != "builtin" && !abs_path_ok(c.seccomp))
                        bad("locks.seccomp must be \"off\", \"builtin\" or a clean absolute path to a list file (seen where the daemon was started), not " + c.seccomp);
                } else {
                    bad("unknown lock " + lk + " (landlock, cgroup, seccomp)");
                }
            }
        } else if (k == "daemon_access") {
            c.daemon_access = str(v, "daemon_access");
            if (c.daemon_access == "ptrace")
                bad("daemon_access \"ptrace\" was removed (11-26): init reaches the daemon's directory only where it is mounted in its ns "
                    "(\"daemon_path\", default /aos); leave \"daemon_access\" out");
            if (c.daemon_access != "mount") bad("daemon_access must be \"mount\" (the only way left; or leave it out)");
        } else if (k == "daemon_path") {
            c.daemon_path = str(v, "daemon_path");
            if (!abs_path_ok(c.daemon_path) || c.daemon_path == "/")
                bad("daemon_path must be a clean absolute path other than / (no . or .., no empty part, no trailing /): " + c.daemon_path);
            if (init_cgroup_path(c) == c.daemon_path)
                bad("daemon_path " + c.daemon_path + " is where the cgroup directory goes (dirname(daemon_path)/cgroup); choose another");
        } else if (k == "net") {
            c.net = str(v, "net");
            if (c.net != "none" && c.net != "host") bad("net must be \"none\" (own network namespace, loopback only) or \"host\"");
        } else if (k == "stdout" || k == "stderr") {
            (k == "stdout" ? c.stdout_path : c.stderr_path) = clean_path(str(v, k), k);
        } else {
            bad("unknown key " + k + " (name, argv, env, cwd, ns, root_size, uid, locks, net, stdout, stderr, daemon_access, daemon_path)");
        }
    }
    if (c.name.empty()) bad("name is missing");
    if (c.argv.empty()) bad("argv is missing");
    return c;
}

}  // namespace d2
