// send.cpp：【send】寄信人這一半——身分、信號、寄一封（說明見 aos/post.hpp）。
//
// 寄＝只用 Linux 的原子動作（N-16、medium-plan § 二 3）：
//   1. mkdir tmp/<信號>：成功就是自己的；撞名（EEXIST）換一個信號再來
//   2. 在裡面寫 letter.json（在 tmp/ 裡寫，處理者不看這格，不必再暫存改名；write_json 照樣先寫 .letter.json.tmp）
//   3. rename tmp/<信號> → new/<信號>：資料夾改名是原子的，處理者看到就是完整的
// 寫到一半死掉：殘骸留在 tmp/，處理者不碰；收屍歸寄信人的上一層（決定 23），這裡不做。
//
// 有順序的投遞（ordered，medium-plan § 三、N-16）：1、2 照舊（信先在 tmp/ 寫好，鎖握的時間短一點），然後
//   3'. 拿 <信箱>/order.lock/（aos-lock，持有者＝自己；拿不到每 20 毫秒再試、持有者死了就收屍）
//   4'. 讀 order.json 的 N（沒有＝0）→ order.json 先寫 N+1（N-05 暫存改名）→ rename tmp/<信號> → new/<N+1 零填 12 位>.<信號>
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

std::string sender() {
    const char* ws = std::getenv("AOS_WS");
    if (ws != nullptr && ws[0] != '\0') {
        return aos::abspath(ws);
    }
    const char* home = std::getenv("HOME");
    if (home != nullptr && home[0] != '\0') {
        return aos::abspath(home);
    }
    return "/";   // HOME 也沒設（極少見）：根目錄。不查 passwd——-static-pie 的執行檔叫 getpwuid 要在執行時載 glibc 的 NSS
}

// 一個時間點（UTC 奈秒）→ 信號與 sent_at：兩個取自同一刻（medium-plan § 二 2「<sent_at 的 UTC 奈秒 20 位>」）。
struct Stamp {
    std::string id;
    std::string sent_at;
};

static Stamp stamp() {
    long long ns = aos::utc_now_ns();
    return Stamp{aos::unique_id(ns), aos::utc_ms_at(ns)};   // 信號與 sent_at 的產生法在 aos-util（10-30 收過去）
}

// order.json 的 N：沒有＝0；在但讀不懂丟 OrderBad。
static long long read_counter(const std::string& path) {
    int err = 0;
    std::optional<std::string> text = aos::read_file(path, err);
    if (!text) {
        if (err == ENOENT) {
            return 0;
        }
        throw Error{code::OrderBad, "讀不了 " + path + "：" + std::strerror(err)};
    }
    std::optional<Json> doc = aos::read_json(path);
    if (!doc || !doc->is_object() || !doc->contains("counter_letters") || !aos::is_count((*doc)["counter_letters"])) {
        throw Error{code::OrderBad, path + " 要是 {\"counter_letters\": 非負整數}"};
    }
    return (*doc)["counter_letters"].get<long long>();
}

// 3'～5'：信已經寫在 tmp/<信號>（t）。回 new/ 裡的名字。
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
            throw Error{code::WriteFailed, "改名不了 " + t + " → " + to + "：" + std::strerror(errno)};   // 缺一個號
        }
    } catch (...) {
        aos::lock::release(lock_dir);
        drop(t);
        throw;
    }
    aos::lock::release(lock_dir);
    return name;
}

std::string send(const Mailbox& mb, const Json& body, const SendOpts& opts) {
    // 1. mkdir tmp/<信號>（撞名換一個；同一奈秒同一行程才會撞）
    Stamp s;
    std::string t;
    for (int i = 0;; ++i) {
        s = stamp();
        t = aos::join(mb.tmp(), s.id);
        if (mkdir(t.c_str(), 0777) == 0) {
            break;
        }
        int e = errno;
        if (e != EEXIST || i >= 100) {
            throw Error{code::MkdirFailed, "建不了 " + t + "：" + std::strerror(e)};
        }
    }
    // 1'. 另放的檔（在 tmp/ 裡，處理者還看不到）
    for (const auto& [name, from] : opts.files) {
        if (name.empty() || name[0] == '.' || name.find('/') != std::string::npos || name == "letter.json") {
            drop(t);
            throw Error{code::ArgumentsBad, "信裡另放的檔名要是單純的名字、不是 letter.json：" + name};
        }
        std::error_code ec;
        std::filesystem::copy_file(from, aos::join(t, name), ec);
        if (ec) {
            drop(t);
            throw Error{code::WriteFailed, "複製不了 " + from + " → " + aos::join(t, name) + "：" + ec.message()};
        }
    }
    // 2. 寫 letter.json
    Json letter = Json::object();
    letter["kind"] = "letter";
    letter["sender"] = sender();
    letter["sent_at"] = s.sent_at;
    if (opts.reply_to) {
        letter["reply_to"] = aos::abspath(*opts.reply_to);
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
        throw Error{code::WriteFailed, "改名不了 " + t + " → " + n + "：" + std::strerror(e)};
    }
    return s.id;
}

}  // namespace aos::post
