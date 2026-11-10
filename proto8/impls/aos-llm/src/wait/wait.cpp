// wait.cpp：【wait】收回信、等回信、撤信（說明見 wait.hpp）。
#include "wait/wait.hpp"

#include "send/send.hpp"

#include "aos/util/files.hpp"

#include <cstdio>
#include <filesystem>
#include <optional>
#include <set>
#include <signal.h>
#include <sys/stat.h>

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

static int deliver(const aos::post::Mailbox& rb, const std::string& n, const std::string& id, bool full) {
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
        if (full) {
            std::string line = aos::dumps(*reply) + "\n";
            std::fwrite(line.data(), 1, line.size(), stdout);
            std::fflush(stdout);
        }
        const Json& e = (*reply)["error"];
        throw Error{e["code"].get<std::string>(), e["msg"].get<std::string>()};
    }
    Json output = (*reply)["message"];
    if (full) {
        output = *reply;
        output["letter"] = id;
    }
    std::string line = aos::dumps(output) + "\n";
    std::fwrite(line.data(), 1, line.size(), stdout);
    std::fflush(stdout);
    return 0;
}

// kernel 寫得進回信信箱嗎（只看權限位；kernel 的身分＝owner 那份檔的 uid／gid，補充群組看不到）。寫得進或看不出＝空字串，
// 寫不進＝哪一格、為什麼（英文）。root（uid 0）一律當寫得進。
static std::string unwritable_for(const std::string& owner, const aos::post::Mailbox& rb) {
    struct stat who{};
    if (::stat(owner.c_str(), &who) != 0 || who.st_uid == 0) {
        return "";
    }
    for (const std::string& d : {rb.tmp(), rb.fresh()}) {
        struct stat st{};
        if (::stat(d.c_str(), &st) != 0) {
            return "";
        }
        mode_t need = 0;
        if (st.st_uid == who.st_uid) {
            need = S_IWUSR | S_IXUSR;
        } else if (st.st_gid == who.st_gid) {
            need = S_IWGRP | S_IXGRP;
        } else {
            need = S_IWOTH | S_IXOTH;
        }
        if ((st.st_mode & need) != need) {
            char mode[8];
            std::snprintf(mode, sizeof mode, "%03o", (unsigned)(st.st_mode & 0777));
            return d + " is mode " + mode + ", owner uid " + std::to_string(st.st_uid) + ", kernel uid " +
                   std::to_string(who.st_uid);
        }
    }
    return "";
}

int recv(const std::string& box, const std::string& name, bool full, bool quiet) {
    aos::post::check_name(name);   // 不合 ArgumentsBad
    aos::post::Mailbox rb = aos::post::open(box);   // 不是資料夾＝MailboxMissing
    std::set<std::string> seen;
    std::optional<std::string> n = find_reply(rb, name, seen);
    if (n && aos::post::take(rb, *n)) {
        return deliver(rb, *n, name, full);
    }
    // 11-10（坑-102）：還沒到時，看得出不對勁就多印一行提醒說是哪一種（照舊退 10）：
    //   ① 信還在 kernel 的 new/、cur/，而 kernel 沒在跑；② kernel（它 stack 的 state.json 的主人）照權限位寫不進 BOX 的 tmp/、new/。
    // 「信已不在 kernel、BOX 也沒有」不報：回信已經收過一次（再叫 recv）也長這樣，分不出來。
    // 沒設 AOS_LLM_KERNEL（或不是資料夾）＝不判斷，照舊安靜退 10。--quiet＝不判斷不印（每拍輪詢的呼叫者；11-10 TX3：kernel 沒跑時每拍一行會灌爆 stderr.txt）。
    if (quiet) {
        return 10;
    }
    try {
        Mailbox mb = kernel();
        bool queued = exists(aos::join(mb.fresh(), name)) || exists(aos::join(mb.cur(), name));
        std::string why = queued ? idle_reason(mb) : std::string();
        if (!why.empty()) {
            aos::warn("aos-llm", "no reply for " + name + " yet: " + aos::dirname(mb.root) + ": " + why +
                                 "; the reply comes once it runs");
        }
        std::string blocked = unwritable_for(aos::join(aos::dirname(mb.root), "state.json"), rb);
        if (!blocked.empty()) {
            aos::warn("aos-llm", "no reply for " + name + ": the llm kernel cannot deliver into " + rb.root + " (" + blocked +
                                 "); give it write access (see cmd/aos-sandbox/root/setup.sh --mailbox)");
        }
    } catch (const Error&) {
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
            return deliver(rb, *n, id, full);
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
