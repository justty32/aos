// limits.cpp：【child】proc 的份額 limits（說明見 limits.hpp；11-05 feat-proto 件 5，等同 s6-softlimit／s6-setuidgid）。
#include "child/limits.hpp"

#include "aos/util/files.hpp"

#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>

#include <grp.h>
#include <sys/resource.h>
#include <unistd.h>

namespace aos::daemon {

namespace {

struct Key {
    const char* name;
    int resource;
    int resource2;   // mem_mb 同時設 RLIMIT_DATA；其他 -1
    bool mb;         // 值是 MB（換成位元組）
};

const Key KEYS[] = {
    {"mem_mb", RLIMIT_AS, RLIMIT_DATA, true},
    {"cpu_s", RLIMIT_CPU, -1, false},
    {"procs", RLIMIT_NPROC, -1, false},
    {"file_mb", RLIMIT_FSIZE, -1, true},
    {"files", RLIMIT_NOFILE, -1, false},
    {"mem_total_mb", -1, -1, true},
    {"procs_total", -1, -1, false},
};

const long long MB_MAX = 0x7fffffffffffffffLL >> 20;   // 換成位元組不溢位

// /etc/passwd、/etc/group 用 etc_rows（subuid.cpp）讀。不用 getpwnam／getgrouplist：aos-daemon 是靜態連結的，glibc 的 NSS 在靜態程式裡
// 要執行時載同版本的共享庫，實測查不到的名字會把整台 daemon 弄成 SIGSEGV。所以只認本機兩份檔裡的帳號（LDAP 之類的不認）。
bool is_id(const std::string& s) {
    return !s.empty() && s.find_first_not_of("0123456789") == std::string::npos;
}

}  // namespace

void check_limits(const Json& v, const std::string& where) {
    if (v.is_null()) {
        return;
    }
    if (!v.is_object()) {
        throw Error{code::CfgBad, where + " must be an object {mem_mb, cpu_s, procs, file_mb, files, mem_total_mb, procs_total: positive integers; user: a string}"};
    }
    for (auto& [k, x] : v.items()) {
        if (k == "user") {
            if (!x.is_string() || x.get<std::string>().empty()) {
                throw Error{code::CfgBad, where + ".user must be a user name or sub:N (non-empty string)"};
            }
            if (is_sub(x.get<std::string>()) && sub_number(x.get<std::string>()) == 0) {
                throw Error{code::CfgBad, where + ".user " + aos::dumps(x) + ": sub:N needs N from 1 to 60000 (no leading zero)"};
            }
            continue;
        }
        const Key* key = nullptr;
        for (const Key& c : KEYS) {
            if (k == c.name) {
                key = &c;
            }
        }
        if (key == nullptr) {
            throw Error{code::CfgBad, where + ": unknown key " + aos::dumps(Json(k)) + " (known: mem_mb, cpu_s, procs, file_mb, files, mem_total_mb, procs_total, user)"};
        }
        bool ok = x.is_number_unsigned() ? x.get<unsigned long long>() > 0 && x.get<unsigned long long>() <= 0x7fffffffffffffffULL
                                         : x.is_number_integer() && x.get<long long>() > 0;
        if (ok && key->mb && x.get<long long>() > MB_MAX) {
            ok = false;
        }
        if (!ok) {
            throw Error{code::CfgBad, where + "." + k + " must be a positive integer"};
        }
    }
}

void check_limits_max(const Json& lim, const Json& max) {
    if (max.is_null() || max.empty()) {
        return;
    }
    for (const Key& c : KEYS) {
        if (!max.contains(c.name)) {
            continue;
        }
        std::string ceiling = aos::dumps(max[c.name]);
        if (!lim.is_object() || !lim.contains(c.name)) {
            throw Error{code::LimitBad, std::string(c.name) + " unlimited exceeds limits_max " + ceiling};
        }
        if (lim[c.name].get<long long>() > max[c.name].get<long long>()) {
            throw Error{code::LimitBad, std::string(c.name) + " " + aos::dumps(lim[c.name]) + " exceeds limits_max " + ceiling};
        }
    }
}

Limits prep_limits(const Json& limits, bool& procs_warned) {
    Limits out;
    if (!limits.is_object()) {
        return out;
    }
    for (const Key& c : KEYS) {
        if (c.resource < 0 || !limits.contains(c.name)) {
            continue;
        }
        long long n = limits[c.name].get<long long>();
        unsigned long long val = c.mb ? (unsigned long long)n << 20 : (unsigned long long)n;
        for (int resource : {c.resource, c.resource2}) {
            if (resource < 0) {
                continue;
            }
            struct rlimit inherited;
            bool finite = getrlimit(resource, &inherited) == 0 && inherited.rlim_max != RLIM_INFINITY;
            if (finite && val > inherited.rlim_max) {
                unsigned long long shown = c.mb ? (unsigned long long)inherited.rlim_max >> 20 : inherited.rlim_max;
                throw Error{code::LimitBad, std::string(c.name) + " " + std::to_string(n) +
                            " exceeds the daemon's own hard limit " + std::to_string(shown)};
            }
            unsigned long long hard = resource == RLIMIT_CPU ? val + 1 : val;
            if (finite && hard > inherited.rlim_max) {
                hard = val;
            }
            out.rl.push_back({resource, val, hard, c.name, n});
        }
    }
    if (limits.contains("procs") && !limits.contains("user") && !procs_warned) {
        std::fprintf(stderr, "aos-daemon: warning: procs %lld counts every process of uid %lu, not only this proc (no user switch)\n",
                     limits["procs"].get<long long>(), (unsigned long)getuid());
        procs_warned = true;
    }
    if (limits.contains("user")) {   // 子行程裡不查（要讀檔、配置）：fork 之前查好（同 s6-setuidgid：uid、主群組、附加群組）
        out.has_user = true;
        out.user = limits["user"].get<std::string>();
        if (is_sub(out.user)) {   // 免 root 換成 subuid（線 subuid-1119）：查號碼段與 helper，做不到丟 LimitBad（父行程預檢，單列 stopped）
            prep_sub(out.sub, out.user);
            out.user_found = true;
            return out;
        }
        for (const auto& f : etc_rows("/etc/passwd")) {
            if (f.size() >= 4 && f[0] == out.user && is_id(f[2]) && is_id(f[3])) {
                out.user_found = true;
                out.uid = (uid_t)std::strtoul(f[2].c_str(), nullptr, 10);
                out.gid = (gid_t)std::strtoul(f[3].c_str(), nullptr, 10);
                break;
            }
        }
        if (out.user_found) {
            out.groups.push_back(out.gid);
            for (const auto& f : etc_rows("/etc/group")) {
                if (f.size() < 4 || !is_id(f[2])) {
                    continue;
                }
                std::string m = "," + f[3] + ",";
                gid_t g = (gid_t)std::strtoul(f[2].c_str(), nullptr, 10);
                if (m.find("," + out.user + ",") != std::string::npos && g != out.gid) {
                    out.groups.push_back(g);
                }
            }
        }
    }
    return out;
}

void apply_limits(const Limits& lim) {
    for (const Limits::Rl& r : lim.rl) {   // 先 setrlimit 再換身分（同 s6-softlimit … s6-setuidgid 的順序）
        if (r.resource < 0) {
            continue;
        }
        struct rlimit rl;
        rl.rlim_cur = (rlim_t)r.value;
        rl.rlim_max = (rlim_t)r.hard;
        if (setrlimit(r.resource, &rl) != 0) {
            int e = errno;
            if (e == EPERM) {   // 比 daemon 自己的 hard 寬：hard 只能降不能升（不自動夾成 daemon 的，C-56）
                std::fprintf(stderr, "aos-daemon: error: %s %s %lld exceeds the daemon's own hard limit\n", code::LimitBad, r.key, r.shown);
            } else {
                std::fprintf(stderr, "aos-daemon: error: %s %s %lld %s\n", code::LimitBad, r.key, r.shown, std::strerror(e));
            }
            std::fflush(stderr);
            _exit(1);
        }
    }
    if (!lim.has_user || lim.sub.n != 0) {   // sub:N 由 run_child 接著呼叫 enter_sub（要跟父行程對號碼）
        return;
    }
    if (!lim.user_found) {
        std::fprintf(stderr, "aos-daemon: error: %s user %s: no such user\n", code::LimitBad, lim.user.c_str());
        std::fflush(stderr);
        _exit(1);
    }
    if (setgroups(lim.groups.size(), lim.groups.data()) != 0 || setgid(lim.gid) != 0 || setuid(lim.uid) != 0) {
        int e = errno;
        std::fprintf(stderr, "aos-daemon: error: %s user %s: %s%s\n", code::LimitBad, lim.user.c_str(), std::strerror(e),
                     e == EPERM ? " (switching users needs the daemon to run as root)" : "");
        std::fflush(stderr);
        _exit(1);
    }
}

}  // namespace aos::daemon
