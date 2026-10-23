// loop.cpp：【engine】Loop 每圈怎麼走（說明見 aos/loop.hpp）。照 proto8/bin/aos_loop.py 的 Loop.main、end、nap。
//
// 訊號：block_signals 擋著的三個訊號排在 kernel 裡；signal_got 拍與拍之間取出第一個並記住（之後一直回它，同 Python 版 take()）；
// nap 用 sigtimedwait 睡，收到就醒。拍中收到的由 run_beat 轉給那拍、放在 Beat::received。
#include "engine/engine.hpp"

#include "beat/beat.hpp"

#include <chrono>
#include <cstdio>
#include <ctime>
#include <exception>

namespace aos::loop {

using Clock = std::chrono::steady_clock;

void Loop::tend(const Json&) {}
void Loop::finish() {}
Json Loop::info() { return Json::object(); }
std::optional<std::string> Loop::check_ctl(const Json&) { return std::nullopt; }

void Loop::say(const std::string& msg) {
    std::fprintf(stderr, "%s: %s\n", d_.prog.c_str(), msg.c_str());
    std::fflush(stderr);
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

int Loop::end(int code, const std::string& state) {
    finish();
    write_state(state, Json(code));
    return code;
}

int Loop::main_loop() {
    Clock::time_point next_at = Clock::now();
    while (true) {
        if (signal_got() != 0) {
            return end(128 + signal_got(), "stopped");
        }
        ctl_now_ = read_ctl();
        const Json& c = ctl_now_;
        std::optional<long long> mx = max_;
        if (c.contains("max")) {
            mx = c["max"].get<long long>();
        }
        long long iv = interval_ms_;
        if (c.contains("interval_ms")) {
            iv = c["interval_ms"].get<long long>();
        }
        bool paused = c.value("paused", false);
        try {
            tend(c);
        } catch (const Error& e) {
            say(e.code + " " + e.msg);
            return end(1, "stopped");
        }
        if (c.value("stop", false)) {
            return end(0, "stopped");
        }
        if (mx && lap_ >= *mx) {
            return end(0, "done");
        }
        double wait = std::chrono::duration<double>(next_at - Clock::now()).count();
        if (paused || wait > 0) {
            write_state(paused ? "paused" : "waiting", Json());
            nap(paused ? 1.0 : wait);
            continue;
        }
        lap_ += 1;
        write_state("running", Json());
        if (has_run_) {
            Beat b;
            try {
                b = run_beat(run_.target, run_.args);
            } catch (const Error& e) {
                say(e.code + " " + e.msg);
                return end(1, "done");
            }
            if (b.received != 0) {
                return end(128 + b.received, "stopped");
            }
            if (b.code == 10) {
                return end(0, "done");
            }
            if (b.code != 0) {
                say("第 " + std::to_string(lap_) + " 圈 " + run_.target + " 失敗，結束碼 " + std::to_string(b.code));
                return end(b.code, "done");
            }
        }
        next_at = Clock::now() + std::chrono::milliseconds(iv);
    }
}

int Loop::serve() {
    try {
        return main_loop();
    } catch (const Error& e) {
        say(e.code + " " + e.msg);
    } catch (const std::exception& e) {
        say(std::string(code::Internal) + " " + e.what());
    }
    try {
        finish();
    } catch (...) {
    }
    return 1;
}

}  // namespace aos::loop
