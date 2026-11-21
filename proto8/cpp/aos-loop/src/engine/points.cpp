// points.cpp：【engine】loop 的四個點怎麼跑——on_start／on_stop（run_side、stop_side）與每跑一次身體前後的 on_before_run／on_after_run（說明見 aos/loop.hpp）。
// 11-11 起停兩格（使用者選「aos-loop 自己加」）；11-20 hook 第 5 刀加身體前後兩格與兩個 _if 旗標檔（使用者「能攔」「用旗標檔」「before_run / after_run」），
// 四個點失敗都收工（使用者「四個點都跟著停」；aos-daemon 只有 on_start／on_stop，11-21「daemon 也停」起失敗一樣收工）。loop 不知道這些點是什麼（C-52）。
#include "engine/engine.hpp"

#include "run/run.hpp"

#include <cstdlib>
#include <optional>
#include <unistd.h>
#include <utility>
#include <vector>

namespace aos::loop {

namespace {

// 設幾個環境變數，離開範圍時還原成原本的（沒有的 unset）
struct EnvSet {
    std::vector<std::pair<std::string, std::optional<std::string>>> old;
    void set(const char* k, const std::string& v) {
        const char* o = std::getenv(k);
        old.emplace_back(k, o ? std::optional<std::string>(o) : std::nullopt);
        setenv(k, v.c_str(), 1);
    }
    ~EnvSet() {
        for (auto it = old.rbegin(); it != old.rend(); ++it) {
            if (it->second) {
                setenv(it->first.c_str(), it->second->c_str(), 1);
            } else {
                unsetenv(it->first.c_str());
            }
        }
    }
};

}  // namespace

Loop::PointRun Loop::run_point(const Target& t, const char* key, long long timeout_ms) {
    PointRun p;
    try {
        Run b = run_once(t, timeout_ms);
        p.received = b.received;
        if (b.received != 0 && got_ == 0) {
            got_ = b.received;
        }
        if (b.timed_out) {
            p.code = b.code != 0 ? b.code : 1;
            p.why = std::string(key) + " " + t.label() + " did not finish in " + std::to_string(timeout_ms) + " ms and was killed";
        } else if (b.code != 0) {
            p.code = b.code;
            p.why = std::string(key) + " " + t.label() + " exited " + std::to_string(b.code);
        }
    } catch (const Error& e) {
        p.code = 1;
        p.why = std::string(key) + " " + t.label() + " cannot run: " + e.code + " " + e.msg;
    }
    return p;
}

bool Loop::point_on(const std::string& flag) const {
    return flag.empty() || access(flag.c_str(), F_OK) == 0;
}

// code≥0＝on_stop：環境多 AOS_LOOP_CODE、AOS_LOOP_SIGNAL、AOS_LOOP_CAUSE（跑完還原）。跑的期間收到的訊號記成這支收到的（之後照常收工）。
Loop::PointRun Loop::run_side(const std::optional<Target>& t, const char* key, int code, const std::string& cause) {
    if (!t) {
        return PointRun{};
    }
    EnvSet env;
    if (code >= 0) {
        env.set("AOS_LOOP_CODE", std::to_string(code));
        env.set("AOS_LOOP_SIGNAL", got_ != 0 ? std::to_string(got_) : "");
        env.set(cause_env, cause);
    }
    return run_point(*t, key, on_timeout_ms_);
}

int Loop::stop_side(int code, const char* own) {
    if (!served_ || stop_ran_) {
        return code;
    }
    stop_ran_ = true;
    if (!on_stop_) {
        return code;   // 沒有 on_stop：原因也不用算（不讀原因檔、不印它的 warning）
    }
    // 收尾途中（例：daemon 的 finish 等子項退）才到、還排著的訊號也算收到：先取出來，原因照 6.3 判；
    // 不取的話它會被 run_once 當成 on_stop 跑的期間收到的、轉給 on_stop 把它收掉
    signal_got();
    PointRun p = run_side(on_stop_, "on_stop", code, stop_cause(own));
    if (p.code == 0) {
        return code;
    }
    if (code == 0 && p.received == 0) {   // 11-20「四個點都跟著停」（11-21 daemon 也是）：本來要退 0 才改碼；跑的期間收到訊號不算它失敗
        fail_line(code::PointFailed, p.why);
        return p.code;
    }
    warn(p.why);
    return code;
}

int Loop::before_point() {
    if (!on_before_run_ || !point_on(before_run_if_)) {
        return go;
    }
    PointRun p;
    {
        EnvSet env;
        env.set(runs_env, std::to_string(runs_ + 1));
        p = run_point(*on_before_run_, "on_before_run", 0);
    }
    if (p.received != 0 || signal_got() != 0) {
        return top;   // 頂端照「收到訊號」收工（不算它失敗）
    }
    if (p.code == 10) {
        return skip;
    }
    if (p.code != 0) {
        fail_line(code::PointFailed, "run " + std::to_string(runs_ + 1) + ": " + p.why);
        return end(p.code, StateWindow::done, StopCauseWindow::error);
    }
    read_ctl();   // 扣在這個點期間下的 stop／pause 要生效（Argon A3）
    if (stopping_ || paused_ || (max_ && runs_ >= *max_)) {
        return top;
    }
    return go;
}

int Loop::after_point(const Run& b) {
    if (!on_after_run_ || !point_on(after_run_if_)) {
        return go;
    }
    PointRun p;
    {
        EnvSet env;
        env.set(runs_env, std::to_string(runs_));
        env.set(run_code_env, std::to_string(b.code));
        env.set(run_signal_env, b.signal != 0 ? std::to_string(b.signal) : "");
        env.set(run_ms_env, std::to_string(b.elapsed_ms));
        p = run_point(*on_after_run_, "on_after_run", 0);
    }
    if (p.received != 0 || signal_got() != 0) {
        return end(128 + signal_got(), "stopped", StopCauseWindow::signal);
    }
    if (p.code == 0) {
        return go;
    }
    if (b.code == 0) {
        fail_line(code::PointFailed, "run " + std::to_string(runs_) + ": " + p.why);
        return end(p.code, StateWindow::done, StopCauseWindow::error);
    }
    warn("run " + std::to_string(runs_) + ": " + p.why + " (the run itself ends the loop, its result counts)");
    return go;
}

}  // namespace aos::loop
