// take.cpp：【take】處理者這一半——認領、讀信、回信、處理完；加上寄信人的撤回（說明見 aos/post.hpp）。
//
//   認領＝new/ 照處理順序（sort_letters），rename new/<名> → cur/<名>，成功的那個人才算（被撤、被別人拿走、cur/ 已有同名＝跳過）
//   處理完＝rename cur→tmp 再刪（cur/ 裡永遠不會出現刪一半的），keep＝rename cur→archive
//   撤回＝rename new→tmp 再刪；進了 cur/ 就撤不了（認領是界線）
//   壞信＝letter.json 不是 JSON 物件、sender／sent_at 不是字串、沒有 body、reply_to／in_reply_to 不是字串：
//     done 時丟掉，不通知寄信人（決定 27）。kind 不看（11-03 拿掉；讀到＝不認得的 key、忽略）；名字有序無序都不算壞
#include "common/common.hpp"

#include "aos/files.hpp"

#include <filesystem>

namespace aos::post {

// take／take_all 的入口：new/ 是資料夾；cur/ 沒有就建。
static void ready_to_take(const Mailbox& mb) {
    need_dir(mb.fresh());
    make_dir(mb.cur());
}

std::optional<std::string> take(const Mailbox& mb) {
    ready_to_take(mb);
    for (const std::string& name : names_in(mb.fresh())) {
        if (move(aos::join(mb.fresh(), name), aos::join(mb.cur(), name))) {
            return name;
        }
    }
    return std::nullopt;
}

std::vector<std::string> take_all(const Mailbox& mb) {
    ready_to_take(mb);
    std::vector<std::string> got;
    for (const std::string& name : names_in(mb.fresh())) {
        if (move(aos::join(mb.fresh(), name), aos::join(mb.cur(), name))) {
            got.push_back(name);
        }
    }
    return got;
}

std::optional<std::string> first_in_cur(const Mailbox& mb) {
    need_dir(mb.cur());
    std::vector<std::string> names = names_in(mb.cur());
    if (names.empty()) {
        return std::nullopt;
    }
    return names.front();
}

static std::string in_cur(const Mailbox& mb, const std::string& name) {
    std::string c = aos::join(mb.cur(), name);
    std::error_code ec;
    if (!std::filesystem::exists(std::filesystem::symlink_status(c, ec))) {   // 不是資料夾也算在（讀不到 letter.json＝壞信，done 丟掉）
        throw Error{code::LetterMissing, "letter not in cur/: " + c};
    }
    return c;
}

// 驗信封；好信回空字串，壞信回原因。
static std::string why_bad(const std::optional<Json>& doc) {
    if (!doc) {
        return "letter.json is missing, unreadable, or not JSON";
    }
    if (!doc->is_object()) {
        return "letter.json must be an object";
    }
    const char* strings[] = {"sender", "sent_at"};
    for (const char* k : strings) {
        if (!doc->contains(k) || !(*doc)[k].is_string()) {
            return std::string("missing ") + k + " (must be a string)";
        }
    }
    if (!doc->contains("body")) {
        return "missing body";
    }
    const char* optional_strings[] = {"reply_to", "in_reply_to"};
    for (const char* k : optional_strings) {
        if (doc->contains(k) && !(*doc)[k].is_string()) {
            return std::string(k) + " must be a string";
        }
    }
    return "";
}

Seen see(const Mailbox& mb, const std::string& name) {
    need_dir(mb.cur());
    std::string c = in_cur(mb, name);
    std::optional<Json> doc = aos::read_json(aos::join(c, "letter.json"));
    Seen r;
    r.reason = why_bad(doc);
    r.ok = r.reason.empty();
    if (r.ok) {
        r.letter = *doc;
    }
    return r;
}

std::optional<std::string> reply(const Mailbox& mb, const std::string& name, const Json& body) {
    Seen c = see(mb, name);
    if (!c.ok || !c.letter.contains("reply_to")) {
        return std::nullopt;
    }
    // 回信寄不出去時說清楚是「回信」、原信還在（不然只看到一個陌生信箱不在）
    try {
        Mailbox to = open(reply_to_abs(mb, c.letter["reply_to"].get<std::string>()));   // 相對的從信箱根拼（11-05）
        SendOpts opts;
        opts.in_reply_to = name;
        return send(to, body, opts);
    } catch (const Error& e) {
        throw Error{e.code, "cannot send the reply (reply_to of " + name + "); original left in cur/: " + e.msg};
    }
}

void done(const Mailbox& mb, const std::string& name, bool keep) {
    need_dir(mb.tmp());
    Seen c = see(mb, name);
    std::string from = aos::join(mb.cur(), name);
    if (keep && c.ok) {
        make_dir(mb.archive());
        if (!move(from, aos::join(mb.archive(), name))) {
            throw Error{code::WriteFailed, "cannot move into archive/ (same name already there, or letter gone): " + from};
        }
        return;
    }
    std::string t = aos::join(mb.tmp(), name);
    if (!move(from, t)) {
        throw Error{code::LetterMissing, "letter not in cur/: " + from};
    }
    drop(t);
}

bool regret(const Mailbox& mb, const std::string& name) {
    need_dir(mb.fresh());
    need_dir(mb.tmp());
    std::string t = aos::join(mb.tmp(), name);
    if (!move(aos::join(mb.fresh(), name), t)) {
        return false;
    }
    drop(t);
    return true;
}

}  // namespace aos::post
