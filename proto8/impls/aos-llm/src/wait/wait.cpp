// wait.cpp：【wait】收回信、等回信、撤信（說明見 wait.hpp）。
#include "wait/wait.hpp"

#include "aos/util/files.hpp"

#include <cstdio>
#include <filesystem>
#include <optional>
#include <set>
#include <signal.h>

namespace fs = std::filesystem;

namespace aos::llm {

static bool exists(const std::string& p) {
    std::error_code ec;
    return fs::exists(p, ec);
}

// 回信信箱 new/ 裡回 id 的那封（看過不是的記在 seen，不再讀）；沒有＝nullopt。
static std::optional<std::string> find_reply(const aos::post::Mailbox& rb, const std::string& id,
                                             std::set<std::string>& seen) {
    std::error_code ec;
    std::vector<std::string> names;
    for (const fs::directory_entry& e : fs::directory_iterator(rb.fresh(), ec)) {
        names.push_back(e.path().filename().string());
    }
    for (const std::string& n : names) {
        if (n.empty() || n[0] == '.' || seen.count(n)) {
            continue;
        }
        std::optional<Json> l = aos::read_json(aos::join(aos::join(rb.fresh(), n), "letter.json"));
        if (l && l->is_object() && l->value("in_reply_to", Json()) == Json(id)) {
            return n;
        }
        if (l) {
            seen.insert(n);   // 讀得到、不是回我的；讀不到的（正在被別人認領）下次再看
        }
    }
    return std::nullopt;
}

static int deliver(const aos::post::Mailbox& rb, const std::string& n, bool full) {
    std::string dir = aos::join(rb.cur(), n);
    std::optional<Json> l = aos::read_json(aos::join(dir, "letter.json"));
    std::optional<Json> reply;
    if (l && l->is_object() && l->contains("body")) {
        reply = aos::llm_kernel::reply_of((*l)["body"]);
    }
    try {
        aos::post::done(rb, n, false);
    } catch (const Error&) {
    }
    if (!reply) {
        throw Error{code::ReplyBad, "cannot understand the reply: body of " + aos::join(dir, "letter.json")};
    }
    if (reply->contains("error")) {
        const Json& e = (*reply)["error"];
        throw Error{e["code"].get<std::string>(), e["msg"].get<std::string>()};
    }
    Json output = (*reply)["message"];
    if (full) {
        output = *reply;
    }
    std::string line = aos::dumps(output) + "\n";
    std::fwrite(line.data(), 1, line.size(), stdout);
    std::fflush(stdout);
    return 0;
}

int recv(const std::string& box, const std::string& name, bool full) {
    aos::post::check_name(name);   // 不合 ArgumentsBad
    aos::post::Mailbox rb = aos::post::open(box);   // 不是資料夾＝MailboxMissing
    std::set<std::string> seen;
    std::optional<std::string> n = find_reply(rb, name, seen);
    if (n && aos::post::take(rb, *n)) {
        return deliver(rb, *n, full);
    }
    return 10;
}

static void withdraw(const Mailbox& mb, const aos::post::Mailbox& rb, const std::string& id,
                     std::set<std::string>& seen) {
    std::error_code ec;
    std::string t = aos::join(mb.tmp(), id);
    if (std::rename(aos::join(mb.fresh(), id).c_str(), t.c_str()) == 0) {
        fs::remove_all(t, ec);
        return;
    }
    // 在 cur/：正在跑，讓它跑完；回信已經到了就收掉，沒到的 kernel 寄回信時看寄信的人不在了會撤回
    std::optional<std::string> n = find_reply(rb, id, seen);
    if (n && aos::post::take(rb, *n)) {
        try {
            aos::post::done(rb, *n, false);
        } catch (const Error&) {
        }
    }
}

int ask_wait(const Mailbox& mb, const std::string& id, bool full) {
    aos::post::Mailbox rb = aos::post::open(reply_box(mb));
    std::set<std::string> seen;
    sigset_t set;
    sigemptyset(&set);
    sigaddset(&set, SIGINT);
    sigaddset(&set, SIGTERM);
    sigaddset(&set, SIGHUP);
    while (true) {
        std::optional<std::string> n = find_reply(rb, id, seen);
        if (n && aos::post::take(rb, *n)) {
            return deliver(rb, *n, full);
        }
        // 照信走的方向看：new → cur（kernel 先寄回信才刪 cur/ 那封，所以 cur/ 沒了回信一定已經到了）
        if (!exists(aos::join(mb.fresh(), id)) && !exists(aos::join(mb.cur(), id)) && !find_reply(rb, id, seen)) {
            if (!exists(rb.fresh())) {   // 11-05 edge-llm：回信信箱被刪＝kernel 寄不進、信照刪，別說成「信不見了」
                throw Error{code::LetterMissing, "reply mailbox " + rb.root + " is gone (kernel could not deliver the reply; letter " + id + " already handled)"};
            }
            throw Error{code::LetterMissing, "letter " + id + " is gone from mailbox " + mb.root};
        }
        timespec ts{0, 20 * 1000 * 1000};
        int sig = sigtimedwait(&set, nullptr, &ts);
        if (sig > 0) {
            withdraw(mb, rb, id, seen);
            return 128 + sig;
        }
    }
}

}  // namespace aos::llm
