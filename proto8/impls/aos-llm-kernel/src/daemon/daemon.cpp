// daemon.cpp：【daemon】找 daemon、提醒 AOS_KERNEL 缺信箱、寄掛信與讀表（說明見 daemon.hpp）。
#include "daemon/daemon.hpp"

#include "aos/directive.hpp"
#include "aos/util/files.hpp"
#include "aos/post.hpp"

#include <cstdlib>
#include <filesystem>
#include <set>
#include <utility>

#include <unistd.h>

namespace fs = std::filesystem;

namespace aos::llm_kernel {

static const char* PROCS_STATE = "procs_state.json";

static std::string env(const char* name) {
    const char* v = std::getenv(name);
    return v == nullptr ? "" : v;
}

Host find_host() {
    Host h;
    std::string d = env("AOS_DAEMON");
    std::error_code ec;
    if (d.empty() || !fs::is_directory(d, ec)) {
        throw Error{code::DaemonMissing, d.empty() ? "AOS_DAEMON is not set (the kernel runs under a daemon: it asks the daemon to add each brain call as a proc)"
                                                   : "AOS_DAEMON points to a missing directory: " + d};
    }
    h.daemon = aos::abspath(d);
    if (h.daemon != "/") {
        h.daemon += "/";
    }
    std::string k = env("AOS_KERNEL");
    if (!k.empty()) {
        h.box = aos::abspath(k);
        if (!fs::is_directory(aos::join(h.box, "new"), ec)) {
            // 與 AOS_CLOCK 相同：每行程每路徑一次；fork 後仍有自己的提醒。
            static std::set<std::pair<pid_t, std::string>> warned;
            if (warned.emplace(::getpid(), h.box).second) {
                aos::warn("aos-llm-kernel", "AOS_KERNEL points to a missing mailbox: " + h.box + "; letters to it fail until it exists");
            }
        }
        return h;
    }
    Json mb = Json("procs_ctl_mailbox");
    std::optional<Json> st = aos::read_json(aos::join(h.daemon, PROCS_STATE));
    if (st && st->is_object() && st->contains("procs_ctl_mailbox")) {
        mb = (*st)["procs_ctl_mailbox"];
    }
    if (!mb.is_string() || mb.get<std::string>().empty()) {
        throw Error{code::MailboxMissing, h.daemon + ": the daemon has no ctl mailbox (procs_ctl_mailbox in procs_state.json is null)"};
    }
    h.box = aos::abspath(aos::join(h.daemon, mb.get<std::string>()));
    return h;
}

Table read_table(const Host& h) {
    Table t;
    std::optional<Json> st = aos::read_json(aos::join(h.daemon, PROCS_STATE));
    if (!st || !st->is_object()) {
        return t;
    }
    if (st->value("mailbox_warning", Json()).is_string()) {
        t.warning = (*st)["mailbox_warning"].get<std::string>();
    }
    Json p = st->value("procs", Json::object());
    try {
        p = aos::resolve(p, h.daemon);   // 切檔（{"$ref": [分檔, …]}）解回整張
    } catch (const Error&) {
        return t;   // 分檔正在換：當這次沒看到，下一次再讀
    }
    if (p.is_object()) {
        t.procs = p;
    }
    return t;
}

std::string send_procs(const Host& h, const Json& body) {
    aos::post::Mailbox box = aos::post::open(h.box);
    return aos::post::send(box, body, aos::post::SendOpts{});
}

}  // namespace aos::llm_kernel
