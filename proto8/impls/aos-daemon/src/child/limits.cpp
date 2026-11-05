// limits.cpp：【child】proc 的份額 limits（說明見 limits.hpp；11-05 feat-proto 件 5，等同 s6-softlimit／s6-setuidgid）。
#include "child/limits.hpp"

#include "aos/files.hpp"

#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <sstream>

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
};

const long long MB_MAX = 0x7fffffffffffffffLL >> 20;   // 換成位元組不溢位

// /etc/passwd、/etc/group 一行一行（name:x:id:…）。不用 getpwnam／getgrouplist：aos-daemon 是靜態連結的，glibc 的 NSS 在靜態程式裡
// 要執行時載同版本的共享庫，實測查不到的名字會把整台 daemon 弄成 SIGSEGV。所以只認本機兩份檔裡的帳號（LDAP 之類的不認）。
std::vector<std::vector<std::string>> rows_of(const char* path) {
    std::vector<std::vector<std::string>> out;
    int err = 0;
    std::optional<std::string> text = aos::read_file(path, err);
    if (!text) {
        return out;
    }
    std::istringstream in(*text);
    std::string line;
    while (std::getline(in, line)) {
        std::vector<std::string> f;
        size_t i = 0;
        while (true) {
            size_t j = line.find(':', i);
            f.push_back(line.substr(i, j == std::string::npos ? std::string::npos : j - i));
            if (j == std::string::npos) {
                break;
            }
            i = j + 1;
        }
        out.push_back(std::move(f));
    }
    return out;
}

bool is_id(const std::string& s) {
    return !s.empty() && s.find_first_not_of("0123456789") == std::string::npos;
}

}  // namespace

void check_limits(const Json& v, const std::string& where) {
    if (v.is_null()) {
        return;
    }
    if (!v.is_object()) {
        throw Error{code::CfgBad, where + " must be an object {mem_mb, cpu_s, procs, file_mb, files: positive integers; user: a string}"};
    }
    for (auto& [k, x] : v.items()) {
        if (k == "user") {
            if (!x.is_string() || x.get<std::string>().empty()) {
                throw Error{code::CfgBad, where + ".user must be a user name (non-empty string)"};
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
            throw Error{code::CfgBad, where + ": unknown key " + aos::dumps(Json(k)) + " (known: mem_mb, cpu_s, procs, file_mb, files, user)"};
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

Limits prep_limits(const Json& limits) {
    Limits out;
    if (!limits.is_object()) {
        return out;
    }
    for (const Key& c : KEYS) {
        if (!limits.contains(c.name)) {
            continue;
        }
        long long n = limits[c.name].get<long long>();
        unsigned long long val = c.mb ? (unsigned long long)n << 20 : (unsigned long long)n;
        out.rl.push_back({c.resource, val, c.name, n});
        if (c.resource2 >= 0) {
            out.rl.push_back({c.resource2, val, c.name, n});
        }
    }
    if (limits.contains("user")) {   // 子行程裡不查（要讀檔、配置）：fork 之前查好（同 s6-setuidgid：uid、主群組、附加群組）
        out.has_user = true;
        out.user = limits["user"].get<std::string>();
        for (const auto& f : rows_of("/etc/passwd")) {
            if (f.size() >= 4 && f[0] == out.user && is_id(f[2]) && is_id(f[3])) {
                out.user_found = true;
                out.uid = (uid_t)std::strtoul(f[2].c_str(), nullptr, 10);
                out.gid = (gid_t)std::strtoul(f[3].c_str(), nullptr, 10);
                break;
            }
        }
        if (out.user_found) {
            out.groups.push_back(out.gid);
            for (const auto& f : rows_of("/etc/group")) {
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
        struct rlimit rl;
        rl.rlim_cur = (rlim_t)r.value;
        rl.rlim_max = (rlim_t)r.value;
        if (setrlimit(r.resource, &rl) != 0) {
            int e = errno;
            if (e == EPERM) {   // 比 daemon 自己的 hard 寬：hard 只能降不能升（不自動夾成 daemon 的，C-56）
                std::fprintf(stderr, "aos-daemon: %s %s %lld exceeds the daemon's own hard limit\n", code::LimitBad, r.key, r.shown);
            } else {
                std::fprintf(stderr, "aos-daemon: %s %s %lld %s\n", code::LimitBad, r.key, r.shown, std::strerror(e));
            }
            std::fflush(stderr);
            _exit(1);
        }
    }
    if (!lim.has_user) {
        return;
    }
    if (!lim.user_found) {
        std::fprintf(stderr, "aos-daemon: %s user %s: no such user\n", code::LimitBad, lim.user.c_str());
        std::fflush(stderr);
        _exit(1);
    }
    if (setgroups(lim.groups.size(), lim.groups.data()) != 0 || setgid(lim.gid) != 0 || setuid(lim.uid) != 0) {
        int e = errno;
        std::fprintf(stderr, "aos-daemon: %s user %s: %s%s\n", code::LimitBad, lim.user.c_str(), std::strerror(e),
                     e == EPERM ? " (switching users needs the daemon to run as root)" : "");
        std::fflush(stderr);
        _exit(1);
    }
}

}  // namespace aos::daemon
