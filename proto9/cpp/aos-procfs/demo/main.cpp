// main.cpp：aos-procfs-demo——一隻最小的 aos proc（status／ctl／settings／attrs／_metainfo.json），另有 --cleanup 收死掉的掛載。
#include "aos/procfs.hpp"

#include <cerrno>
#include <chrono>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <iostream>
#include <mutex>
#include <poll.h>
#include <sys/eventfd.h>
#include <sys/signalfd.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <thread>
#include <unistd.h>

namespace {

namespace pf = aos::procfs;

const char* USAGE = "aos-procfs-demo [NAME MOUNTPOINT] [--threads N] [--socket] [--persist PATH] | --cleanup PATH [--force]";

const char* HELP = R"(aos-procfs-demo - A minimal aos proc served over FUSE.

usage: aos-procfs-demo NAME MOUNTPOINT [--threads N] [--socket] [--persist PATH]
       aos-procfs-demo --cleanup PATH [--force]

Without NAME and MOUNTPOINT it uses $AOS_NAME and $AOS_MOUNT (set by aos-daemon).

Mounts MOUNTPOINT, chdirs into it and prints "pid: N" and "AOS_ROOT=/proc/N/cwd".
Files: status, ctl, settings, attrs, _metainfo.json, links/.
ctl words: stop, pause, resume; for tests: slow N (sleep N seconds), link NAME TARGET,
unlink NAME (add or remove the symlink links/NAME).

flags:
  --threads N      answer threads (default 1)
  --socket         allow unix sockets in the root and serve an echo socket named "sock"
  --persist PATH   value of aos_persist in settings (default -)
  --cleanup PATH   unmount a dead aos-procfs mount at PATH, then exit
  --force          with --cleanup: unmount even if the server process still exists
  -h, --help       show this help
)";

int fail(const std::string& code, const std::string& why) {
    std::cerr << "aos-procfs-demo: error: " << code << " " << why << " (usage: " << USAGE << ")\n";
    return 1;
}

// localtime 會去讀 /etc/localtime，所以只在起來時算一次，不在回答的線上算
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

int cleanup(const std::string& path, bool force) {
    switch (pf::cleanup_dead_mount(path, force)) {
    case pf::Cleanup::Unmounted:
        rmdir(path.c_str());   // 空夾是 mount 時建的；不是空的就留著
        std::cout << "unmounted " << path << "\n";
        return 0;
    case pf::Cleanup::NotMounted:
        std::cerr << "aos-procfs-demo: error: NotMounted no mount at " << path << "\n";
        return 10;
    case pf::Cleanup::Alive:
        std::cerr << "aos-procfs-demo: error: ServerAlive the server process still exists (use --force)\n";
        return 1;
    case pf::Cleanup::Foreign:
        std::cerr << "aos-procfs-demo: error: MountForeign not an aos-procfs mount: " << path << "\n";
        return 1;
    default:
        std::cerr << "aos-procfs-demo: error: UnmountFailed fusermount3 -u -z failed on " << path << "\n";
        return 1;
    }
}

// 測試用的 echo socket：一行進、一行 "pong: ..." 出
void echo_server(int lfd) {
    for (;;) {
        int c = accept4(lfd, nullptr, nullptr, SOCK_CLOEXEC);
        if (c < 0) {
            if (errno == EINTR) continue;
            return;
        }
        char buf[512];
        ssize_t n = read(c, buf, sizeof buf);
        if (n > 0) {
            std::string out = "pong: " + std::string(buf, static_cast<size_t>(n));
            if (write(c, out.data(), out.size()) < 0) {}
        }
        close(c);
    }
}

}  // namespace

int main(int argc, char** argv) {
    std::vector<std::string> pos;
    int threads = 1;
    bool sock = false, force = false;
    std::string persist, clean;
    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        auto need = [&](const char* f) -> std::string {
            if (i + 1 >= argc) throw std::invalid_argument(std::string(f) + " needs a value");
            return argv[++i];
        };
        try {
            if (a == "-h" || a == "--help") {
                std::cout << HELP;
                return 0;
            } else if (a == "--threads") {
                threads = std::stoi(need("--threads"));
            } else if (a == "--socket") {
                sock = true;
            } else if (a == "--persist") {
                persist = need("--persist");
            } else if (a == "--cleanup") {
                clean = need("--cleanup");
            } else if (a == "--force") {
                force = true;
            } else if (a.rfind("-", 0) == 0) {
                return fail("FlagUnknown", a);
            } else {
                pos.push_back(a);
            }
        } catch (const std::exception& e) {
            return fail("ArgumentsBad", e.what());
        }
    }
    if (!clean.empty()) return cleanup(clean, force);
    // daemon 起它時不給參數，名字路與掛載點走環境變數 AOS_NAME、AOS_MOUNT
    const char* en = std::getenv("AOS_NAME");
    const char* em = std::getenv("AOS_MOUNT");
    if (pos.empty() && en && *en && em && *em) pos = {en, em};
    if (pos.size() != 2) return fail("ArgumentsBad", "need NAME and MOUNTPOINT (or $AOS_NAME and $AOS_MOUNT)");
    const std::string name = pos[0], mnt = pos[1];
    const long pid = static_cast<long>(getpid());
    const std::string started_at = now_iso();

    // 訊號在所有線起來之前擋下，只由主線的 signalfd 收
    sigset_t sigs;
    sigemptyset(&sigs);
    sigaddset(&sigs, SIGTERM);
    sigaddset(&sigs, SIGINT);
    sigaddset(&sigs, SIGHUP);
    pthread_sigmask(SIG_BLOCK, &sigs, nullptr);
    int sfd = signalfd(-1, &sigs, SFD_CLOEXEC);
    int efd = eventfd(0, EFD_CLOEXEC);   // stop 指令或連線沒了：叫醒主線
    auto wake = [efd] {
        uint64_t one = 1;
        if (write(efd, &one, sizeof one) < 0) {}
    };

    std::mutex mu;
    std::string phase = "running";
    auto set_phase = [&](const char* p) {
        std::lock_guard<std::mutex> g(mu);
        phase = p;
    };

    pf::Options opt;
    opt.threads = threads;
    opt.root_sockets = sock;
    opt.on_gone = wake;
    pf::Fs fs(opt);
    pf::Ctl* ctl = nullptr;
    try {
        ctl = &fs.add_ctl("ctl", "aos_ctl_");
        fs.add_text("status", [&] {
            std::string ph;
            {
                std::lock_guard<std::mutex> g(mu);
                ph = phase;
            }
            return pf::Kv()
                .add("aos_name", name)
                .add("aos_phase", ph)
                .add("aos_pid", static_cast<long long>(pid))
                .add("aos_started_at", started_at)
                .raw(ctl->feedback())
                .str();
        });
        fs.add_text("settings", [&] { return pf::Kv().add("aos_persist", persist).add("aos_mailbox", "").str(); });
        fs.add_text("attrs", [] { return pf::Kv().add("aos_kind", "fuse").add("aos_live", "yes").str(); });
        fs.add_json("_metainfo.json", "{\n  \"summary\": \"Minimal aos proc served over FUSE by aos-procfs-demo.\"\n}\n");

        auto no_args = [](const pf::Command& c) -> std::string {
            return c.words.size() == 1 ? "" : "ArgumentsBad " + c.words[0] + " takes no arguments";
        };
        ctl->on("pause", [&](const pf::Command&) { set_phase("paused"); return pf::Result::done(); }, no_args);
        ctl->on("resume", [&](const pf::Command&) { set_phase("running"); return pf::Result::done(); }, no_args);
        ctl->on("stop", [&](const pf::Command&) {
            set_phase("stopping");
            wake();
            return pf::Result::hold_until_exit();   // stop 的「做完」是行程結束，鎖不放
        }, no_args);
        ctl->on("slow", [](const pf::Command& c) {
            std::this_thread::sleep_for(std::chrono::duration<double>(std::stod(c.words[1])));
            return pf::Result::done();
        }, [](const pf::Command& c) -> std::string {
            try {
                if (c.words.size() == 2 && std::stod(c.words[1]) >= 0) return "";
            } catch (...) {
            }
            return "ArgumentsBad slow needs one number of seconds";
        });

        // 測試用：在 links/ 底下隨時加、拿掉 symlink（daemon 的 procs/<名> 會這樣用）
        fs.add_dir("links");
        ctl->on("link", [&fs](const pf::Command& c) {
            try {
                fs.add_symlink("links/" + c.words[1], c.words[2]);
            } catch (const std::exception& e) {
                return pf::Result::failed(std::string("LinkFailed ") + e.what());
            }
            return pf::Result::done();
        }, [](const pf::Command& c) -> std::string {
            return c.words.size() == 3 && c.words[1].find('/') == std::string::npos ? "" : "ArgumentsBad link NAME TARGET";
        });
        ctl->on("unlink", [&fs](const pf::Command& c) {
            return fs.remove("links/" + c.words[1]) ? pf::Result::done() : pf::Result::failed("LinkMissing " + c.words[1]);
        }, [](const pf::Command& c) -> std::string {
            return c.words.size() == 2 ? "" : "ArgumentsBad unlink NAME";
        });

        fs.mount(mnt);
    } catch (const std::exception& e) {
        return fail("MountFailed", e.what());
    }
    // chdir 要在回答的線起來之後：chdir 本身會送 LOOKUP／GETATTR 進來
    if (chdir(fs.mountpoint().c_str()) != 0) {
        fs.unmount();
        return fail("ChdirFailed", std::strerror(errno));
    }
    int lfd = -1;
    if (sock) {
        lfd = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);
        sockaddr_un sa{};
        sa.sun_family = AF_UNIX;
        std::strcpy(sa.sun_path, "sock");   // 相對路徑：已經站在自己的目錄裡
        if (bind(lfd, reinterpret_cast<sockaddr*>(&sa), sizeof sa) != 0 || listen(lfd, 16) != 0) {
            std::cerr << "aos-procfs-demo: warning: socket bind failed: " << std::strerror(errno) << "\n";
            close(lfd);
            lfd = -1;
        } else {
            std::thread(echo_server, lfd).detach();
        }
    }
    std::cout << "pid: " << pid << "\nAOS_ROOT=/proc/" << pid << "/cwd" << std::endl;

    pollfd pfd[2] = {{sfd, POLLIN, 0}, {efd, POLLIN, 0}};
    for (;;) {
        int n = poll(pfd, 2, -1);
        if (n < 0 && errno == EINTR) continue;
        if (n < 0) break;
        if (pfd[0].revents) set_phase("stopping");
        break;
    }
    if (lfd >= 0) shutdown(lfd, SHUT_RDWR);   // 叫醒 accept，echo 線自己結束
    fs.unmount();
    return 0;
}
