// serve.cpp：【serve】鎖信箱、選開計數、清理寄件人已離開的信、按宣告級數留 high 格、檢查後端限制與記換包，再串起每輪流程（說明見 serve.hpp）。
#include "serve/serve.hpp"

#include "aos/util/files.hpp"
#include "aos/util/signals.hpp"
#include "aos/util/text.hpp"
#include "aos/util/clock.hpp"

#include <cerrno>
#include <charconv>
#include <chrono>
#include <cstring>
#include <filesystem>
#include <limits>

#include <fcntl.h>
#include <sys/file.h>

namespace fs = std::filesystem;

namespace aos::llm_kernel {

namespace {

// 開計數時才讀寫 $AOS_STACK/counter_kernel_runs.txt；同一個信箱的 flock 保護讀、加一、原子寫回。
void count_run(const std::string& stack) {
    std::string path = aos::join(stack, "counter_kernel_runs.txt");
    long long runs = 0;
    int err = 0;
    std::optional<std::string> text = aos::read_file(path, err);
    if (!text && err != ENOENT) {
        throw Error{code::CounterBad, "cannot read " + path + ": " + std::strerror(err)};
    }
    if (text) {
        std::string value = aos::strip(*text);
        bool digits = aos::is_utf8(*text) && !value.empty();
        for (char ch : value) {
            if (ch < '0' || ch > '9') {
                digits = false;
            }
        }
        std::from_chars_result parsed = std::from_chars(value.data(), value.data() + value.size(), runs);
        if (!digits || parsed.ec != std::errc{} || parsed.ptr != value.data() + value.size()) {
            throw Error{code::CounterBad, path + " must contain a non-negative integer within signed 64-bit range (delete it to start over)"};
        }
    }
    if (runs == std::numeric_limits<long long>::max()) {
        throw Error{code::CounterBad, path + " is too large to increment (delete it to start over)"};
    }
    std::string tmp = aos::join(stack, ".counter_kernel_runs.txt");
    std::optional<aos::TextWriteError> error = aos::write_text(path, std::to_string(runs + 1) + "\n", tmp);
    if (error) {
        if (error->operation == aos::TextWriteOperation::rename) {
            throw Error{code::WriteFailed, "cannot rename " + tmp + " -> " + path + ": " + std::strerror(error->number)};
        }
        throw Error{code::WriteFailed, "cannot write " + tmp + ": " + std::strerror(error->number)};
    }
}

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
    if (enable_counters_) {
        count_run(stack_);
    }
    used_ = read_used(stack_, budget_.window);
    table_ = read_table(host_);
    write_window(stack_, window_of(cfg_.packs));
    collect();
    sweep();
    std::optional<long long> now_cycle = aos::now_cycle();
    long long now_ms = aos::utc_now_epoch_ms();
    std::vector<Waiting> ws = scan(now_ms, now_cycle);
    order(ws, cfg_.aging_cycles, q_);

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
                q_.seen_at_cycles.erase(w.id);
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
                    q_.seen_at_cycles.erase(w.id);
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
                    q_.seen_at_cycles.erase(w.id);
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
            if (w.pack.backend) {
                const auto& backend = *w.pack.backend;
                const Backend& limits = cfg_.backends.at(backend);
                const auto& packs = backend_packs_[backend];
                if (backend_busy_[backend] >= limits.slots ||
                    (limits.max_packs && !packs.contains(w.endpoint) &&
                     packs.size() >= static_cast<size_t>(*limits.max_packs))) {
                    continue;
                }
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
            q_.seen_at_cycles.erase(w.id);
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
                proc["switched"] = w.pack.backend &&
                    (!q_.backends.contains(*w.pack.backend) || q_.backends[*w.pack.backend]["pack"] != w.endpoint);
                if (w.pack.backend) {
                    proc["backend"] = *w.pack.backend;
                }
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
            if (w.pack.backend) {
                const auto& backend = *w.pack.backend;
                if (!q_.backends.contains(backend) || q_.backends[backend]["pack"] != w.endpoint) {
                    long long switches = q_.backends.contains(backend)
                        ? q_.backends[backend]["counter_switches"].get<long long>() : 0;
                    q_.backends[backend] = Json{{"pack", w.endpoint}, {"switched_at", mounted_at},
                                              {"counter_switches", switches + 1}};
                }
                ++backend_busy_[backend];
                backend_packs_[backend].insert(w.endpoint);
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

int serve(const Cfg& cfg, const std::string& stack, bool enable_counters) {
    Server s(cfg, stack, enable_counters);
    return s.run();
}

}  // namespace aos::llm_kernel
