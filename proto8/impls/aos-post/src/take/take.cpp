// take.cpp：【take】處理者這一半——認領、讀信、回信、處理完；加上寄信人的撤回（說明見 aos/post.hpp）。
//
//   認領＝rename new/<信號> → cur/<信號>，成功的那個人才算（被撤、被別人拿走＝跳過）
//   處理完＝rename cur→tmp 再刪（cur/ 裡永遠不會出現刪一半的），keep＝rename cur→done
//   撤回＝rename new→tmp 再刪；進了 cur/ 就撤不了（認領是界線）
//   壞信＝letter.json 不是 JSON 物件、缺必填（kind／sender／sent_at／body）、型別不對：finish 時丟掉，不通知寄信人（決定 27）
#include "common/common.hpp"

#include "aos/files.hpp"

#include <filesystem>

namespace aos::post {

std::optional<std::string> claim(const Mailbox& mb) {
    for (const std::string& id : names_in(mb.fresh())) {
        if (move(aos::join(mb.fresh(), id), aos::join(mb.cur(), id))) {
            return id;
        }
    }
    return std::nullopt;
}

std::vector<std::string> claim_all(const Mailbox& mb) {
    std::vector<std::string> got;
    for (const std::string& id : names_in(mb.fresh())) {
        if (move(aos::join(mb.fresh(), id), aos::join(mb.cur(), id))) {
            got.push_back(id);
        }
    }
    return got;
}

static std::string in_cur(const Mailbox& mb, const std::string& id) {
    std::string c = aos::join(mb.cur(), id);
    std::error_code ec;
    if (!std::filesystem::exists(std::filesystem::symlink_status(c, ec))) {   // 不是資料夾也算在（讀不到 letter.json＝壞信，finish 丟掉）
        throw Error{code::LetterMissing, "信不在 cur/：" + c};
    }
    return c;
}

// 驗信封；好信回空字串，壞信回原因。
static std::string why_bad(const std::optional<Json>& doc) {
    if (!doc) {
        return "letter.json 不在、讀不了或不是 JSON";
    }
    if (!doc->is_object()) {
        return "letter.json 要是物件";
    }
    if (!doc->contains("kind") || !(*doc)["kind"].is_string() || (*doc)["kind"].get<std::string>() != "letter") {
        return "kind 要是 \"letter\"";
    }
    const char* strings[] = {"sender", "sent_at"};
    for (const char* k : strings) {
        if (!doc->contains(k) || !(*doc)[k].is_string()) {
            return std::string("缺 ") + k + "（要是字串）";
        }
    }
    if (!doc->contains("body")) {
        return "缺 body";
    }
    const char* optional_strings[] = {"reply_to", "in_reply_to"};
    for (const char* k : optional_strings) {
        if (doc->contains(k) && !(*doc)[k].is_string()) {
            return std::string(k) + " 要是字串";
        }
    }
    return "";
}

Checked check(const Mailbox& mb, const std::string& id) {
    std::string c = in_cur(mb, id);
    std::optional<Json> doc = aos::read_json(aos::join(c, "letter.json"));
    Checked r;
    r.reason = why_bad(doc);
    r.ok = r.reason.empty();
    if (r.ok) {
        r.letter = *doc;
    }
    return r;
}

std::optional<std::string> reply(const Mailbox& mb, const std::string& id, const Json& body) {
    Checked c = check(mb, id);
    if (!c.ok || !c.letter.contains("reply_to")) {
        return std::nullopt;
    }
    Mailbox to = open(c.letter["reply_to"].get<std::string>());
    SendOpts opts;
    opts.in_reply_to = id;
    return send(to, body, opts);
}

void finish(const Mailbox& mb, const std::string& id, bool keep) {
    Checked c = check(mb, id);
    std::string from = aos::join(mb.cur(), id);
    if (keep && c.ok) {
        std::error_code ec;
        std::filesystem::create_directories(mb.done(), ec);
        if (!is_dir(mb.done())) {
            throw Error{code::MkdirFailed, "建不了 " + mb.done() + (ec ? "：" + ec.message() : "")};
        }
        if (!move(from, aos::join(mb.done(), id))) {
            throw Error{code::WriteFailed, "搬不進 done/（同名的已經在、或信不見了）：" + from};
        }
        return;
    }
    std::string t = aos::join(mb.tmp(), id);
    if (!move(from, t)) {
        throw Error{code::LetterMissing, "信不在 cur/：" + from};
    }
    drop(t);
}

bool withdraw(const Mailbox& mb, const std::string& id) {
    std::string t = aos::join(mb.tmp(), id);
    if (!move(aos::join(mb.fresh(), id), t)) {
        return false;
    }
    drop(t);
    return true;
}

}  // namespace aos::post
