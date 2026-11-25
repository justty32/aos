// main.cpp：aos-daemon——一台最小的 aos daemon：自己是一隻 aos proc，另外擺出 procs/、procs_ctl、procs_status 管底下的 proc。
#include "daemon.hpp"

#include <cerrno>
#include <climits>
#include <csignal>
#include <cstring>
#include <iostream>
#include <sys/eventfd.h>
#include <sys/signalfd.h>
#include <sys/stat.h>
#include <unistd.h>

using namespace aosd;

namespace {

const char* USAGE =
    "aos-daemon [NAME [MOUNTPOINT]] [--mount-base DIR] [--register-timeout S] [--check-interval S] "
    "[--check-timeout S] [--stop-timeout S] [--ctl-timeout S]";

const char* HELP = R"(aos-daemon - A minimal aos daemon: an aos proc that also manages procs below it.

usage: aos-daemon [NAME [MOUNTPOINT]] [flags]

NAME and MOUNTPOINT default to $AOS_NAME (last part) and $AOS_MOUNT, which a parent
daemon sets together with $AOS_NAME_PID; they count only when $AOS_NAME_PID equals this
process's pid (a wrapper script must exec aos-daemon). Without $AOS_ROOT this daemon is the root and prints
"export AOS_ROOT=/proc/<PID>/cwd" on stdout once it is mounted.

Files: status, ctl (stop, pause, resume), settings, attrs, _metainfo.json,
procs/ (alias proc), procs_ctl, procs_status.
A proc started here gets AOS_NAME, AOS_MOUNT, AOS_NAME_PID (its own pid) and AOS_ROOT.
procs_ctl words: add NAME PATH, rm NAME, stop NAME, start NAME, kill NAME, register NAME PID.
PATH is an executable or a json file {"exec": [argv...], "env": {...}}.

flags:
  --mount-base DIR       where mountpoints of procs below go
                         (default $XDG_RUNTIME_DIR/aos/mnt, else /tmp/aos-<uid>/mnt)
  --register-timeout S   seconds a new proc has to make its settings readable (default 10)
  --check-interval S     seconds between stuck checks (default 5)
  --check-timeout S      seconds a status read may take before the proc counts as stuck (default 1)
  --stop-timeout S       seconds to wait after "stop" before killing, on daemon stop and rm (default 10)
  --ctl-timeout S        seconds to write a proc's ctl or read an add PATH (default 1)
  -h, --help             show this help
)";

int fail(const std::string& code, const std::string& why) {
    std::cerr << "aos-daemon: error: " << code << " " << why << " (usage: " << USAGE << ")\n";
    return 1;
}

std::string env_or(const char* k, const std::string& dflt) {
    const char* v = std::getenv(k);
    return v && *v ? v : dflt;
}

void mkdirs(const std::string& path) {
    for (size_t i = 1; i <= path.size(); ++i)
        if (i == path.size() || path[i] == '/') mkdir(path.substr(0, i).c_str(), 0700);
}

std::string absolute(const std::string& p) {
    if (!p.empty() && p[0] == '/') return p;
    char buf[PATH_MAX];
    return std::string(getcwd(buf, sizeof buf) ? buf : "/") + "/" + p;
}

bool name_ok(const std::string& n) {
    if (n.empty() || n.size() > 64 || n[0] == '.') return false;
    for (char c : n)
        if (!isalnum(static_cast<unsigned char>(c)) && c != '_' && c != '-' && c != '.') return false;
    return true;
}

// 起來時：清掉自己的掛載點、與 mount-base 底下屬於自己這一支的死掛載（活著的不動）
void clean_dead(const Config& cfg) {
    if (pf::cleanup_dead_mount(cfg.mountpoint) == pf::Cleanup::Unmounted) rmdir(cfg.mountpoint.c_str());
    std::string prefix = cfg.mount_base + "/";
    if (cfg.aos_name != "/") {
        std::string own = cfg.aos_name;
        for (char& c : own)
            if (c == '/') c = '%';
        prefix += own + "%";
    }
    for (const auto& e : read_mountinfo())
        if (e.fstype == "fuse.aosproc" && e.point.rfind(prefix, 0) == 0 &&
            e.point.find('/', cfg.mount_base.size() + 1) == std::string::npos &&
            pf::cleanup_dead_mount(e.point) == pf::Cleanup::Unmounted)
            rmdir(e.point.c_str());
}

}  // namespace

int main(int argc, char** argv) {
    Config cfg;
    std::vector<std::string> pos;
    std::string base;
    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        try {
            auto num = [&](double& out) {
                if (i + 1 >= argc) throw std::invalid_argument(a + " needs a value");
                out = std::stod(argv[++i]);
                if (!(out > 0)) throw std::invalid_argument(a + " must be > 0");
            };
            if (a == "-h" || a == "--help") {
                std::cout << HELP;
                return 0;
            } else if (a == "--mount-base") {
                if (i + 1 >= argc) throw std::invalid_argument("--mount-base needs a value");
                base = argv[++i];
            } else if (a == "--register-timeout") num(cfg.register_timeout);
            else if (a == "--check-interval") num(cfg.check_interval);
            else if (a == "--check-timeout") num(cfg.check_timeout);
            else if (a == "--stop-timeout") num(cfg.stop_timeout);
            else if (a == "--ctl-timeout") num(cfg.ctl_timeout);
            else if (a.rfind("-", 0) == 0) return fail("FlagUnknown", a);
            else pos.push_back(a);
        } catch (const std::exception& e) {
            return fail("ArgumentsBad", e.what());
        }
    }
    // AOS_NAME、AOS_MOUNT 只在 AOS_NAME_PID 等於自己的 PID 時算數（孫子行程繼承到的不算）
    auto given = pf::env_assignment();
    std::string env_name = given ? given->name : "";
    std::string name = pos.size() > 0 ? pos[0] : env_name.substr(env_name.rfind('/') + 1);
    std::string mnt = pos.size() > 1 ? pos[1] : (given ? given->mount : "");
    if (pos.size() > 2 || name.empty() || mnt.empty())
        return fail("ArgumentsBad", "need NAME and MOUNTPOINT (or $AOS_NAME and $AOS_MOUNT with $AOS_NAME_PID = own pid)");
    const pid_t pid = getpid();
    cfg.is_root = env_or("AOS_ROOT", "").empty();
    cfg.aos_name = !env_name.empty() ? env_name : (cfg.is_root ? "/" : name);
    cfg.aos_root = cfg.is_root ? cwd_of(pid) : env_or("AOS_ROOT", "");
    cfg.mountpoint = absolute(mnt);
    if (base.empty()) {
        std::string run = env_or("XDG_RUNTIME_DIR", "");
        base = !run.empty() ? run + "/aos/mnt" : "/tmp/aos-" + std::to_string(getuid()) + "/mnt";
    }
    mkdirs(absolute(base));
    char real[PATH_MAX];
    if (!realpath(absolute(base).c_str(), real)) return fail("MountBaseBad", base + ": " + std::strerror(errno));
    cfg.mount_base = real;
    mkdirs(cfg.mountpoint.substr(0, cfg.mountpoint.rfind('/')));
    clean_dead(cfg);
    const std::string started_at = now_iso();

    // 訊號在所有線起來之前擋下，只由監工的 signalfd 收（SIGCHLD＝收屍）
    sigset_t sigs;
    sigemptyset(&sigs);
    for (int s : {SIGCHLD, SIGTERM, SIGINT, SIGHUP}) sigaddset(&sigs, s);
    pthread_sigmask(SIG_BLOCK, &sigs, nullptr);
    signal(SIGPIPE, SIG_IGN);
    int sfd = signalfd(-1, &sigs, SFD_CLOEXEC | SFD_NONBLOCK);
    int efd = eventfd(0, EFD_CLOEXEC | EFD_NONBLOCK);
    auto wake = [efd] {
        uint64_t one = 1;
        if (write(efd, &one, sizeof one) < 0) {}
    };

    State st;
    pf::Options opt;
    opt.fsname = "aosproc";
    opt.on_gone = [&st, wake] {
        // 連線被斷開（例：上面的 daemon kill 了我）：照 stop 收底下的
        std::lock_guard<std::mutex> g(st.mu);
        st.stop_requested = true;
        wake();
    };
    pf::Fs fs(opt);
    try {
        pf::Ctl& ctl = fs.add_ctl("ctl", "aos_ctl_");
        pf::Ctl& pctl = fs.add_ctl("procs_ctl", "aos_procs_ctl_");
        // 回答的線上跑：只抄表、不碰任何路徑
        fs.add_text("status", [&] {
            std::string ph;
            size_t n;
            {
                std::lock_guard<std::mutex> g(st.mu);
                ph = st.phase;
                n = st.procs.size();
            }
            return pf::Kv()
                .add("aos_name", cfg.aos_name)
                .add("aos_phase", ph)
                .add("aos_pid", static_cast<long long>(pid))
                .add("aos_started_at", started_at)
                .raw(ctl.feedback())
                .add("aos_procs", static_cast<long long>(n))
                .raw(pctl.feedback())
                .str();
        });
        fs.add_text("settings", [&] {
            return pf::Kv().add("aos_persist", "").add("aos_mailbox", "").add("mount_base", cfg.mount_base).str();
        });
        fs.add_text("attrs", [] { return pf::Kv().add("aos_kind", "fuse").add("aos_live", "yes").str(); });
        fs.add_json("_metainfo.json", "{\n  \"summary\": \"Minimal aos daemon (proto9 aos-daemon).\"\n}\n");
        fs.add_dir("procs");
        fs.add_symlink("proc", "procs");
        fs.add_text("procs_status", [&] {
            pf::Kv kv;
            std::lock_guard<std::mutex> g(st.mu);
            for (const auto& [n, p] : st.procs) {
                kv.add(n + ".phase", p.phase).add(n + ".want", p.want);
                kv.add(n + ".pid", p.pid > 0 ? std::to_string(p.pid) : "-");
                kv.add(n + ".code", p.code).add(n + ".signal", p.sig).add(n + ".reason", p.reason);
                kv.add(n + ".persist", p.persist).add(n + ".mailbox", p.mailbox).add(n + ".stuck", p.stuck);
                if (p.external) kv.add(n + ".external", "yes");
            }
            return kv.str();
        });

        auto no_args = [](const pf::Command& c) -> std::string {
            return c.words.size() == 1 ? "" : "ArgumentsBad " + c.words[0] + " takes no arguments";
        };
        auto set_phase = [&st](const char* ph) {
            std::lock_guard<std::mutex> g(st.mu);
            if (st.phase != "stopping") st.phase = ph;
            return pf::Result::done();
        };
        ctl.on("pause", [=](const pf::Command&) { return set_phase("paused"); }, no_args);
        ctl.on("resume", [=](const pf::Command&) { return set_phase("running"); }, no_args);
        ctl.on("stop", [&st, wake](const pf::Command&) {
            std::lock_guard<std::mutex> g(st.mu);
            st.stop_requested = true;
            wake();
            return pf::Result::hold_until_exit();   // 做完＝daemon 收完底下的、結束
        }, no_args);

        // procs_ctl：回答的線上只看參數與表；動作交給監工，做事的線等它回話（有上限）
        auto check = [&st](const pf::Command& c) -> std::string {
            const std::string& w = c.words[0];
            bool creates = w == "add" || w == "register";
            if (c.words.size() != (creates ? 3u : 2u))
                return "ArgumentsBad usage: " + w + (creates ? (w == "add" ? " NAME PATH" : " NAME PID") : " NAME");
            const std::string& n = c.words[1];
            if (!name_ok(n)) return "NameBad " + n + " (letters, digits, _ - . ; not starting with .)";
            if (w == "add" && c.words[2][0] != '/') return "PathNotAbsolute " + c.words[2];
            if (w == "register" && (c.words[2].find_first_not_of("0123456789") != std::string::npos || c.words[2].size() > 9 || std::stol(c.words[2]) <= 0))
                return "ArgumentsBad PID must be a positive number";
            std::lock_guard<std::mutex> g(st.mu);
            if (creates || w == "start") {
                if (st.phase == "stopping") return "DaemonStopping not starting anything now";
                if (st.phase == "paused") return "DaemonPaused resume the daemon first";
            }
            auto it = st.procs.find(n);
            if (creates) return it == st.procs.end() ? "" : "ProcExists " + n;
            if (it == st.procs.end()) return "ProcUnknown " + n;
            if (it->second.external && w != "rm") return "ProcExternal " + n + " was registered; only rm is allowed";
            return "";
        };
        auto act = [&st, &cfg, wake](const pf::Command& c) {
            auto r = std::make_shared<Request>();
            r->words = c.words;
            {
                std::lock_guard<std::mutex> g(st.mu);
                st.requests.push_back(r);
            }
            wake();
            if (!r->wait(cfg.ctl_timeout + cfg.check_timeout + 5))
                return pf::Result::failed("Internal supervisor did not answer in time");
            return r->error.empty() ? pf::Result::done() : pf::Result::failed(r->error);
        };
        for (const char* w : {"add", "rm", "stop", "start", "kill", "register"}) pctl.on(w, act, check);

        fs.mount(cfg.mountpoint);
    } catch (const std::exception& e) {
        return fail("MountFailed", e.what());
    }
    // chdir 要在回答的線起來之後：chdir 本身會送 LOOKUP／GETATTR 進來
    if (chdir(fs.mountpoint().c_str()) != 0) {
        fs.unmount();
        return fail("ChdirFailed", std::strerror(errno));
    }
    if (cfg.is_root) std::cout << "export AOS_ROOT=" << cwd_of(pid) << std::endl;

    Supervisor(cfg, st, fs, sfd, efd).run();
    fs.unmount();
    return 0;
}
