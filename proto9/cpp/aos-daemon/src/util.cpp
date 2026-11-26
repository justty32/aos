// util.cpp：小工具——經起動前握住的根讀外面的檔、時間字串、記錄、訊號名字。
#include "common.hpp"

#include <cerrno>
#include <csignal>
#include <cstring>
#include <ctime>
#include <fcntl.h>
#include <linux/openat2.h>
#include <sys/syscall.h>
#include <unistd.h>

namespace d2 {

World W;

std::string errstr(int e) {
    const char* d = strerrordesc_np(e);
    return d ? d : ("errno " + std::to_string(e));
}

namespace {

std::string read_all(int fd, size_t limit, bool& too_big) {
    std::string out;
    char buf[8192];
    too_big = false;
    for (;;) {
        ssize_t n = read(fd, buf, sizeof buf);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) break;
        out.append(buf, static_cast<size_t>(n));
        if (out.size() > limit) {
            too_big = true;
            break;
        }
    }
    return out;
}

}  // namespace

std::string read_host_file(const std::string& path, std::string& err) {
    err.clear();
    if (path.empty() || path[0] != '/') {
        err = "PathNotAbsolute " + path;
        return "";
    }
    // 根是起動前那一層：絕對路徑的 symlink 與 .. 都在那一層裡解（不會跑進小世界）
    open_how how{};
    how.flags = O_RDONLY | O_CLOEXEC;
    how.resolve = RESOLVE_IN_ROOT;
    std::string rel = path.substr(1).empty() ? "." : path.substr(1);
    int fd = static_cast<int>(syscall(SYS_openat2, W.rootfd, rel.c_str(), &how, sizeof how));
    if (fd < 0) {
        err = "ConfigUnreadable " + path + ": " + errstr(errno);
        return "";
    }
    bool big = false;
    std::string s = read_all(fd, 1 << 20, big);
    close(fd);
    if (big) err = "ConfigTooBig " + path + " (over 1 MiB)";
    return s;
}

std::string read_fd_at(int dirfd, const std::string& rel) {
    int fd = openat(dirfd, rel.c_str(), O_RDONLY | O_CLOEXEC);
    if (fd < 0) return "";
    bool big = false;
    std::string s = read_all(fd, 4 << 20, big);
    close(fd);
    return s;
}

std::string iso_now() {
    // gmtime_r 不讀 /etc/localtime（換根之後也沒有）
    timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    tm t;
    gmtime_r(&ts.tv_sec, &t);
    char buf[64];
    snprintf(buf, sizeof buf, "%04d-%02d-%02dT%02d:%02d:%02d.%03ldZ", t.tm_year + 1900, t.tm_mon + 1, t.tm_mday,
             t.tm_hour, t.tm_min, t.tm_sec, ts.tv_nsec / 1000000);
    return buf;
}

std::string seconds_text(double s) {
    char buf[64];
    snprintf(buf, sizeof buf, "%g", s);
    return buf;
}

double mono_now() {
    timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return static_cast<double>(ts.tv_sec) + static_cast<double>(ts.tv_nsec) / 1e9;
}

void log(const std::string& msg) {
    std::string line = "aos-daemon: " + msg + "\n";
    if (write(2, line.data(), line.size()) < 0) {}
}

namespace {
const std::pair<const char*, int> SIGS[] = {
    {"HUP", SIGHUP},   {"INT", SIGINT},   {"QUIT", SIGQUIT}, {"ILL", SIGILL},   {"TRAP", SIGTRAP},
    {"ABRT", SIGABRT}, {"BUS", SIGBUS},   {"FPE", SIGFPE},   {"KILL", SIGKILL}, {"USR1", SIGUSR1},
    {"SEGV", SIGSEGV}, {"USR2", SIGUSR2}, {"PIPE", SIGPIPE}, {"ALRM", SIGALRM}, {"TERM", SIGTERM},
    {"CHLD", SIGCHLD}, {"CONT", SIGCONT}, {"STOP", SIGSTOP}, {"TSTP", SIGTSTP}, {"TTIN", SIGTTIN},
    {"TTOU", SIGTTOU}, {"URG", SIGURG},   {"XCPU", SIGXCPU}, {"XFSZ", SIGXFSZ}, {"VTALRM", SIGVTALRM},
    {"PROF", SIGPROF}, {"WINCH", SIGWINCH}, {"IO", SIGIO},  {"PWR", SIGPWR},   {"SYS", SIGSYS},
};
}  // namespace

int signal_number(const std::string& s) {
    if (s.empty()) return 0;
    if (s.find_first_not_of("0123456789") == std::string::npos) {
        if (s.size() > 2) return 0;
        int n = std::stoi(s);
        return n >= 1 && n <= 64 ? n : 0;
    }
    std::string n = s.rfind("SIG", 0) == 0 ? s.substr(3) : s;
    for (const auto& [name, num] : SIGS)
        if (n == name) return num;
    return 0;
}

std::string signal_name(int sig) {
    for (const auto& [name, num] : SIGS)
        if (num == sig) return std::string("SIG") + name;
    return "SIG" + std::to_string(sig);
}

}  // namespace d2
