// serve.cpp：【serve】鎖信箱、清理寄件人已離開的信、按宣告級數留 high 格與串起每輪流程（說明見 serve.hpp）。
#include "serve/serve.hpp"

#include "aos/util/files.hpp"
#include "aos/util/signals.hpp"
#include "aos/util/tick.hpp"

#include <cerrno>
#include <chrono>
#include <cstring>
#include <filesystem>

#include <fcntl.h>
#include <sys/file.h>

namespace fs = std::filesystem;

namespace aos::llm_kernel {

namespace {

// 窗 $AOS_STACK/endpoints.json（11-05 feat-proto 件 2）：包的屬性表，給人與 aos-llm ls 挑代號；跟現有的一樣就不寫（N-05 暫存改名）。
void write_window(const std::string& stack, const Json& w) {
    std::string path = aos::join(stack, "endpoints.json");
    std::optional<Json> old = aos::read_json(path);
    if (old && *old == w) {
        return;
    }
    std::optional<std::string> err = aos::write_json(path, w);
    if (err) {
        throw Error{code::WriteFailed, *err};
    }
}

}  // namespace

void Server::lock() {
    std::string path = aos::join(mb_.root, ".flock");   // 10-29 改名（原 .lock；.lock/ 留給 N-15 的資料夾鎖）
    lock_fd_ = open(path.c_str(), O_RDWR | O_CREAT | O_CLOEXEC, 0644);
    if (lock_fd_ < 0) {
        throw Error{code::LockFailed, "cannot open " + path + ": " + std::strerror(errno)};
    }
    if (flock(lock_fd_, LOCK_EX | LOCK_NB) != 0) {
        throw Error{code::LockFailed, "mailbox " + mb_.root + " is locked by another kernel (one kernel per mailbox at a time)"};
    }
}

// 寄信的人不在了的（<信>/sender.flock 在、但沒人鎖著）：tmp/ 直接刪；new/ 先改名回 tmp/ 再刪（跟撤信同一個做法，不會跟認領撞）。
// 沒有 sender.flock＝非同步寄的（aos-llm send、aos-post send）或還在建鎖檔：不判存活、不碰（11-04 衝突 2 (a)）。
void Server::sweep() {
    std::vector<std::string> tmps;
    std::error_code ec;
    for (const fs::directory_entry& e : fs::directory_iterator(mb_.tmp(), ec)) {
        tmps.push_back(e.path().filename().string());
    }
    for (const std::string& n : tmps) {
        std::string dir = aos::join(mb_.tmp(), n);
        bool writing = !n.empty() && n[0] == '.';
        if (writing && !fs::exists(aos::join(dir, "letter.json"), ec)) {
            continue;   // ask 鎖好才寫 letter.json：還沒有＝可能正在建鎖檔、上鎖，不碰
        }
        if (has_sender(dir) && !sender_alive(dir)) {
            aos::remove_tree(dir);
        }
    }
    for (const std::string& id : aos::names_in(mb_.fresh(), true)) {
        std::string dir = aos::join(mb_.fresh(), id);
        if (has_sender(dir) && !sender_alive(dir)) {
            std::string t = aos::join(mb_.tmp(), id);
            if (aos::move(dir, t)) {
                aos::remove_tree(t);
            }
        }
    }
}

int Server::run() {
    host_ = find_host();   // 沒 AOS_DAEMON＝DaemonMissing、daemon 沒開 ctl 信箱＝MailboxMissing（kernel 自己的錯，退 1；信箱還沒建）
    for (const std::string& d : {mb_.root, mb_.tmp(), mb_.fresh(), mb_.cur()}) {
        aos::make_dir(d);
    }
    lock();
    q_ = read_queue(stack_);
    q_.runs += 1;
    used_ = read_used(stack_, budget_.window);
    table_ = read_table(host_);
    write_window(stack_, window_of(cfg_.packs));
    collect();
    sweep();
    std::optional<long long> now_tick = aos::now_tick();
    long long now_ms = aos::utc_now_epoch_ms();
    std::vector<Waiting> ws = scan(now_ms, now_tick);
    order(ws, cfg_.aging_ticks);

    int got = aos::take_signal();
    if (got == 0) {
        long long n = 0;   // 這次新掛的
        const int high_level = parse_priority(Json("high")).level;
        for (const Waiting& w : ws) {
            if (spent(budget_, used_, n + busy_)) {   // 這一窗額度到頂
                if (budget_.wait) {
                    break;   // 留在 new/ 等下一窗（寄信的一直等，由它自己那邊守）
                }
                q_.seen_at_ms.erase(w.id);
                q_.seen_at_ticks.erase(w.id);
                refuse(w.id, error_reply(code::BudgetMissing, "budget for this window (" + budget_.window + ") is used up; not run"));
                continue;
            }
            if (n + busy_ >= slots_) {
                break;   // 補位到 slots 為止；其餘下一次
            }
            if (w.priority.level < high_level && n + busy_ >= slots_ - cfg_.reserved_high) {
                continue;   // 宣告級數才認保留格（不含 aging）；後面可能還有 high，不能停整列
            }
            // 包（11-05 feat-proto 件 3）：在飛＝上一次留下的＋這次新掛的
            long long inflight = pack_busy_[w.endpoint];
            if (w.pack.max_calls || w.pack.max_tokens) {
                if (spent_pack(used_, w.endpoint, w.pack.max_calls, w.pack.max_tokens, inflight)) {
                    if (budget_.wait) {
                        continue;   // 這包到頂：這封留在 new/ 等下一窗，別包照跑
                    }
                    q_.seen_at_ms.erase(w.id);
                    q_.seen_at_ticks.erase(w.id);
                    bool by_calls = spent_pack(used_, w.endpoint, w.pack.max_calls, std::nullopt, inflight);
                    std::string which = by_calls ? "max_calls " + std::to_string(*w.pack.max_calls)
                                                 : "max_tokens " + std::to_string(*w.pack.max_tokens);
                    refuse(w.id, error_reply(code::BudgetMissing, "endpoint " + w.endpoint + ": " + which + " reached in this window (" +
                                                                       budget_.window + "); not run (no fallback: pick another endpoint name)"));
                    continue;
                }
            }
            // 寄件人（11-05 feat-proto 件 5）：budget.senders 列了這人＝這人在飛＋這次新掛的也算；到頂同包的做法（refuse 回、wait 留著，別人照跑）
            std::string who = sender_key(w.sender, stack_);
            auto lim = budget_.senders.find(who);
            if (lim != budget_.senders.end() && !w.sender.empty()) {
                long long mine = sender_busy_[who];
                const Limit& l = lim->second;
                if (spent_of(used_.senders, who, l.max_calls, l.max_tokens, mine)) {
                    if (budget_.wait) {
                        continue;
                    }
                    q_.seen_at_ms.erase(w.id);
                    q_.seen_at_ticks.erase(w.id);
                    bool by_calls = spent_of(used_.senders, who, l.max_calls, std::nullopt, mine);
                    std::string which = by_calls ? "max_calls " + std::to_string(*l.max_calls) : "max_tokens " + std::to_string(*l.max_tokens);
                    refuse(w.id, error_reply(code::BudgetMissing, "sender " + w.sender + ": " + which + " reached in this window (" +
                                                                       budget_.window + "); not run"));
                    continue;
                }
            }
            if (w.pack.slots && inflight >= *w.pack.slots) {
                continue;   // 這包的格滿了：跳過、讓下一封補位（不是停下）
            }
            std::string dir = aos::join(mb_.cur(), w.id);
            if (!aos::move(aos::join(mb_.fresh(), w.id), dir)) {
                continue;   // 寄信的剛撤信
            }
            Json seen_at = q_.seen_at_ms.value(w.id, Json());
            if (seen_at.is_number()) {
                seen_at = seen_at.get<double>() / 1000.0;
            } else {
                seen_at = nullptr;
            }
            q_.seen_at_ms.erase(w.id);
            q_.seen_at_ticks.erase(w.id);
            double mounted_at = std::chrono::duration<double>(
                std::chrono::system_clock::now().time_since_epoch()).count();
            Json req = Json::object();
            req["endpoint"] = w.group;
            req["request"] = w.letter["body"]["request"];
            Json declared = w.letter["body"].value("priority", Json());
            Json priority = Json::object();
            priority["level"] = "normal";
            if (declared.is_object()) {
                priority["level"] = declared.value("level", Json("normal"));
            } else if (!declared.is_null()) {
                priority["level"] = declared;
            }
            std::optional<double> deadline = w.priority.deadline;
            if (cfg_.timeout_ms) {
                double timeout_at = mounted_at + static_cast<double>(*cfg_.timeout_ms) / 1000.0;
                if (!deadline || timeout_at < *deadline) {
                    deadline = timeout_at;
                }
            }
            if (deadline) {
                priority["deadline"] = *deadline;
            }
            req["priority"] = priority;
            std::optional<std::string> werr = aos::write_json(aos::join(dir, "request.json"), req);
            try {
                if (werr) {
                    throw Error{code::WriteFailed, *werr};
                }
                Json proc = Json::object();
                proc["seen_at"] = seen_at;
                proc["mounted_at"] = mounted_at;
                proc["endpoint"] = w.endpoint;   // 代號（在飛幾封、packs 的帳照它算；request.json 裡是解好的那組、沒代號）
                if (!w.sender.empty()) {
                    proc["sender"] = w.sender;   // 寄件人（這人在飛幾封、senders 的帳照它算）
                }
                mount(w.id, w.exec, proc);
            } catch (const Error& e) {
                std::error_code ec;
                fs::remove(aos::join(dir, PROC_JSON), ec);
                finish(w.id, error_reply(code::LaunchFailed, "cannot add the brain call to the daemon: " + e.code + " " + e.msg));
                continue;
            }
            ++n;
            ++pack_busy_[w.endpoint];
            if (!w.sender.empty()) {
                ++sender_busy_[who];
            }
        }
    }
    write_queue(stack_, q_);
    if (got != 0) {
        return 128 + got;
    }
    return 0;
}

int serve(const Cfg& cfg, const std::string& stack) {
    Server s(cfg, stack);
    return s.run();
}

}  // namespace aos::llm_kernel
