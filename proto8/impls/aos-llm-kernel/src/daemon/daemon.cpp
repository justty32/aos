// daemon.cpp：【daemon】找 daemon、寄掛信、讀表（說明見 daemon.hpp）。
#include "daemon/daemon.hpp"

#include "aos/directive.hpp"
#include "aos/files.hpp"
#include "aos/post.hpp"

#include <cstdlib>
#include <filesystem>

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
        throw Error{code::DaemonMissing, d.empty() ? "沒設定 AOS_DAEMON（kernel 要掛在 daemon 底下：問腦請 daemon 掛成 proc）"
                                                   : "AOS_DAEMON 指的資料夾不在：" + d};
    }
    h.daemon = aos::abspath(d);
    if (h.daemon != "/") {
        h.daemon += "/";
    }
    std::string k = env("AOS_KERNEL");
    if (!k.empty()) {
        h.box = aos::abspath(k);
        return h;
    }
    Json mb = Json("procs_ctl_mailbox");
    std::optional<Json> st = aos::read_json(aos::join(h.daemon, PROCS_STATE));
    if (st && st->is_object() && st->contains("procs_ctl_mailbox")) {
        mb = (*st)["procs_ctl_mailbox"];
    }
    if (!mb.is_string() || mb.get<std::string>().empty()) {
        throw Error{code::MailboxMissing, h.daemon + " 的 daemon 沒開 ctl 信箱（procs_state.json 的 procs_ctl_mailbox 是 null）"};
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
