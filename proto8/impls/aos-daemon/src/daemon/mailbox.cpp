// mailbox.cpp：【daemon】信箱 procs_ctl_mailbox（10-29，medium-plan § 二 4、§ 四 3；NORMS N-28 的 10-29 補、N-16；11-03 改名 procs、多 stop／start；說明見 daemon.hpp）。
// 跟 procs_ctl 可以同時開；信改的是「底」want_／stopped_，procs_ctl 每圈疊在底上（tend）。
//
//   open_mailbox   起來時（建構子最後、adopt 之後）：aos::post::init 建 tmp/ new/ cur/（已在就沿用；$AOS_STACK 不在＝不建、MkdirFailed）、
//                  底 want_（建構子已設成 daemon.json 的 procs）再加 adopt 接回、不在上面的（設定記 null：只留名，不會被重起；它結束時 drop 從 want_ 拿掉）、
//                  cur/ 裡的殘骸（上次認領了、還沒收完就死掉）記進 redo_——片段、重做無害，所以照建議重做
//   take_letters   每圈（stop／pause 那圈不呼叫）：redo_（照處理順序）＋take_all 認領到的（照處理順序），逐封 see 驗信封、
//                  apply_letter 驗 body 並套進底；壞信的原因記進 mailbox_warning_（state_flux 的最後一封壞信；沒有壞信的圈維持原值）
//                  這圈拿到信（好壞都算）就更新 state_flux 的 responded_at；pause／stop 那圈照舊不認領。
//   apply_letter   body 要是物件，只認 procs_added（物件，寫法同 procs_ctl）、procs_removed、procs_stopped、procs_started、procs_slept、procs_woken（11-05，名字的陣列），其他 key 忽略；
//                  檢查照 procs_ctl（check_lists；相對 $ref 從 daemon 的 cwd 算——信收完就刪了，不能從信的資料夾算）；不按起法拒信。
//                  另認 ping：有寫就必須是 true，只回 applied、不改底；跟其他 key 一起寫時其他 key 照常套。
//                  好的才套：procs_added（已在名單上的換設定、不在的接在尾巴）→procs_removed（名單與 stopped 集合都拿掉）→procs_stopped 加進 stopped 集合→
//                  procs_started 從 stopped 集合拿掉（同名兩邊都寫＝起）；後面的信蓋前面的
//   done_letters   對完表之後：好信有 reply_to 的回 {"applied": true}（壞信不回，決定 27）；全部 done 收掉（不留 archive/）。
//                  回信寄不出去、收不掉（信被別人拿走、寫不了）都不管：不另外通知（決定 27），也不讓 daemon 因此結束
#include "daemon/daemon.hpp"

#include "aos/util/files.hpp"

namespace aos::daemon {

void Daemon::open_mailbox() {
    if (!aos::is_dir(stack_)) {   // 建 stack 只在 aos-exec 做（N-59 第 1 件）；init 是 mkdir -p，不能讓它順手建出來
        throw Error{code::MkdirFailed, "cannot create mailbox " + mbox_path_ + " ($AOS_STACK is missing: " + stack_ + ")"};
    }
    aos::post::init(mbox_path_);
    mbox_ = aos::post::open(mbox_path_);
    for (auto& [n, c] : table_) {   // adopt 接回、daemon.json 沒有的：留在名單上，直到有信把它 procs_removed、或它結束（方向題 1；11-02）
        if (!want_.contains(n)) {
            want_[n] = nullptr;
        }
    }
    for (const std::string& name : aos::names_in(mbox_.cur())) {
        redo_.push_back(name);   // 非隱藏名字，同 aos-post 的信件規則（N-05）
    }
    aos::post::sort_letters(redo_);   // 處理順序同 aos-post 的 take（有序在前）
}

Daemon::Letters Daemon::take_letters() {
    std::vector<std::string> names;
    names.swap(redo_);
    try {
        for (std::string& name : aos::post::take_all(mbox_)) {
            names.push_back(std::move(name));
        }
    } catch (const Error& e) {
        // 11-05 第二輪：new/ 唯讀等認領不了＝原本整台 daemon 退 1；改成記進 state_flux 的 mailbox_warning、下一圈再試
        mailbox_warning_ = "cannot take letters: " + e.code + " " + e.msg;
    }
    if (!names.empty()) {
        responded();
    }
    Letters got;
    for (const std::string& id : names) {
        std::optional<std::string> bad;
        try {
            aos::post::Seen c = aos::post::see(mbox_, id);
            bad = c.ok ? apply_letter(c.letter["body"]) : std::optional<std::string>(c.reason);
        } catch (const Error&) {
            continue;   // 不在 cur/ 了（被人拿走、刪掉）：沒有這封
        }
        if (bad) {
            mailbox_warning_ = "letter " + id + " rejected: " + *bad;
        }
        got.push_back({id, !bad});
    }
    return got;
}

std::optional<std::string> Daemon::apply_letter(const Json& body) {
    if (!body.is_object()) {
        return std::string("body must be an object");
    }
    if (body.contains("ping") && (!body["ping"].is_boolean() || body["ping"] != true)) {
        return std::string("ping must be true");
    }
    Json doc = Json::object();
    // 名單增減與起停睡醒；沒有整份的 procs（信是增減，整份宣告留給 procs_ctl）
    for (const char* k : {"procs_added", "procs_removed", "procs_stopped", "procs_started", "procs_slept", "procs_woken"}) {
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
        bad = "cannot resolve directives: " + e.msg;
    }
    if (bad) {
        return bad;
    }
    // 在副本上套：結構驗過後，各種起法一視同仁
    Json w = want_;
    Names s = stopped_;
    Names z = slept_;   // 11-05 sleep／wake：procs_slept 加進 slept 集合、procs_woken 拿掉（同名兩邊都寫＝醒）
    if (doc.contains("procs_added")) {
        for (auto& [n, spec] : doc["procs_added"].items()) {
            w[n] = spec;   // 已在名單上的換設定（已在跑的不看設定變了沒，同 N-54；stopped 的照停）、不在的接在尾巴
        }
    }
    if (doc.contains("procs_removed")) {
        for (const Json& n : doc["procs_removed"]) {
            w.erase(n.get<std::string>());
            s.erase(n.get<std::string>());
            z.erase(n.get<std::string>());
        }
    }
    if (doc.contains("procs_stopped")) {
        for (const Json& n : doc["procs_stopped"]) {
            s.insert(n.get<std::string>());
        }
    }
    if (doc.contains("procs_started")) {
        for (const Json& n : doc["procs_started"]) {
            s.erase(n.get<std::string>());
        }
    }
    if (doc.contains("procs_slept")) {
        for (const Json& n : doc["procs_slept"]) {
            z.insert(n.get<std::string>());
        }
    }
    if (doc.contains("procs_woken")) {
        for (const Json& n : doc["procs_woken"]) {
            z.erase(n.get<std::string>());
        }
    }
    want_ = std::move(w);
    stopped_ = std::move(s);
    slept_ = std::move(z);
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
            aos::post::done(mbox_, id, false);
        } catch (const Error&) {
        }
    }
}

}  // namespace aos::daemon
