// main.cpp：aos-procfs-demo——一隻最小的 aos proc（status／ctl／settings／attrs／_metainfo.json／mailbox/），另有 --cleanup 收死掉的掛載。
#include "aos/procfs.hpp"
#include "mail.hpp"

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

const char* USAGE = "aos-procfs-demo [NAME MOUNTPOINT] [--threads N] [--socket] [--persists PATH] [--obey WORDS] [--mail-* N] | --cleanup PATH [--force]";

const char* HELP = R"(aos-procfs-demo - A minimal aos proc served over FUSE.

usage: aos-procfs-demo NAME MOUNTPOINT [--threads N] [--socket] [--persists PATH] [--obey WORDS] [--mail-* N]
       aos-procfs-demo --cleanup PATH [--force]

Without NAME and MOUNTPOINT it uses $AOS_NAME and $AOS_MOUNT (set by aos-daemon), but only
when $AOS_NAME_PID equals its own pid: a grandchild that inherited them ignores them, so a
wrapper script must exec this program.

Mounts MOUNTPOINT, chdirs into it and prints "pid: N" and "AOS_ROOT=/proc/N/cwd".
Files: status, ctl, settings, attrs, _metainfo.json, links/, mailbox/ (tmp/ new/ cur/).
ctl words: stop, pause, resume; for tests: slow N (sleep N seconds), link NAME TARGET,
unlink NAME (add or remove the symlink links/NAME), take (take the oldest letter from
mailbox/new/), refuse on|off (refuse letters as they are moved into new/, with EPERM).
Deliver a letter: write it under mailbox/tmp/, then mv it into mailbox/new/.

flags:
  --threads N      answer threads (default 1)
  --socket         allow unix sockets in the root and serve an echo socket named "sock"
  --persists PATH  value of aos_persists in settings (default -)
  --obey WORDS     add "aos_obey: WORDS" to settings: the ctl words a daemon this proc is
                   registered with may use on it, e.g. "stop kill" (default: no line, only rm)
  --mail-max-bytes N    max bytes in one letter (default 8388608; over it: EFBIG)
  --mail-max-letters N  max entries in tmp/ and new/ together (default 4096; ENOSPC)
  --mail-max-total N    max bytes in tmp/ and new/ together (default 67108864; ENOSPC)
  --mail-stale S        drop entries in tmp/ untouched for S seconds (default 129600)
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
    std::string persists, obey, clean;
    DemoMail dm;
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
            } else if (a == "--persists") {
                persists = need("--persists");
            } else if (a == "--obey") {
                obey = need("--obey");
            } else if (a == "--cleanup") {
                clean = need("--cleanup");
            } else if (a == "--force") {
                force = true;
            } else if (demo_mail_wants_value(a)) {
                demo_mail_flag(a, need(a.c_str()), dm);
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
    // daemon 起它時不給參數，名字路與掛載點走環境變數 AOS_NAME、AOS_MOUNT（AOS_NAME_PID 要等於自己的 PID）
    if (pos.empty())
        if (auto a = pf::env_assignment()) pos = {a->name, a->mount};
    if (pos.size() != 2)
        return fail("ArgumentsBad", "need NAME and MOUNTPOINT (or $AOS_NAME and $AOS_MOUNT with $AOS_NAME_PID = own pid)");
    const std::string name = pos[0], mnt = pos[1];
    const long long pid = static_cast<long long>(getpid());
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
            return pf::to_text(DemoStatus{name, ph, pid, started_at, ctl->snapshot(), demo_mail_status(dm)});
        });
        // settings 的 aos_mailbox 是「掛了的時候信投到哪」（硬碟上的），跟活著時的 mailbox/ 不是同一個：demo 沒有，寫 -
        fs.add_text("settings", [&] { return pf::to_text(DemoSettings{persists, "", obey}); });
        fs.add_text("attrs", [] { return pf::to_text(DemoAttrs{"fuse", "yes", "yes"}); });
        demo_mail_setup(fs, *ctl, dm);
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
