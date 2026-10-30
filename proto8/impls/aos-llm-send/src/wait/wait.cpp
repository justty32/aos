// wait.cpp：【wait】等回信、撤信、轉交（說明見 wait.hpp）。
#include "wait/wait.hpp"

#include "aos/files.hpp"
#include "aos/post.hpp"

#include <cstdio>
#include <filesystem>
#include <optional>
#include <set>
#include <signal.h>

#include <unistd.h>

namespace fs = std::filesystem;

namespace aos::llm_send {

static bool exists(const std::string& p) {
    std::error_code ec;
    return fs::exists(p, ec);
}

static void copy_to(const std::string& path, int fd) {
    int err = 0;
    std::optional<std::string> text = aos::read_file(path, err);
    if (!text) {
        return;   // 沒有這個檔＝單子自己導到別處了
    }
    const char* p = text->data();
    size_t left = text->size();
    while (left > 0) {
        ssize_t n = write(fd, p, left);
        if (n <= 0) {
            return;   // 對方不收了（EPIPE 之類）就算了
        }
        p += n;
        left -= (size_t)n;
    }
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

// 認領回信（new → cur）；被別人搶走（不會發生，除非有人亂動）＝false。
static bool take(const aos::post::Mailbox& rb, const std::string& n) {
    return std::rename(aos::join(rb.fresh(), n).c_str(), aos::join(rb.cur(), n).c_str()) == 0;
}

static int relay(const aos::post::Mailbox& rb, const std::string& n) {
    std::string dir = aos::join(rb.cur(), n);
    std::fflush(nullptr);
    copy_to(aos::join(dir, "stdout.txt"), 1);
    copy_to(aos::join(dir, "stderr.txt"), 2);
    std::optional<Json> l = aos::read_json(aos::join(dir, "letter.json"));
    std::optional<Json> reply;
    if (l && l->is_object() && l->contains("body")) {
        reply = aos::llm_kernel::reply_of((*l)["body"]);
    }
    try {
        aos::post::finish(rb, n, false);
    } catch (const Error&) {
    }
    if (!reply) {
        throw Error{code::ReplyBad, "回信讀不懂：" + aos::join(dir, "letter.json") + " 的 body"};
    }
    if (reply->contains("error")) {
        const Json& e = (*reply)["error"];
        throw Error{e["code"].get<std::string>(), e["msg"].get<std::string>()};
    }
    return (*reply)["code"].get<int>();
}

static void withdraw(const Mailbox& mb, const aos::post::Mailbox& rb, const std::string& id,
                     std::set<std::string>& seen) {
    std::error_code ec;
    std::string t = aos::join(mb.tmp(), id);
    if (std::rename(aos::join(mb.fresh(), id).c_str(), t.c_str()) == 0) {
        fs::remove_all(t, ec);
        return;
    }
    // 在 cur/：正在跑，讓它跑完；回信已經到了就收掉，沒到的 kernel 之後看寄信的人不在了會撤回
    std::optional<std::string> n = find_reply(rb, id, seen);
    if (n && take(rb, *n)) {
        try {
            aos::post::finish(rb, *n, false);
        } catch (const Error&) {
        }
    }
}

int wait_reply(const Mailbox& mb, const std::string& id) {
    aos::post::Mailbox rb = aos::post::open(reply_box(mb));
    std::set<std::string> seen;
    sigset_t set;
    sigemptyset(&set);
    sigaddset(&set, SIGINT);
    sigaddset(&set, SIGTERM);
    sigaddset(&set, SIGHUP);
    while (true) {
        std::optional<std::string> n = find_reply(rb, id, seen);
        if (n && take(rb, *n)) {
            return relay(rb, *n);
        }
        if (!exists(aos::join(mb.fresh(), id)) && !exists(aos::join(mb.cur(), id)) &&
            !exists(aos::join(mb.done(), id)) && !find_reply(rb, id, seen)) {
            throw Error{code::LetterMissing, "信 " + id + " 在信箱 " + mb.root + " 裡不見了"};
        }
        timespec ts{0, 20 * 1000 * 1000};
        int sig = sigtimedwait(&set, nullptr, &ts);
        if (sig > 0) {
            withdraw(mb, rb, id, seen);
            return 128 + sig;
        }
    }
}

}  // namespace aos::llm_send
