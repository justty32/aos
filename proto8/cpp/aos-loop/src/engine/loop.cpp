// loop.cpp：【engine】Loop 每次怎麼走（說明見 aos/loop.hpp）。
// 10-23 壓測後：沒有身體時一輪只 tend 一次、只寫一份 state（11-02 起有變才寫，睡著的 daemon 窗不動）。
// 11-02：有身體時每跑完一次在 stdout 印一行 log（log_line，11-02 晚起 --enable-logs 才印）；心跳（beat）拿掉。
// state_flux 的 responded_at 只在處理新 ctl、收到信、起或收子項時更新。
//
// 訊號：block_signals 擋著的三個訊號排在 kernel 裡；signal_got 兩次之間取出第一個並記住（之後一直回它）；
// nap 用 sigtimedwait 睡，收到就醒。跑的期間收到的由 run_once 轉給那次、放在 Run::received。
// 11-11：on_start 在第一次之前跑一次；on_stop 在 end（finish 之後、最後一份 state 之前）或 serve 的錯誤路徑跑一次（run_side、stop_side，在 points.cpp）。
// 11-20 hook 第 5 刀：身體每跑一次的前後各一個點（before_point、after_point，在 points.cpp）；四個點失敗都收工（11-21 起 aos-daemon 的起停失敗也收工）。
// nap 也等子類別 wake_ 的訊號，交 woke 決定是否提前算一圈；aos-loop 不設，daemon 用來接 poke。
// 11-14 B7：on_stop 多 AOS_LOOP_CAUSE（stop_cause；原因檔讀法在 window.cpp 的 cause_file）。
#include "engine/engine.hpp"

#include "run/run.hpp"

#include "aos/util/proc.hpp"

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <ctime>
#include <exception>

namespace aos::loop {

using Clock = std::chrono::steady_clock;

void Loop::tend() {}
bool Loop::woke(int) { return false; }
void Loop::finish() {}
Json Loop::flux_more() { return Json::object(); }
Json Loop::info() { return Json::object(); }
std::optional<std::string> Loop::check_ctl(Json&, const aos::Resolved&) { return std::nullopt; }
void Loop::write_more(const Json&) {}

void Loop::responded() {
    responded_at_ = aos::utc_now_ms();
}

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
    if ((secs <= 0 && sigisemptyset(&wake_)) || signal_got() != 0) {
        return;
    }
    if (secs < 0) {
        secs = 0;   // 有喚醒訊號時不睡也照取一次排著的（interval 0 時 poke 不會一直排著）
    }
    long long ns = (long long)(secs * 1e9);
    timespec ts{(time_t)(ns / 1000000000LL), (long)(ns % 1000000000LL)};
    sigset_t stop = the_signals();
    sigset_t set = stop;
    for (int sig = 1; sig < NSIG; ++sig) {
        if (sigismember(&wake_, sig) == 1) {
            sigaddset(&set, sig);
        }
    }
    int sig = sigtimedwait(&set, nullptr, &ts);   // 被別的訊號打斷（EINTR）、零逾時沒東西（EAGAIN）就當睡完，回頭再看
    if (sig > 0 && sigismember(&stop, sig) == 1 && got_ == 0) {
        got_ = sig;
    } else if (sig > 0 && sigismember(&wake_, sig) == 1) {
        if (woke(sig)) {
            due_ = true;
        }
    }
}

// 四個點（on_start、on_stop、on_before_run、on_after_run）怎麼跑在 points.cpp。

// 11-14 B7（圖紙 6.3）：照這個順序，第一條成立就停——
// 1 收到 SIGTERM 而且原因檔可用＝檔裡的值（不管 stopping_、身體之後怎麼退）；2 收到任何訊號＝stopping_ 時 stop、否則 signal（SIGINT、SIGHUP 不讀檔）；
// 3 stopping_＝stop；4～6 own（呼叫處給的：跑滿 max、身體 10 body_exit、其他 error；身體自己被 SIGSEGV 殺掉時 got_ 是 0，落在 error）。
std::string Loop::stop_cause(const char* own) {
    if (got_ == SIGTERM) {
        if (std::optional<std::string> r = cause_file()) {
            return *r;
        }
    }
    if (got_ != 0) {
        return stopping_ ? StopCauseWindow::stop : StopCauseWindow::signal;
    }
    if (stopping_) {
        return StopCauseWindow::stop;
    }
    return own;
}

int Loop::end(int code, const std::string& phase, const char* own) {
    finish();
    code = stop_side(code, own);   // 11-20：on_stop 失敗而本來要退 0＝改它的碼
    write_state(phase, Json(code));
    return code;
}

int Loop::main_loop() {
    Clock::time_point next_at = Clock::now();
    max_base_ = max_;               // ctl 寫 null 回這兩個（11-03）
    interval_base_ = interval_ms_;
    read_old_state();              // 先接回 paused 與 ctl_seq；第一輪讀 ctl 前不得覆寫舊 state／state_flux
    served_ = true;
    // 11-11：起來跑一次（期間收到訊號＝下面頂端照常收工，on_stop 照跑）。11-20「四個點都跟著停」：失敗＝身體不跑、以它的碼收工；
    // 11-21「daemon 也停」：aos-daemon 同一條（起不來，表上的子項一個都還沒起）
    PointRun started = run_side(on_start_, "on_start", -1);
    if (started.code != 0 && started.received == 0) {
        fail_line(code::PointFailed, started.why);
        return end(started.code, StateWindow::done, StopCauseWindow::error);
    }
    while (true) {
        if (signal_got() != 0) {
            return end(128 + signal_got(), "stopped", StopCauseWindow::signal);
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
            return end(1, "stopped", StopCauseWindow::error);
        }
        if (stopping_) {
            return end(0, "stopped", StopCauseWindow::stop);
        }
        if (mx && runs_ >= *mx) {
            return end(0, StateWindow::done, StopCauseWindow::max);
        }
        if (due_) {
            due_ = false;
            if (!paused) {
                next_at = Clock::now();
            }
        }
        double wait = std::chrono::duration<double>(next_at - Clock::now()).count();
        if (paused || wait > 0) {
            write_state(paused ? "paused" : "waiting", Json());
            nap(paused ? 1.0 : wait);
            continue;
        }
        if (has_exec_) {   // 11-20：身體之前的點（沒寫、旗標檔不在＝go）
            int r = before_point();
            if (r == skip) {
                next_at = Clock::now() + std::chrono::milliseconds(interval_ms_);   // 跳過也推時間，不然不睡覺一直重跑（Argon A4）
                continue;
            }
            if (r == top) {
                continue;
            }
            if (r != go) {
                return r;
            }
            iv = interval_ms_;   // 再讀過一次 ctl
        }
        runs_ += 1;
        write_counter();
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
                return end(1, StateWindow::done, StopCauseWindow::error);
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
                if (got_ == 0) {
                    got_ = b.received;   // 11-11：on_stop 的 AOS_LOOP_SIGNAL 看它
                }
                return end(128 + b.received, "stopped", StopCauseWindow::signal);
            }
            if (b.code != 0 && b.code != 10) {   // 11-20：這行在 on_after_run 之前印
                fail_line(code::RunFailed, "run " + std::to_string(runs_) + ": " + exec_.label() + " failed with exit code " + std::to_string(b.code));
            }
            int r = after_point(b);   // 11-20：身體之後的點
            if (r != go) {
                return r;
            }
            if (b.code == 10) {
                return end(0, StateWindow::done, StopCauseWindow::body_exit);
            }
            if (b.code != 0) {
                return end(b.code, StateWindow::done, StopCauseWindow::error);
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
    try {
        stop_side(1, StopCauseWindow::error);   // 11-11：自己的錯退出也跑 on_stop
    } catch (...) {
    }
    return 1;
}

}  // namespace aos::loop
