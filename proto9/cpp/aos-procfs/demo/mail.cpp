// mail.cpp：aos-procfs-demo 的信箱部分——mailbox/ 收信、ctl 的 take（拿一封）與 refuse on|off（拒收開關）、status 的 mail_* 行。
#include "mail.hpp"

#include <cerrno>
#include <stdexcept>

namespace pf = aos::procfs;

bool demo_mail_wants_value(const std::string& f) {
    return f == "--mail-max-bytes" || f == "--mail-max-letters" || f == "--mail-max-total" || f == "--mail-stale";
}

bool demo_mail_flag(const std::string& f, const std::string& v, DemoMail& dm) {
    auto count = [&] {
        long long n = std::stoll(v);
        if (n < 0) throw std::invalid_argument(f + " must be >= 0");
        return static_cast<size_t>(n);
    };
    if (f == "--mail-max-bytes") dm.limits.max_letter_bytes = count();
    else if (f == "--mail-max-letters") dm.limits.max_letters = count();
    else if (f == "--mail-max-total") dm.limits.max_total_bytes = count();
    else if (f == "--mail-stale") {
        dm.limits.stale_tmp_seconds = std::stod(v);
        if (!(dm.limits.stale_tmp_seconds > 0)) throw std::invalid_argument("--mail-stale must be > 0");
    } else return false;
    return true;
}

void demo_mail_setup(pf::Fs& fs, pf::Ctl& ctl, DemoMail& dm) {
    // accept 在回答的線上跑：只讀一個布林（拿一下自己的小鎖，不碰檔、不等別人）
    dm.box = &fs.add_mailbox("mailbox", dm.limits, [&dm](const pf::Letter&) -> pf::Refusal {
        std::lock_guard<std::mutex> g(dm.mu);
        if (dm.refusing) return {EPERM, "MailRefused this proc refuses letters now (ctl: refuse off)"};
        return {};
    });
    ctl.on("take", [&dm](const pf::Command&) {
        auto l = dm.box->take();
        if (!l) return pf::Result::failed("MailEmpty no letter waiting in mailbox/new/");
        std::lock_guard<std::mutex> g(dm.mu);
        dm.last_name = l->name;
        dm.last_bytes = static_cast<long long>(l->size);
        return pf::Result::done();
    }, [](const pf::Command& c) -> std::string {
        return c.words.size() == 1 ? "" : "ArgumentsBad take takes no arguments";
    });
    ctl.on("refuse", [&dm](const pf::Command& c) {
        std::lock_guard<std::mutex> g(dm.mu);
        dm.refusing = c.words[1] == "on";
        return pf::Result::done();
    }, [](const pf::Command& c) -> std::string {
        return c.words.size() == 2 && (c.words[1] == "on" || c.words[1] == "off") ? "" : "ArgumentsBad refuse on|off";
    });
}

DemoMailStatus demo_mail_status(DemoMail& dm) {
    pf::MailStats s = dm.box->stats();
    DemoMailStatus m;
    m.waiting = static_cast<long long>(s.waiting);
    m.writing = static_cast<long long>(s.writing);
    m.bytes = static_cast<long long>(s.bytes);
    m.delivered = static_cast<long long>(s.delivered);
    m.taken = static_cast<long long>(s.taken);
    m.refused = static_cast<long long>(s.refused);
    m.dropped_stale = static_cast<long long>(s.dropped_stale);
    m.last_refusal = s.last_refusal;
    std::lock_guard<std::mutex> g(dm.mu);
    m.refusing = dm.refusing ? "on" : "off";
    m.last_name = dm.last_name;
    m.last_bytes = dm.last_bytes;
    return m;
}
