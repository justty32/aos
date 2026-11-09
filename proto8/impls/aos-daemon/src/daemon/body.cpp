// body.cpp：【daemon】執行 daemon 自己的身體並記錄結果（說明見 daemon.hpp）。
#include "daemon/daemon.hpp"
#include "aos/util/files.hpp"
#include "aos/util/proc.hpp"
#include <csignal>
#include <unistd.h>

namespace aos::daemon {

using Clock = std::chrono::steady_clock;


// 11-05（edge-daemon 題 1，使用者選「記一行、下一圈再跑 (Recommended)」）：身體由 daemon 自己跑（建構子把 Loop 的 exec_ 收成 body_、
// 讓 Loop 當沒有身體），失敗（退非 0、起不來）不收工：stderr 一行（碼或錯變了才印；好了印一行 ok again）、state 的 body_code 記最後一次的碼、
// 下一圈（interval_ms 後）再跑。照 Loop 的：到時間才跑（Loop 一輪可能 tend 好幾次）、max 照算、每跑完一次印 log 一行（--enable-logs）、
// 跑前寫一份 running；退 10＝daemon 收工（同 ctl 的 stop：stopping_，state phase stopped、碼 0）；跑的期間收到訊號＝原樣排回自己（kill），
// Loop 下一次取訊號就以 128＋N 收工。要整台停用 ctl 的 stop 或 Ctrl-C。
void Daemon::run_body() {
    if (!has_body_ || (max_ && body_runs_ >= *max_) || Clock::now() < body_next_) {
        return;
    }
    body_runs_ += 1;
    write_state("running", Json());
    aos::loop::Run b;
    std::string bad;
    std::string started_at = aos::utc_now_ms();
    try {
        b = aos::loop::run_once(body_);
        Json line = Json::object();   // 同 Loop 的 log 那一行
        line["started_at"] = started_at;
        line["counter_runs"] = body_runs_;
        line["code"] = b.code;
        line["signal"] = b.signal == 0 ? Json() : Json(b.signal);
        line["elapsed_ms"] = b.elapsed_ms;
        log_line(line);
    } catch (const Error& e) {
        b.code = 1;   // 起不來（LaunchFailed、單子壞……）：Loop 原本也是以 1 收工
        bad = e.code + " " + e.msg;
    }
    body_next_ = Clock::now() + std::chrono::milliseconds(interval_ms_);
    if (b.received != 0) {
        kill(getpid(), b.received);   // 三個訊號擋著：排回去，Loop 兩次之間取出
        return;
    }
    body_code_ = b.code;
    write_state("running", Json());   // body_code 變了就在這裡寫（phase 照 Loop 有身體時的 running；之後 Loop 寫 waiting 當沒變）
    if (b.code == 10) {
        stopping_ = true;
        return;
    }
    if (b.code == 0) {
        if (!body_bad_.empty()) {
            warn("body " + body_.label() + " ok again");
            body_bad_.clear();
        }
        return;
    }
    std::string key = bad.empty() ? "code " + std::to_string(b.code) : bad;
    if (key != body_bad_) {
        warn("body " + body_.label() + " failed (" + key + "), retrying next round");
        body_bad_ = key;
    }
}


}  // namespace aos::daemon
