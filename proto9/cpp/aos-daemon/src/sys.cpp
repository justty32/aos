// sys.cpp：系統小工具——讀 mountinfo、時間與訊號名、拋棄式小行程（碰底下 proc 的檔只在這裡做）、起底下的 proc。
#include "daemon.hpp"

#include <cerrno>
#include <csignal>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <fcntl.h>
#include <fstream>
#include <sstream>
#include <unistd.h>

extern char** environ;

namespace aosd {

namespace {

// mountinfo 把空白、tab、換行、反斜線寫成 \040 這種八進位
std::string unescape(const std::string& s) {
    std::string out;
    for (size_t i = 0; i < s.size(); ++i) {
        if (s[i] == '\\' && i + 3 < s.size() && s[i + 1] >= '0' && s[i + 1] <= '3') {
            out += static_cast<char>((s[i + 1] - '0') * 64 + (s[i + 2] - '0') * 8 + (s[i + 3] - '0'));
            i += 3;
        } else {
            out += s[i];
        }
    }
    return out;
}

// 小行程的讀緩衝放全域：fork 之後不能配置記憶體
char g_buf[65536];

// fork 之後只准用 async-signal-safe 的呼叫
void put_errno(int fd, int e) {
    char b[16];
    int n = 0;
    b[n++] = 'E';
    char d[12];
    int k = 0;
    do {
        d[k++] = static_cast<char>('0' + e % 10);
        e /= 10;
    } while (e && k < 11);
    while (k) b[n++] = d[--k];
    if (write(fd, b, static_cast<size_t>(n)) < 0) {}
}

}  // namespace

std::vector<MountEntry> read_mountinfo() {
    std::vector<MountEntry> out;
    std::ifstream in("/proc/self/mountinfo");
    for (std::string line; std::getline(in, line);) {
        // id parent major:minor root point opts [optional...] - fstype source superopts
        std::istringstream ls(line);
        std::string f;
        MountEntry e;
        for (int i = 0; i < 5 && ls >> f; ++i)
            if (i == 4) e.point = unescape(f);
        while (ls >> f && f != "-") {}
        ls >> e.fstype >> e.source;
        e.source = unescape(e.source);
        out.push_back(std::move(e));
    }
    return out;
}

std::string mount_of_pid(pid_t pid) {
    std::string tail = ":" + std::to_string(pid), hit;
    for (const auto& e : read_mountinfo())
        if (e.fstype == "fuse.aosproc" && e.source.size() > tail.size() &&
            e.source.compare(e.source.size() - tail.size(), tail.size(), tail) == 0)
            hit = e.point;
    return hit;
}

std::string kv_get(const std::string& text, const std::string& name) {
    std::string key = name + ": ";
    size_t at = text.rfind("\n" + key);
    size_t b = text.compare(0, key.size(), key) == 0 ? 0 : (at == std::string::npos ? at : at + 1);
    if (b == std::string::npos) return "-";
    b += key.size();
    std::string v = text.substr(b, text.find('\n', b) - b);
    return v.empty() ? "-" : v;
}

std::string now_iso() {
    time_t t = time(nullptr);
    tm lt;
    localtime_r(&t, &lt);
    char buf[40];
    strftime(buf, sizeof buf, "%Y-%m-%dT%H:%M:%S%z", &lt);
    std::string s = buf;
    if (s.size() >= 5) s.insert(s.size() - 2, ":");
    return s;
}

std::string signal_name(int sig) {
    const char* n = sigabbrev_np(sig);
    return n ? std::string("SIG") + n : std::to_string(sig);
}

HelperStart start_helper(const std::string& path, bool wr, const std::string& data) {
    int p[2];
    if (pipe2(p, O_CLOEXEC) != 0) return {};
    const char* cpath = path.c_str();
    const char* cdata = data.data();
    size_t clen = data.size();
    pid_t pid = fork();
    if (pid == 0) {
        // 只留管子（搬到 3），其餘 fd 全關：卡在這裡的小行程不該攥著 daemon 自己的 /dev/fuse
        if (p[1] != 3) dup2(p[1], 3);
        close_range(4, ~0U, 0);
        // 不站在 daemon 自己的掛載點裡，免得卡住的小行程擋住 daemon 卸載
        if (chdir("/") != 0) _exit(1);
        int fd = open(cpath, wr ? O_WRONLY : O_RDONLY);
        if (fd < 0) {
            put_errno(3, errno);
            _exit(0);
        }
        if (wr) {
            if (write(fd, cdata, clen) < 0 || close(fd) != 0) {
                put_errno(3, errno);
                _exit(0);
            }
            if (write(3, "O-", 2) < 0) {}
            _exit(0);
        }
        size_t n = 0;
        for (;;) {
            ssize_t r = read(fd, g_buf + n, sizeof g_buf - n);
            if (r < 0 && errno == EINTR) continue;
            if (r < 0) {
                put_errno(3, errno);
                _exit(0);
            }
            if (r == 0 || (n += static_cast<size_t>(r)) == sizeof g_buf) break;
        }
        char head[2] = {'O', access(cpath, X_OK) == 0 ? 'x' : '-'};
        if (write(3, head, 2) < 0) {}
        for (size_t off = 0; off < n;) {
            ssize_t w = write(3, g_buf + off, n - off);
            if (w <= 0) break;
            off += static_cast<size_t>(w);
        }
        _exit(0);
    }
    close(p[1]);
    if (pid < 0) {
        close(p[0]);
        return {};
    }
    fcntl(p[0], F_SETFL, O_NONBLOCK);
    return {pid, p[0]};
}

std::string find_in_path(const std::string& prog) {
    if (prog.find('/') != std::string::npos) return prog;
    const char* path = std::getenv("PATH");
    std::istringstream in(path ? path : "/usr/bin:/bin");
    for (std::string dir; std::getline(in, dir, ':');) {
        std::string p = (dir.empty() ? "." : dir) + "/" + prog;
        if (access(p.c_str(), X_OK) == 0) return p;
    }
    return prog;
}

pid_t spawn(const std::vector<std::string>& argv_in, const std::vector<std::string>& extra_env, std::string& err) {
    // fork 之前把 argv／envp 全部備好：fork 之後只准做 async-signal-safe 的事
    std::vector<std::string> args = argv_in;
    args[0] = find_in_path(args[0]);
    std::vector<std::string> envs;
    auto key = [](const std::string& kv) { return kv.substr(0, kv.find('=')); };
    for (char** e = environ; e && *e; ++e) {
        std::string kv = *e, k = key(kv);
        bool over = false;
        for (const auto& x : extra_env) over = over || key(x) == k;
        if (!over) envs.push_back(kv);
    }
    for (const auto& x : extra_env) envs.push_back(x);
    std::vector<char*> av, ev;
    for (auto& s : args) av.push_back(s.data());
    av.push_back(nullptr);
    for (auto& s : envs) ev.push_back(s.data());
    ev.push_back(nullptr);
    int devnull = open("/dev/null", O_RDONLY | O_CLOEXEC);
    sigset_t none;
    sigemptyset(&none);
    struct sigaction dfl {};
    dfl.sa_handler = SIG_DFL;

    pid_t pid = fork();
    if (pid == 0) {
        // 自己一個行程組：殼對 daemon 按 Ctrl-C 時，底下的不會被一起打到，由 daemon 好好收
        setpgid(0, 0);
        if (chdir("/") != 0) _exit(127);
        if (devnull >= 0) dup2(devnull, 0);
        dup2(2, 1);   // daemon 的 stdout 只留給自己的那行 export
        close_range(3, ~0U, 0);
        // daemon 把這些訊號擋給 signalfd 收；擋著的遮罩會跨過 exec，要還原
        sigprocmask(SIG_SETMASK, &none, nullptr);
        sigaction(SIGPIPE, &dfl, nullptr);
        execve(av[0], av.data(), ev.data());
        _exit(127);
    }
    if (devnull >= 0) close(devnull);
    if (pid < 0) err = std::string("ForkFailed ") + std::strerror(errno);
    return pid;
}

}  // namespace aosd
