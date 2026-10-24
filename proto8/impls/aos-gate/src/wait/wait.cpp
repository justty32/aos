// wait.cpp：【wait】等回信、撤信、轉交（說明見 wait.hpp）。
#include "wait/wait.hpp"

#include "aos/files.hpp"

#include <cstdio>
#include <filesystem>
#include <signal.h>

#include <unistd.h>

namespace fs = std::filesystem;

namespace aos::gate {

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

static int relay(const Mailbox& mb, const std::string& id) {
    std::string dir = aos::join(mb.done(), id);
    std::fflush(nullptr);
    copy_to(aos::join(dir, "stdout.txt"), 1);
    copy_to(aos::join(dir, "stderr.txt"), 2);
    std::optional<Json> reply = aos::kernel_llm::read_reply(aos::join(dir, "reply.json"));
    std::error_code ec;
    fs::remove_all(dir, ec);
    if (!reply) {
        throw Error{code::ReplyBad, "回信讀不懂：" + aos::join(dir, "reply.json")};
    }
    if (reply->contains("error")) {
        const Json& e = (*reply)["error"];
        throw Error{e["code"].get<std::string>(), e["msg"].get<std::string>()};
    }
    return (*reply)["code"].get<int>();
}

static void withdraw(const Mailbox& mb, const std::string& id) {
    std::error_code ec;
    std::string t = aos::join(mb.tmp(), id);
    if (std::rename(aos::join(mb.fresh(), id).c_str(), t.c_str()) == 0) {
        fs::remove_all(t, ec);
        return;
    }
    std::string d = aos::join(mb.done(), id);
    if (exists(d)) {
        fs::remove_all(d, ec);
    }
    // 在 cur/：正在跑，讓它跑完；kernel 之後看寄信的人不在了會清掉
}

int wait_reply(const Mailbox& mb, const std::string& id) {
    sigset_t set;
    sigemptyset(&set);
    sigaddset(&set, SIGINT);
    sigaddset(&set, SIGTERM);
    sigaddset(&set, SIGHUP);
    while (true) {
        if (exists(aos::join(mb.done(), id))) {
            return relay(mb, id);
        }
        if (!exists(aos::join(mb.fresh(), id)) && !exists(aos::join(mb.cur(), id)) &&
            !exists(aos::join(mb.done(), id))) {
            throw Error{code::LetterMissing, "信 " + id + " 在信箱 " + mb.root + " 裡不見了"};
        }
        timespec ts{0, 20 * 1000 * 1000};
        int sig = sigtimedwait(&set, nullptr, &ts);
        if (sig > 0) {
            withdraw(mb, id);
            return 128 + sig;
        }
    }
}

}  // namespace aos::gate
