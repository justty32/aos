// loop.cpp：【engine】Loop 每次怎麼走（說明見 aos/loop.hpp）。
// 10-23 壓測後：沒有身體時一輪只 tend 一次、只寫一份 state（11-02 起有變才寫，睡著的 daemon 窗不動）。
// 11-02：有身體時每跑完一次在 stdout 印一行 log（log_line，11-02 晚起 --enable-logs 才印）；心跳（beat）拿掉。
//
// 訊號：block_signals 擋著的三個訊號排在 kernel 裡；signal_got 兩次之間取出第一個並記住（之後一直回它）；
// nap 用 sigtimedwait 睡，收到就醒。跑的期間收到的由 run_once 轉給那次、放在 Run::received。
#include "engine/engine.hpp"

#include "run/run.hpp"

#include "aos/proc.hpp"

#include <chrono>
#include <cstdio>
#include <ctime>
#include <exception>

namespace aos::loop {

using Clock = std::chrono::steady_clock;

void Loop::tend() {}
void Loop::finish() {}
Json Loop::info() { return Json::object(); }
std::optional<std::string> Loop::check_ctl(Json&, const aos::Resolved&) { return std::nullopt; }
void Loop::write_more(const Json&) {}

int Loop::fail_line(const std::string& code, const std::string& msg) {
    return aos::fail(d_.prog, code, msg);
}

void Loop::warn(const std::string& msg) {
    aos::warn(d_.prog, msg);
}

int Loop::signal_got() {
    if (got_ == 0) {
        got_ = take_signal();
    }
    return got_;
}

void Loop::nap(double secs) {
    if (secs > 1.0) {
        secs = 1.0;
    }
    if (secs <= 0 || signal_got() != 0) {
        return;
    }
    long long ns = (long long)(secs * 1e9);
    timespec ts{(time_t)(ns / 1000000000LL), (long)(ns % 1000000000LL)};
    sigset_t set = the_signals();
    int sig = sigtimedwait(&set, nullptr, &ts);   // 被別的訊號打斷（EINTR）就當睡完，回頭再看
    if (sig > 0 && got_ == 0) {
        got_ = sig;
    }
}

int Loop::end(int code, const std::string& phase) {
    finish();
    write_state(phase, Json(code));
    return code;
}

int Loop::main_loop() {
    Clock::time_point next_at = Clock::now();
    max_base_ = max_;               // ctl 寫 null 回這兩個（11-03）
    interval_base_ = interval_ms_;
    read_old_paused();              // 起來先暫停？（11-03 代定：舊 state 的 paused 是 true）
    while (true) {
        if (signal_got() != 0) {
            return end(128 + signal_got(), "stopped");
        }
        read_ctl();                 // 新的指令才照做（11-03）
        std::optional<long long> mx = max_;
        long long iv = interval_ms_;
        bool paused = paused_;
        try {
            tend();
        } catch (const StateError&) {
            throw;   // tend 裡寫狀態窗寫不了：交給 serve 印一行、收尾（不再走 end 寫 state）
        } catch (const Error& e) {
            fail_line(e.code, e.msg);
            return end(1, "stopped");
        }
        if (stopping_) {
            return end(0, "stopped");
        }
        if (mx && runs_ >= *mx) {
            return end(0, "done");
        }
        double wait = std::chrono::duration<double>(next_at - Clock::now()).count();
        if (paused || wait > 0) {
            write_state(paused ? "paused" : "waiting", Json());
            nap(paused ? 1.0 : wait);
            continue;
        }
        runs_ += 1;
        if (!has_exec_) {
            // 沒有身體：這一次就只是剛才那次 tend。不寫 running、不回頭重讀 ctl 重 tend，直接要寫一份 waiting 睡到下一次（一輪最多一份 state；11-02 起跟上一份一樣就不寫）
            next_at = Clock::now() + std::chrono::milliseconds(iv);
            if (mx && runs_ >= *mx) {
                continue;   // 回頂端照常收工（done）
            }
            write_state("waiting", Json());
            nap(std::chrono::duration<double>(next_at - Clock::now()).count());
            continue;
        }
        write_state("running", Json());
        if (has_exec_) {
            Run b;
            std::string started_at = aos::utc_now_ms();
            try {
                b = run_once(exec_);
            } catch (const Error& e) {
                fail_line(e.code, e.msg);
                return end(1, "done");
            }
            // log（11-02）：每跑完一次一行（欄位名同 N-39 fsm 的 trace、P-38 的 started_at），不論那次怎麼結束
            Json line = Json::object();
            line["started_at"] = started_at;
            line["counter_runs"] = runs_;
            line["code"] = b.code;
            line["signal"] = b.signal == 0 ? Json() : Json(b.signal);
            line["elapsed_ms"] = b.elapsed_ms;
            log_line(line);
            if (b.received != 0) {
                return end(128 + b.received, "stopped");
            }
            if (b.code == 10) {
                return end(0, "done");
            }
            if (b.code != 0) {
                fail_line(code::RunFailed, "run " + std::to_string(runs_) + ": " + exec_.label() + " failed with exit code " + std::to_string(b.code));
                return end(b.code, "done");
            }
        }
        next_at = Clock::now() + std::chrono::milliseconds(iv);
    }
}

int Loop::serve() {
    try {
        return main_loop();
    } catch (const Error& e) {   // 含 StateError
        fail_line(e.code, e.msg);
    } catch (const std::exception& e) {
        fail_line(code::Internal, e.what());
    }
    try {
        finish();
    } catch (...) {
    }
    return 1;
}

}  // namespace aos::loop
