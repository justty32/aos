// mount.cpp：靠 setuid 的 fusermount3 掛載與卸載、讀 /proc/self/mountinfo、abort 連線、清死掉的掛載。
#include "internal.hpp"

#include <cerrno>
#include <climits>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <fstream>
#include <signal.h>
#include <sstream>
#include <stdexcept>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>

extern char** environ;

namespace aos::procfs {

namespace {

thread_local bool g_answer = false;

// mountinfo 的路徑把空白、tab、換行、反斜線寫成 \040 這種八進位
std::string unescape(const std::string& s) {
    std::string out;
    for (size_t i = 0; i < s.size(); ++i) {
        if (s[i] == '\\' && i + 3 < s.size()) {
            int v = 0;
            bool ok = true;
            for (int k = 1; k <= 3; ++k) {
                char c = s[i + k];
                if (c < '0' || c > '7') ok = false;
                v = v * 8 + (c - '0');
            }
            if (ok) {
                out += static_cast<char>(v);
                i += 3;
                continue;
            }
        }
        out += s[i];
    }
    return out;
}

std::string find_fusermount() {
    // fork 之後不能找 PATH（execvp 不是 async-signal-safe），所以先在這裡找好
    const char* path = std::getenv("PATH");
    std::istringstream in(path ? path : "/usr/bin:/bin");
    for (std::string dir; std::getline(in, dir, ':');) {
        std::string p = (dir.empty() ? "." : dir) + "/fusermount3";
        if (access(p.c_str(), X_OK) == 0) return p;
    }
    return "/usr/bin/fusermount3";
}

// fork＋execve fusermount3；keep_fd 是要留給它的 fd（其餘照 close-on-exec 走）。回 pid。
pid_t spawn_fusermount(const std::vector<std::string>& args, const std::string& extra_env, bool quiet) {
    // fork 之前把 argv／envp 全部備好：fork 之後只准做 async-signal-safe 的事
    std::string prog = find_fusermount();
    std::vector<std::string> store;
    store.push_back(prog);
    for (const auto& a : args) store.push_back(a);
    std::vector<char*> argv;
    for (auto& s : store) argv.push_back(s.data());
    argv.push_back(nullptr);
    std::vector<std::string> envs;
    for (char** e = environ; e && *e; ++e)
        if (std::strncmp(*e, "_FUSE_COMMFD=", 13) != 0) envs.emplace_back(*e);
    if (!extra_env.empty()) envs.push_back(extra_env);
    std::vector<char*> envp;
    for (auto& s : envs) envp.push_back(s.data());
    envp.push_back(nullptr);
    int devnull = quiet ? open("/dev/null", O_WRONLY | O_CLOEXEC) : -1;

    pid_t pid = fork();
    if (pid == 0) {
        // cwd 換到 /：別讓 fusermount3 站在某個掛載點裡
        if (chdir("/") != 0) _exit(127);
        if (devnull >= 0) dup2(devnull, 2);
        execve(argv[0], argv.data(), envp.data());
        _exit(127);
    }
    if (devnull >= 0) close(devnull);
    if (pid < 0) throw std::runtime_error(std::string("fork: ") + std::strerror(errno));
    return pid;
}

int wait_exit(pid_t pid) {
    int st = 0;
    while (waitpid(pid, &st, 0) < 0)
        if (errno != EINTR) return -1;
    return WIFEXITED(st) ? WEXITSTATUS(st) : 128 + WTERMSIG(st);
}

}  // namespace

void mark_answer_thread() { g_answer = true; }

bool on_answer_thread() { return g_answer; }

void forbid_on_answer_thread(const char* what) {
    if (g_answer) throw std::logic_error(std::string(what) + " called on an answer thread (would deadlock)");
}

int run_fusermount(const std::vector<std::string>& args, bool quiet) {
    return wait_exit(spawn_fusermount(args, "", quiet));
}

int fuse_mount(const std::string& mnt, const std::string& opts) {
    int sv[2];
    if (socketpair(AF_UNIX, SOCK_STREAM, 0, sv) != 0)
        throw std::runtime_error(std::string("socketpair: ") + std::strerror(errno));
    // sv[0] 留給自己（close-on-exec），sv[1] 要被 fusermount3 繼承，它從這條送回 /dev/fuse 的 fd
    fcntl(sv[0], F_SETFD, FD_CLOEXEC);
    pid_t pid;
    try {
        pid = spawn_fusermount({"-o", opts, "--", mnt}, "_FUSE_COMMFD=" + std::to_string(sv[1]), false);
    } catch (...) {
        close(sv[0]);
        close(sv[1]);
        throw;
    }
    close(sv[1]);

    char byte;
    iovec iov{&byte, 1};
    alignas(cmsghdr) char cbuf[CMSG_SPACE(sizeof(int))];
    msghdr msg{};
    msg.msg_iov = &iov;
    msg.msg_iovlen = 1;
    msg.msg_control = cbuf;
    msg.msg_controllen = sizeof(cbuf);
    ssize_t n;
    // MSG_CMSG_CLOEXEC：收到的那一刻就是 close-on-exec，子行程拿不到（拿到的話主行程死了掛載也不斷線）
    while ((n = recvmsg(sv[0], &msg, MSG_CMSG_CLOEXEC)) < 0 && errno == EINTR) {}
    close(sv[0]);
    int rc = wait_exit(pid);
    int fd = -1;
    if (n > 0) {
        for (cmsghdr* c = CMSG_FIRSTHDR(&msg); c; c = CMSG_NXTHDR(&msg, c))
            if (c->cmsg_level == SOL_SOCKET && c->cmsg_type == SCM_RIGHTS) std::memcpy(&fd, CMSG_DATA(c), sizeof(int));
    }
    if (fd < 0) throw std::runtime_error("fusermount3 did not pass a /dev/fuse fd (exit " + std::to_string(rc) + ")");
    return fd;
}

std::vector<MountEntry> read_mountinfo() {
    std::vector<MountEntry> out;
    std::ifstream in("/proc/self/mountinfo");
    for (std::string line; std::getline(in, line);) {
        // id parent major:minor root point opts [optional...] - fstype source superopts
        std::istringstream ls(line);
        std::string id, parent, dev, root, point, opts, f;
        ls >> id >> parent >> dev >> root >> point >> opts;
        while (ls >> f && f != "-") {}
        MountEntry e;
        ls >> e.fstype >> e.source;
        if (std::sscanf(dev.c_str(), "%u:%u", &e.major, &e.minor) != 2) continue;
        e.point = unescape(point);
        e.source = unescape(e.source);
        out.push_back(std::move(e));
    }
    return out;
}

std::string canonical_point(const std::string& path) {
    std::string p = path;
    while (p.size() > 1 && p.back() == '/') p.pop_back();
    size_t slash = p.rfind('/');
    std::string dir = slash == std::string::npos ? "." : (slash == 0 ? "/" : p.substr(0, slash));
    std::string base = slash == std::string::npos ? p : p.substr(slash + 1);
    char buf[PATH_MAX];
    if (!realpath(dir.c_str(), buf)) return "";
    std::string d = buf;
    return d == "/" ? "/" + base : d + "/" + base;
}

long connection_id(const std::string& path) {
    std::string pt = canonical_point(path);
    long id = -1;
    // 同一點疊了好幾層時最後一筆是最上面那層
    for (const auto& e : read_mountinfo())
        if (e.point == pt && e.fstype.rfind("fuse", 0) == 0) id = static_cast<long>(e.major) << 20 | e.minor;
    return id;
}

bool abort_connection(const std::string& path) {
    forbid_on_answer_thread("abort_connection");
    long id = connection_id(path);
    if (id < 0) return false;
    std::ofstream f("/sys/fs/fuse/connections/" + std::to_string(id) + "/abort");
    f << "1";
    f.flush();
    return static_cast<bool>(f);
}

Cleanup cleanup_dead_mount(const std::string& path, bool force) {
    forbid_on_answer_thread("cleanup_dead_mount");
    std::string pt = canonical_point(path);
    const MountEntry* hit = nullptr;
    auto all = read_mountinfo();
    for (const auto& e : all)
        if (e.point == pt) hit = &e;
    if (!hit) return Cleanup::NotMounted;
    if (hit->fstype != "fuse.aosproc") return Cleanup::Foreign;
    if (!force) {
        size_t colon = hit->source.rfind(':');
        long pid = colon == std::string::npos ? 0 : std::atol(hit->source.c_str() + colon + 1);
        if (pid > 0 && (kill(static_cast<pid_t>(pid), 0) == 0 || errno == EPERM)) {
            // 殭屍的 fd 已經關了、不會再回答，算死；其餘（含被暫停的）算活著，不歸這個函數管
            std::ifstream st("/proc/" + std::to_string(pid) + "/stat");
            std::string s((std::istreambuf_iterator<char>(st)), {});
            size_t rp = s.rfind(')');
            bool zombie = rp != std::string::npos && rp + 2 < s.size() && s[rp + 2] == 'Z';
            if (!zombie) return Cleanup::Alive;
        }
    }
    return run_fusermount({"-u", "-z", pt}, false) == 0 ? Cleanup::Unmounted : Cleanup::Failed;
}

}  // namespace aos::procfs
