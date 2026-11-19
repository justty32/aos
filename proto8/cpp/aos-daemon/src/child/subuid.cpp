// subuid.cpp：【child】免 root 把 proc 換成 subuid（說明見 subuid.hpp；線 subuid-1119，kernel-limits-plan 段 3 的最小一刀）。
#include "child/subuid.hpp"

#include "common/common.hpp"

#include "aos/util/files.hpp"
#include "aos/util/signals.hpp"

#include <cerrno>
#include <climits>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <sstream>

#include <fcntl.h>
#include <grp.h>
#include <sched.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <sys/xattr.h>
#include <unistd.h>

extern char** environ;

namespace aos::daemon {

namespace {

int the_group = SUB_GROUP_MIN;

const char* const ENV_BASE[] = {"PATH", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "TERM", "PYTHONDONTWRITEBYTECODE", "PYTHONIOENCODING"};

bool is_id(const std::string& s) {
    return !s.empty() && s.size() <= 10 && s.find_first_not_of("0123456789") == std::string::npos;
}

// 這個帳號在 /etc/subuid（或 subgid）的第一段：起點、個數。沒有＝丟 LimitBad。
void sub_range(const char* path, const std::string& who, unsigned long long& start, unsigned long long& count) {
    std::string name;
    for (const auto& f : etc_rows("/etc/passwd")) {
        if (f.size() >= 3 && f[2] == std::to_string(getuid())) {
            name = f[0];
            break;
        }
    }
    for (const auto& f : etc_rows(path)) {
        if (f.empty() || (f[0] != name && f[0] != std::to_string(getuid()))) {
            continue;
        }
        if (f.size() != 3 || !is_id(f[1]) || !is_id(f[2])) {
            throw Error{code::LimitBad, "user " + who + ": invalid line for this user in " + path};
        }
        start = std::strtoull(f[1].c_str(), nullptr, 10);
        count = std::strtoull(f[2].c_str(), nullptr, 10);
        return;
    }
    throw Error{code::LimitBad, "user " + who + ": no line for " + (name.empty() ? std::to_string(getuid()) : name) + " in " + path};
}

// PATH 上找得到、可執行的第一個；沒有＝空。
std::string on_path(const char* prog) {
    const char* p = std::getenv("PATH");
    std::string path = p == nullptr ? "" : p;
    size_t i = 0;
    while (i <= path.size()) {
        size_t j = path.find(':', i);
        std::string dir = path.substr(i, j == std::string::npos ? std::string::npos : j - i);
        if (!dir.empty() && dir[0] == '/') {
            std::string full = dir + "/" + prog;
            if (access(full.c_str(), X_OK) == 0) {
                return full;
            }
        }
        if (j == std::string::npos) {
            break;
        }
        i = j + 1;
    }
    return "";
}

// POSIX ACL 的 xattr 格式（linux/posix_acl_xattr.h）：版本 2，之後每筆 {tag u16, perm u16, id u32}，照 tag、id 排好。
enum : unsigned short { ACL_USER_OBJ = 0x01, ACL_USER = 0x02, ACL_GROUP_OBJ = 0x04, ACL_MASK = 0x10, ACL_OTHER = 0x20 };
const unsigned int ACL_UNDEFINED_ID = 0xffffffffu;

std::string acl_bytes(const std::vector<std::pair<unsigned short, unsigned int>>& users) {
    std::string out;
    auto put32 = [&](unsigned int v) { out.append(reinterpret_cast<const char*>(&v), 4); };
    auto entry = [&](unsigned short tag, unsigned short perm, unsigned int id) {
        out.append(reinterpret_cast<const char*>(&tag), 2);
        out.append(reinterpret_cast<const char*>(&perm), 2);
        put32(id);
    };
    put32(2);
    entry(ACL_USER_OBJ, 7, ACL_UNDEFINED_ID);
    for (const auto& [perm, id] : users) {
        entry(ACL_USER, perm, id);
    }
    entry(ACL_GROUP_OBJ, 0, ACL_UNDEFINED_ID);
    entry(ACL_MASK, 7, ACL_UNDEFINED_ID);
    entry(ACL_OTHER, 0, ACL_UNDEFINED_ID);
    return out;
}

// 子行程裡的錯誤行（不配置記憶體）。
[[noreturn]] void die(int n, const char* what, int e) {
    std::fprintf(stderr, "aos-daemon: error: %s user sub:%d: %s: %s\n", code::LimitBad, n, what, std::strerror(e));
    std::fflush(stderr);
    _exit(1);
}

// 跑一支 helper（newuidmap／newgidmap）：stdin、stdout 接 /dev/null，stderr 接小格的 stderr.txt。成功＝true；不然 why 寫原因。
bool run_helper(const std::string& prog, pid_t pid, const std::vector<std::string>& args, int err_fd, std::string& why) {
    std::vector<std::string> words{prog, std::to_string(pid)};
    words.insert(words.end(), args.begin(), args.end());
    std::vector<char*> argv;
    for (std::string& w : words) {
        argv.push_back(w.data());
    }
    argv.push_back(nullptr);
    pid_t h = fork();
    if (h < 0) {
        why = prog + ": fork failed (" + std::strerror(errno) + ")";
        return false;
    }
    if (h == 0) {
        aos::restore_signals();
        int null_fd = open("/dev/null", O_RDWR);
        if (null_fd >= 0) {
            dup2(null_fd, 0);
            dup2(null_fd, 1);
        }
        dup2(err_fd, 2);
        execv(argv[0], argv.data());
        _exit(127);
    }
    int status = 0;
    while (waitpid(h, &status, 0) < 0) {
        if (errno != EINTR) {
            why = prog + ": wait failed (" + std::strerror(errno) + ")";
            return false;
        }
    }
    if (WIFEXITED(status) && WEXITSTATUS(status) == 0) {
        return true;
    }
    why = prog + (WIFEXITED(status) ? " exited " + std::to_string(WEXITSTATUS(status)) : " was killed by signal " + std::to_string(WTERMSIG(status)));
    return false;
}

}  // namespace

std::vector<std::vector<std::string>> etc_rows(const char* path) {
    std::vector<std::vector<std::string>> out;
    int err = 0;
    std::optional<std::string> text = aos::read_file(path, err);
    if (!text) {
        return out;
    }
    std::istringstream in(*text);
    std::string line;
    while (std::getline(in, line)) {
        if (line.empty() || line[0] == '#') {
            continue;
        }
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

int sub_number(const std::string& user) {
    if (!is_sub(user)) {
        return 0;
    }
    std::string d = user.substr(4);
    if (d.empty() || d.size() > 5 || d[0] == '0' || d.find_first_not_of("0123456789") != std::string::npos) {
        return 0;
    }
    int n = std::atoi(d.c_str());
    return n <= 60000 ? n : 0;
}

void set_sub_group(int group) {
    the_group = group;
}

int sub_group() {
    return the_group;
}

void prep_sub(Sub& s, const std::string& user) {
    s.n = sub_number(user);
    s.group = the_group;
    unsigned long long ustart = 0, ucount = 0, gstart = 0, gcount = 0;
    sub_range("/etc/subuid", user, ustart, ucount);
    sub_range("/etc/subgid", user, gstart, gcount);
    if ((unsigned long long)s.n > ucount) {
        throw Error{code::LimitBad, "user " + user + ": exceeds this user's subuid range (" + std::to_string(ucount) + " ids)"};
    }
    if ((unsigned long long)s.group > gcount) {
        throw Error{code::LimitBad, "user " + user + ": group " + std::to_string(s.group) + " exceeds this user's subgid range (" +
                    std::to_string(gcount) + " ids)"};
    }
    s.uidmap = on_path("newuidmap");
    s.gidmap = on_path("newgidmap");
    for (const auto& [prog, found] : {std::pair<const char*, const std::string*>{"newuidmap", &s.uidmap}, {"newgidmap", &s.gidmap}}) {
        if (found->empty()) {
            throw Error{code::LimitBad, "user " + user + ": " + prog + " not found on PATH (install the uidmap package)"};
        }
    }
    s.uid = (uid_t)(ustart + s.n - 1);
    s.gid = (gid_t)(gstart + s.group - 1);
    s.uid_args = {"0", std::to_string(getuid()), "1", std::to_string(s.n), std::to_string(s.uid), "1"};
    s.gid_args = {"0", std::to_string(getgid()), "1", std::to_string(s.group), std::to_string(s.gid), "1"};
}

void finish_sub(Sub& s, const std::string& cell, const std::string& cwd, const std::string& ws) {
    s.env.clear();
    for (char** e = environ; e != nullptr && *e != nullptr; ++e) {
        std::string kv = *e;
        std::string key = kv.substr(0, kv.find('='));
        bool keep = key.rfind("AOS_", 0) == 0;
        for (const char* base : ENV_BASE) {
            keep = keep || key == base;
        }
        if (keep) {
            s.env.push_back(kv);
        }
    }
    s.env.push_back("HOME=/nonexistent");
    if (!ws.empty()) {   // 換了 uid 的 proc 在使用者的 repo 裡跑 git 會撞 dubious ownership（08 G8、X27）
        s.env.push_back("GIT_CONFIG_COUNT=1");
        s.env.push_back("GIT_CONFIG_KEY_0=safe.directory");
        s.env.push_back("GIT_CONFIG_VALUE_0=" + ws);
    }
    s.reach = {{cell, R_OK | W_OK | X_OK}, {cwd, X_OK}};
    if (!ws.empty()) {
        s.reach.push_back({ws, X_OK});
    }
}

void grant_cell(const Sub& s, const std::string& cell) {
    std::string who = "user sub:" + std::to_string(s.n) + ": cannot set the ACL of " + cell + ": ";
    if (chmod(cell.c_str(), 0700) != 0) {
        throw Error{code::LimitBad, who + std::strerror(errno)};
    }
    unsigned int me = (unsigned int)getuid();
    unsigned int sub = (unsigned int)s.uid;
    std::string access_acl = acl_bytes({{7, sub}});
    std::string default_acl = acl_bytes(me < sub ? std::vector<std::pair<unsigned short, unsigned int>>{{7, me}, {7, sub}}
                                                 : std::vector<std::pair<unsigned short, unsigned int>>{{7, sub}, {7, me}});
    if (setxattr(cell.c_str(), "system.posix_acl_access", access_acl.data(), access_acl.size(), 0) != 0 ||
        setxattr(cell.c_str(), "system.posix_acl_default", default_acl.data(), default_acl.size(), 0) != 0) {
        throw Error{code::LimitBad, who + std::strerror(errno)};
    }
}

void map_sub(const Sub& s, pid_t pid, int sock, int err_fd) {
    char c = 0;
    ssize_t got;
    while ((got = recv(sock, &c, 1, 0)) < 0 && errno == EINTR) {
    }
    if (got != 1) {   // 子行程在開 ns 之前就退了（錯誤行它自己寫了）
        close(sock);
        return;
    }
    std::string why;
    bool ok = run_helper(s.uidmap, pid, s.uid_args, err_fd, why) && run_helper(s.gidmap, pid, s.gid_args, err_fd, why);
    if (!ok) {
        dprintf(err_fd, "aos-daemon: error: %s user sub:%d: %s\n", code::LimitBad, s.n, why.c_str());
    }
    c = ok ? '1' : '0';
    while (send(sock, &c, 1, MSG_NOSIGNAL) < 0 && errno == EINTR) {
    }
    close(sock);
}

void open_sub_ns(const Sub& s, int sock) {
    if (unshare(CLONE_NEWUSER) != 0) {
        die(s.n, "unshare", errno);
    }
    char c = '1';
    while (send(sock, &c, 1, MSG_NOSIGNAL) < 0) {
        if (errno != EINTR) {
            die(s.n, "socket", errno);
        }
    }
    ssize_t got;
    c = 0;
    while ((got = recv(sock, &c, 1, 0)) < 0 && errno == EINTR) {
    }
    close(sock);
    if (got != 1 || c != '1') {
        std::fflush(stderr);
        _exit(1);   // 父行程已寫了原因
    }
}

void become_sub(const Sub& s, char** envp) {
    if (setgroups(0, nullptr) != 0) {
        die(s.n, "setgroups", errno);
    }
    if (setresgid(s.group, s.group, s.group) != 0) {
        die(s.n, "setresgid", errno);
    }
    if (setresuid(s.n, s.n, s.n) != 0) {
        die(s.n, "setresuid", errno);
    }
    environ = envp;
    if (close_range(3, ~0U, 0) != 0) {
        for (long fd = 3, top = sysconf(_SC_OPEN_MAX); fd < top; ++fd) {
            close((int)fd);
        }
    }
    // 換了身分才看得準（ACL、祖先的 x 都算進去）：先看整條路，不行再一層層找第一個走不進去的（04 第 1、2 條：家目錄 700 最常見）
    for (const auto& [path, mode] : s.reach) {
        if (access(path.c_str(), mode) == 0) {
            continue;
        }
        int e = errno;
        char buf[PATH_MAX];
        std::snprintf(buf, sizeof buf, "%s", path.c_str());
        for (char* p = buf + 1; *p != '\0'; ++p) {
            if (*p != '/') {
                continue;
            }
            *p = '\0';
            bool walk = access(buf, X_OK) == 0;
            int we = errno;
            if (!walk) {
                std::fprintf(stderr, "aos-daemon: error: %s user sub:%d: cannot reach %s: %s\n", code::LimitBad, s.n, buf, std::strerror(we));
                std::fflush(stderr);
                _exit(1);
            }
            *p = '/';
        }
        std::fprintf(stderr, "aos-daemon: error: %s user sub:%d: cannot reach %s: %s\n", code::LimitBad, s.n, path.c_str(), std::strerror(e));
        std::fflush(stderr);
        _exit(1);
    }
}

}  // namespace aos::daemon
