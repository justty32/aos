// send.cpp：【send】寄信人這一半——驗信箱、信件名稱、寄一封（說明見 aos/post.hpp）。
//
// 寄＝只用 Linux 的原子動作（N-16、medium-plan § 二 3）：
//   0. 入口檢查（C-53 (a)）：信箱的 tmp/、new/ 是資料夾（MailboxMissing）、對自己可寫（access W_OK|X_OK，照字面驗、不試寫；MailboxBad）；
//      reply_to 同一套驗法；in_reply_to、自己給的名字照 check_name，自己給的名字還不得像有序名（ArgumentsBad）
//   1. mkdir tmp/<名>：成功就是自己的；撞名（EEXIST）——預設名換一個再來，自己給的名字丟 LetterExists
//   2. 在裡面寫 letter.json（在 tmp/ 裡寫，處理者不看這格，不必再暫存改名；write_json 照樣先寫 .letter.json.tmp）
//   3. rename tmp/<名> → new/<名>：資料夾改名是原子的，處理者看到就是完整的（new/ 已有同名的＝LetterExists）
// 寫到一半死掉：殘骸留在 tmp/，處理者不碰；收屍歸寄信人的上一層（決定 23），這裡不做。
//
// 有順序的投遞（ordered，medium-plan § 三、N-16）：1、2 照舊（信先在 tmp/ 寫好，鎖握的時間短一點），然後
//   3'. 拿 <信箱>/order.lock/（aos-lock，持有者＝自己；拿不到每 20 毫秒再試、持有者死了就收屍）
//   4'. 讀 order.json 的 N（沒有＝0）→ order.json 先寫 N+1（N-05 暫存改名）→ rename tmp/<名> → new/<N+1 零填 12 位>.<名>
//   5'. 放鎖
//   跟 plan 的順序（先 rename、再寫 N+1）差在 4' 的兩步對調：死在兩步之間時，plan 的順序下一個人會拿到同一個號（重號），
//   這裡的順序只會缺一個號（信留在 tmp/）。鎖握到 rename 完，所以到 new/ 的順序＝取號順序。
#include "common/common.hpp"

#include "aos/files.hpp"
#include "aos/lock.hpp"
#include "aos/proc.hpp"

#include <filesystem>

#include <cerrno>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>

#include <sys/stat.h>
#include <unistd.h>

namespace aos::post {

// 一個時間點（UTC 奈秒）→ 預設的信件名稱與 sent_at：兩個取自同一刻（medium-plan § 二 2「<sent_at 的 UTC 奈秒 20 位>」）。
struct Stamp {
    std::string id;
    std::string sent_at;
};

static Stamp stamp() {
    long long ns = aos::utc_now_ns();
    return Stamp{aos::unique_id(ns), aos::utc_ms_at(ns)};   // 名字與 sent_at 的產生法在 aos-util（10-30 收過去）
}

// order.json 的 N：沒有＝0；在但讀不懂丟 OrderBad。
static long long read_counter(const std::string& path) {
    int err = 0;
    std::optional<std::string> text = aos::read_file(path, err);
    if (!text) {
        if (err == ENOENT) {
            return 0;
        }
        throw Error{code::OrderBad, "cannot read " + path + ": " + std::strerror(err)};
    }
    std::optional<Json> doc = aos::read_json(path);
    if (!doc || !doc->is_object() || !doc->contains("counter_letters") || !aos::is_count((*doc)["counter_letters"])) {
        throw Error{code::OrderBad, path + " must be {\"counter_letters\": non-negative integer}"};
    }
    return (*doc)["counter_letters"].get<long long>();
}

// 3'～5'：信已經寫在 tmp/<名>（t）。回 new/ 裡的名字。
static std::string post_ordered(const Mailbox& mb, const std::string& t, const std::string& id) {
    std::string lock_dir = aos::join(mb.root, "order.lock");
    aos::lock::Holder h = aos::lock::holder_of(0);
    h.note = "aos-post send --ordered";
    try {
        aos::lock::acquire(lock_dir, h, -1);
    } catch (const Error&) {
        drop(t);
        throw;
    }
    std::string name;
    try {
        std::string order = aos::join(mb.root, "order.json");
        long long n = read_counter(order) + 1;
        char seq[32];
        std::snprintf(seq, sizeof seq, "%012lld", n);
        name = std::string(seq) + "." + id;
        Json doc = Json::object();
        doc["counter_letters"] = n;
        std::optional<std::string> err = aos::write_json(order, doc);
        if (err) {
            throw Error{code::WriteFailed, *err};
        }
        std::string to = aos::join(mb.fresh(), name);
        if (std::rename(t.c_str(), to.c_str()) != 0) {
            int e = errno;
            if (e == EEXIST || e == ENOTEMPTY) {
                throw Error{code::LetterExists, "new/ already has a letter with this name: " + to};   // 缺一個號
            }
            throw Error{code::WriteFailed, "cannot rename " + t + " -> " + to + ": " + std::strerror(e)};   // 缺一個號
        }
    } catch (...) {
        aos::lock::release(lock_dir);
        drop(t);
        throw;
    }
    aos::lock::release(lock_dir);
    return name;
}

// 信箱能不能寄（send 的入口檢查；reply_to 也照這套）。
static void check_sendable(const Mailbox& mb) {
    const std::string parts[] = {mb.tmp(), mb.fresh()};
    for (const std::string& p : parts) {
        need_dir(p);
    }
    for (const std::string& p : parts) {
        if (access(p.c_str(), W_OK | X_OK) != 0) {
            throw Error{code::MailboxBad, p.substr(mb.root.size() + 1) + "/ is not writable: " + p};
        }
    }
}

std::string send(const Mailbox& mb, const Json& body, const SendOpts& opts) {
    check_sendable(mb);
    std::optional<std::string> reply_to;
    if (opts.reply_to) {
        Mailbox r = open(*opts.reply_to);
        check_sendable(r);
        reply_to = reply_to_rel(mb, r.root);   // 相對這個信箱的根（11-05）
    }
    if (opts.in_reply_to) {
        check_name(*opts.in_reply_to);
    }
    if (opts.name) {
        check_name(*opts.name);
        if (is_ordered(*opts.name)) {
            throw Error{code::ArgumentsBad, "a given letter name must not look like an ordered name (12 digits then .): " + *opts.name};
        }
    }
    std::string who = aos::identity();   // aos-util：$AOS_WS ＞ $AOS_STACK ＞ $AOS_CF ＞ cwd（cwd 拿不到丟 Internal）
    // 1. mkdir tmp/<名>（預設名撞名換一個；同一奈秒同一行程才會撞）
    Stamp s;
    std::string t;
    for (int i = 0;; ++i) {
        s = stamp();
        if (opts.name) {
            s.id = *opts.name;
        }
        t = aos::join(mb.tmp(), s.id);
        if (mkdir(t.c_str(), 0777) == 0) {
            break;
        }
        int e = errno;
        if (e == EEXIST && opts.name) {
            throw Error{code::LetterExists, "tmp/ already has an entry with this name: " + t};
        }
        if (e != EEXIST || i >= 100) {
            throw Error{code::MkdirFailed, "cannot create " + t + ": " + std::strerror(e)};
        }
    }
    // 1'. 另放的檔（在 tmp/ 裡，處理者還看不到）
    for (const auto& [name, from] : opts.files) {
        if (name.empty() || name[0] == '.' || name.find('/') != std::string::npos || name == "letter.json") {
            drop(t);
            throw Error{code::ArgumentsBad, "attached file name must be a plain name other than letter.json: " + name};
        }
        std::error_code ec;
        std::filesystem::copy_file(from, aos::join(t, name), ec);
        if (ec) {
            drop(t);
            throw Error{code::WriteFailed, "cannot copy " + from + " -> " + aos::join(t, name) + ": " + ec.message()};
        }
    }
    // 2. 寫 letter.json（沒有 kind，11-03）
    Json letter = Json::object();
    letter["sender"] = who;
    letter["sent_at"] = s.sent_at;
    if (reply_to) {
        letter["reply_to"] = *reply_to;
    }
    if (opts.in_reply_to) {
        letter["in_reply_to"] = *opts.in_reply_to;
    }
    letter["body"] = body;
    std::optional<std::string> err = aos::write_json(aos::join(t, "letter.json"), letter);
    if (err) {
        drop(t);
        throw Error{code::WriteFailed, *err};
    }
    if (opts.ordered) {
        return post_ordered(mb, t, s.id);
    }
    // 3. rename 進 new/
    std::string n = aos::join(mb.fresh(), s.id);
    if (std::rename(t.c_str(), n.c_str()) != 0) {
        int e = errno;
        drop(t);
        if (e == EEXIST || e == ENOTEMPTY) {
            throw Error{code::LetterExists, "new/ already has a letter with this name: " + n};
        }
        throw Error{code::WriteFailed, "cannot rename " + t + " -> " + n + ": " + std::strerror(e)};
    }
    return s.id;
}

}  // namespace aos::post
