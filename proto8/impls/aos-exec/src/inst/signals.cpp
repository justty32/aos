// signals.cpp：【inst】訊號——跑單子的期間收到 SIGINT／SIGTERM／SIGHUP 自己不死，轉給子程式的整個行程群組。
//
// 規矩（照 proto8/bin/aos_inst.py 的 _run／_sig）：轉過去之後過 grace_ms 還沒結束就 SIGKILL 整群；
// 子程式還沒起來就收到的，起來再補送；群組已經沒了（ESRCH）就算了。
//
// 做法（從 impls/aos-inst 的 src/libaos/signals.cpp 抄來改）：
//   - run_inst 一進來就用 pthread_sigmask 擋住三個訊號（出去還原，見 run.cpp）。之後開的工人執行緒繼承這個遮罩，
//     訊號不會打死任何人，而是在 kernel 裡排隊。libaos 的子行程 exec 前會清空遮罩、恢復預設，子程式照常收得到。
//   - 排隊的訊號用 signalfd 讀：它把「收到訊號」變成一個可以 poll、可以 read 的 fd，一次讀出一個。
//   - 「還沒起來就收到的」不用另外記：它們排在 kernel 裡，aos_inst_start 回來（子程式已起來）才開始讀、讀到就轉。
//   - 送的對象：子程式是組長（libaos new_session），群組號＝它的 pid，用 killpg 整群送。
//     （aos-inst 用 pidfd 只送那一個；整群送沒有 pidfd 可用，工人收完屍就停止轉送，跟 Python 的 os.killpg 一樣。）
//   - forward_signals_until_done 用 poll 同時等「訊號」和「工人做完」（done_fd），逾時＝SIGKILL 期限；
//     回轉過的第一個訊號（Result::received，給 loop／fsm「收完這拍再以 128＋N 結束」用）。
#include "inst/inst.hpp"

#include <cerrno>
#include <chrono>

#include <poll.h>
#include <sys/signalfd.h>
#include <unistd.h>

namespace aos::exec {

using Clock = std::chrono::steady_clock;

sigset_t forwarded_signals() {
    sigset_t set;
    sigemptyset(&set);
    sigaddset(&set, SIGINT);
    sigaddset(&set, SIGTERM);
    sigaddset(&set, SIGHUP);
    return set;
}

int open_signal_fd() {
    sigset_t set = forwarded_signals();
    return signalfd(-1, &set, SFD_CLOEXEC);
}

namespace {

// 轉送的狀態：轉給哪個群組、第一次轉過之後的 SIGKILL 期限。
struct Forwarder {
    pid_t pgid = 0;
    unsigned long long grace_ms = 0;
    std::optional<Clock::time_point> kill_at;   // 第一次收到訊號＋grace_ms：到了還沒結束就 SIGKILL
    bool killed = false;
    int first = 0;                              // 轉過的第一個訊號（給 Result::received）

    void send(int sig) const {
        killpg(pgid, sig);   // ESRCH（群組沒了）不管
    }

    // sig_fd 有東西：讀一個訊號、轉給群組；第一次的話記下 SIGKILL 期限。
    void on_signal(int sig_fd) {
        signalfd_siginfo info;
        if (read(sig_fd, &info, sizeof info) != (ssize_t)sizeof info) {
            return;
        }
        if (!kill_at) {
            // grace_ms 大到離譜（幾百年）時加上去會溢位，壓在約 3 年＝實際上不會 SIGKILL
            unsigned long long grace = grace_ms;
            if (grace > 100'000'000'000ULL) {
                grace = 100'000'000'000ULL;
            }
            kill_at = Clock::now() + std::chrono::milliseconds(grace);
        }
        if (first == 0) {
            first = (int)info.ssi_signo;
        }
        send((int)info.ssi_signo);
    }

    // 離 SIGKILL 期限還有幾毫秒（給 poll 當逾時；-1＝沒有期限要等）。
    int ms_until_kill() const {
        if (!kill_at || killed) {
            return -1;
        }
        long long left = std::chrono::ceil<std::chrono::milliseconds>(*kill_at - Clock::now()).count();
        if (left < 0) {
            return 0;
        }
        if (left > (1 << 30)) {
            return 1 << 30;   // poll 的逾時是 int
        }
        return (int)left;
    }

    void kill_if_due() {
        if (ms_until_kill() == 0) {
            send(SIGKILL);
            killed = true;
        }
    }
};

}  // namespace

int forward_signals_until_done(pid_t pgid, unsigned long long grace_ms, int sig_fd, int done_fd) {
    Forwarder fw;
    fw.pgid = pgid;
    fw.grace_ms = grace_ms;
    while (true) {
        pollfd fds[2] = {{sig_fd, POLLIN, 0}, {done_fd, POLLIN, 0}};
        int r = poll(fds, 2, fw.ms_until_kill());
        if (r < 0 && errno == EINTR) {
            continue;
        }
        if (fds[1].revents != 0) {
            return fw.first;   // 工人收完屍了：不再轉（群組號可能已經沒人用）
        }
        if (fds[0].revents != 0) {
            fw.on_signal(sig_fd);
        }
        fw.kill_if_due();
    }
}

}  // namespace aos::exec
