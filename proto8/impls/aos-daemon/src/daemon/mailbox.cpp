// mailbox.cpp：【daemon】信箱模式（10-29，medium-plan § 二 4、§ 四 3、實作第 5 步；NORMS N-28 的 10-29 補、N-16；說明見 daemon.hpp）。
//
//   open_mailbox   起來時（建構子最後、adopt 之後）：aos::post::init 建四格（已在就沿用；$AOS_STACK 不在＝不建、MkdirFailed）、
//                  期望表 want_＝daemon.json 的 loops＋adopt 接回、不在上面的（設定記 null：只留名，不會被重起）、
//                  cur/ 裡的殘骸（上次認領了、還沒收完就死掉）記進 redo_——宣告式片段、重做無害，所以照建議重做
//   take_letters   每圈（stopped／paused 那圈不呼叫）：redo_（照名字順序）＋claim_all 認領到的（照名字順序），逐封 check 驗信封、
//                  apply_letter 驗 body 並套進 want_；壞信的原因記進 letter_warning_（最後一封壞信；沒有壞信的圈維持原值）
//   apply_letter   body 要是物件，只認 loops_added（物件，寫法同 loops_ctl）、loops_removed（名字的陣列），其他 key 忽略；
//                  檢查照 loops_ctl（check_lists：read_loops、撞名；相對 $ref 從 daemon 的 cwd 算——信收完就刪了，不能從信的資料夾算）。
//                  好的才套：先加（已在名單上的換設定、不在的接在尾巴）後減，後面的信蓋前面的
//   done_letters   對完表之後：好信有 reply_to 的回 {"applied": true}（壞信不回，決定 27）；全部 finish 收掉（不留 done/）。
//                  回信寄不出去、收不掉（信被別人拿走、寫不了）都不管：不另外通知（決定 27），也不讓 daemon 因此結束
#include "daemon/daemon.hpp"

#include "aos/files.hpp"

#include <algorithm>
#include <filesystem>

namespace aos::daemon {

void Daemon::open_mailbox() {
    std::error_code ec;
    if (!std::filesystem::is_directory(stack_, ec)) {   // 建 stack 只在 aos-exec 做（N-59 第 1 件）；init 是 mkdir -p，不能讓它順手建出來
        throw Error{code::MkdirFailed, "建不了信箱 " + mbox_path_ + "（$AOS_STACK 不在：" + stack_ + "）"};
    }
    aos::post::init(mbox_path_);
    mbox_ = aos::post::open(mbox_path_);
    want_ = loops_;
    for (auto& [n, c] : table_) {   // adopt 接回、daemon.json 沒有的：留在名單上，直到有信把它 loops_removed（方向題 1）
        if (!want_.contains(n)) {
            want_[n] = nullptr;
        }
    }
    for (const auto& e : std::filesystem::directory_iterator(mbox_.cur(), ec)) {
        std::string id = e.path().filename().string();
        if (!id.empty() && id[0] != '.') {   // . 開頭不算信（N-05，同 aos-post）
            redo_.push_back(id);
        }
    }
    std::sort(redo_.begin(), redo_.end());
}

Daemon::Letters Daemon::take_letters() {
    std::vector<std::string> ids;
    ids.swap(redo_);
    for (std::string& id : aos::post::claim_all(mbox_)) {
        ids.push_back(std::move(id));
    }
    Letters got;
    for (const std::string& id : ids) {
        std::optional<std::string> bad;
        try {
            aos::post::Checked c = aos::post::check(mbox_, id);
            bad = c.ok ? apply_letter(c.letter["body"]) : std::optional<std::string>(c.reason);
        } catch (const Error&) {
            continue;   // 不在 cur/ 了（被人拿走、刪掉）：沒有這封
        }
        if (bad) {
            letter_warning_ = "信 " + id + " 不採用：" + *bad;
        }
        got.push_back({id, !bad});
    }
    return got;
}

std::optional<std::string> Daemon::apply_letter(const Json& body) {
    if (!body.is_object()) {
        return std::string("body 要是物件");
    }
    Json doc = Json::object();
    for (const char* k : {"loops_added", "loops_removed"}) {   // 只認這兩個；沒有整份的 loops（信是增減，整份宣告留給 ctl 模式）
        if (body.contains(k)) {
            doc[k] = body[k];
        }
    }
    aos::Resolved where;
    where.base_dir = cwd_;
    std::optional<std::string> bad;
    try {
        bad = check_lists(doc, where);
    } catch (const Error& e) {
        bad = "指示詞解不開：" + e.msg;
    }
    if (bad) {
        return bad;
    }
    if (doc.contains("loops_added")) {
        for (auto& [n, spec] : doc["loops_added"].items()) {
            want_[n] = spec;   // 已在名單上的換設定（已在跑的不看設定變了沒，同 N-54）、不在的接在尾巴
        }
    }
    if (doc.contains("loops_removed")) {
        for (const Json& n : doc["loops_removed"]) {
            want_.erase(n.get<std::string>());
        }
    }
    return std::nullopt;
}

void Daemon::done_letters(const Letters& got) {
    for (const auto& [id, ok] : got) {
        try {
            if (ok) {
                aos::post::reply(mbox_, id, Json::object({{"applied", true}}));   // 沒寫 reply_to＝不回
            }
        } catch (const Error&) {
        }
        try {
            aos::post::finish(mbox_, id, false);
        } catch (const Error&) {
        }
    }
}

}  // namespace aos::daemon
