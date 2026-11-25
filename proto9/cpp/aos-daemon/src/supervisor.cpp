// supervisor.cpp：監工的事件迴圈——收屍、收小行程的結果、登記期限、定期查卡住；全部不阻塞，碰底下的 proc 一律經拋棄式小行程（表上一隻的狀態變化在 lifecycle.cpp）。
#include "daemon.hpp"

#include <cerrno>
#include <csignal>
#include <cstring>
#include <poll.h>
#include <sys/signalfd.h>
#include <sys/wait.h>
#include <unistd.h>

namespace aosd {

namespace {

Clock::duration secs(double s) { return std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double>(s)); }

}  // namespace

Supervisor::Supervisor(const Config& cfg, State& st, pf::Fs& fs, int sigfd, int evfd)
    : cfg_(cfg), st_(st), fs_(fs), sigfd_(sigfd), evfd_(evfd) {}

void Supervisor::run() {
    for (;;) {
        std::vector<pollfd> fds = {{sigfd_, POLLIN, 0}, {evfd_, POLLIN, 0}};
        std::vector<pid_t> hp;
        std::vector<std::string> ext;
        for (auto& [pid, h] : helpers_)
            if (h.fd >= 0) {
                fds.push_back({h.fd, POLLIN, 0});
                hp.push_back(pid);
            }
        {
            std::lock_guard<std::mutex> g(st_.mu);
            for (auto& [name, p] : st_.procs)
                if (p.pidfd >= 0) {
                    fds.push_back({p.pidfd, POLLIN, 0});
                    ext.push_back(name);
                }
        }
        // 固定 100 ms 醒一次看期限：比算「下一個期限」簡單，閒著也只是一秒十次空轉
        if (poll(fds.data(), fds.size(), 100) < 0 && errno != EINTR) break;
        if (fds[0].revents) on_signals();
        if (fds[1].revents) {
            uint64_t n;
            if (read(evfd_, &n, sizeof n) < 0) {}
        }
        std::deque<std::shared_ptr<Request>> reqs;
        bool stop = false;
        {
            std::lock_guard<std::mutex> g(st_.mu);
            reqs.swap(st_.requests);
            stop = st_.stop_requested;
        }
        if (stop) begin_shutdown();
        for (auto& r : reqs) handle(r);
        for (size_t k = 0; k < hp.size(); ++k)
            if (fds[2 + k].revents) read_helper(hp[k]);
        for (size_t k = 0; k < ext.size(); ++k)
            if (fds[2 + hp.size() + k].revents) {
                std::lock_guard<std::mutex> g(st_.mu);
                auto it = st_.procs.find(ext[k]);
                if (it != st_.procs.end() && it->second.pidfd >= 0) external_gone(it->second);
            }
        tick();
        // 卸死掛載會 fork fusermount3，放開表的鎖再做，回答的線讀表不用等它
        std::vector<std::string> todo;
        todo.swap(cleanups_);
        for (const auto& m : todo) {
            // 不 stat 掛載點本身（卡住的會拖住監工）；rmdir 碰到還掛著的只會 EBUSY
            auto c = pf::cleanup_dead_mount(m);
            if (c == pf::Cleanup::Unmounted || c == pf::Cleanup::NotMounted) rmdir(m.c_str());
        }
        if (shutting_ && shutdown_tick()) {
            // 還沒收屍的小行程：殺掉、不等（殺不掉的也不攥著 daemon 的任何 fd）
            for (auto& [pid, h] : helpers_)
                if (!h.reaped) kill(pid, SIGKILL);
            return;
        }
    }
}

void Supervisor::on_signals() {
    signalfd_siginfo si;
    while (read(sigfd_, &si, sizeof si) == static_cast<ssize_t>(sizeof si)) {
        if (si.ssi_signo == SIGCHLD) reap();
        else begin_shutdown();   // SIGTERM／SIGINT／SIGHUP 照 ctl 的 stop 走
    }
}

void Supervisor::reap() {
    int status;
    pid_t pid;
    while ((pid = waitpid(-1, &status, WNOHANG)) > 0) {
        auto h = helpers_.find(pid);
        if (h != helpers_.end()) {
            h->second.reaped = true;
            if (h->second.fd < 0) drop_helper(h);
            continue;
        }
        std::lock_guard<std::mutex> g(st_.mu);
        for (auto& [name, p] : st_.procs)
            if (!p.external && p.pid == pid) {
                exited(p, status);
                break;
            }
    }
}

void Supervisor::read_helper(pid_t pid) {
    auto it = helpers_.find(pid);
    if (it == helpers_.end() || it->second.fd < 0) return;
    char buf[8192];
    for (;;) {
        ssize_t n = read(it->second.fd, buf, sizeof buf);
        if (n > 0) {
            it->second.out.append(buf, static_cast<size_t>(n));
            continue;
        }
        if (n < 0 && (errno == EAGAIN || errno == EINTR)) return;
        break;   // EOF：小行程說完了
    }
    finish_helper(pid, false);
}

void Supervisor::finish_helper(pid_t pid, bool timed_out) {
    auto it = helpers_.find(pid);
    Helper& h = it->second;
    close(h.fd);
    h.fd = -1;
    Done done = std::move(h.done);
    bool ok = false;
    int err = ETIMEDOUT;
    std::string data;
    if (timed_out) {
        // 放棄：殺掉、不等。它若已經把請求交給那隻 proc（殺不掉），就留著等收屍；收到之前不再碰那隻
        kill(pid, SIGKILL);
        h.abandoned = true;
        std::lock_guard<std::mutex> g(st_.mu);
        if (Proc* p = find(h.proc, h.id)) ++p->hung;
    } else if (!h.out.empty() && h.out[0] == 'O') {
        ok = true;
        err = h.out.size() > 1 && h.out[1] == 'x' ? 0 : EACCES;   // 讀的時候順便報可不可執行
        data = h.out.size() > 2 ? h.out.substr(2) : "";
    } else {
        err = h.out.size() > 1 && h.out[0] == 'E' ? std::atoi(h.out.c_str() + 1) : EIO;
    }
    if (h.reaped) drop_helper(it);
    std::lock_guard<std::mutex> g(st_.mu);
    if (done) done(ok, err, data);
}

void Supervisor::drop_helper(std::map<pid_t, Helper>::iterator it) {
    {
        std::lock_guard<std::mutex> g(st_.mu);
        if (Proc* p = find(it->second.proc, it->second.id)) {
            --p->inflight;
            if (it->second.abandoned) --p->hung;
        }
    }
    helpers_.erase(it);
}

// 為 p 開一支小行程讀或寫一個檔，到期就放棄；呼叫時拿著 st_.mu
void Supervisor::helper(Proc& p, const std::string& path, bool write, const std::string& data, double timeout, Done done) {
    HelperStart hs = start_helper(path, write, data);
    if (hs.pid < 0) return;
    Helper h;
    h.fd = hs.fd;
    h.deadline = Clock::now() + secs(timeout);
    h.done = std::move(done);
    h.proc = p.name;
    h.id = p.id;
    ++p.inflight;
    helpers_[hs.pid] = std::move(h);
}

void Supervisor::tick() {
    auto now = Clock::now();
    std::vector<pid_t> late;
    for (auto& [pid, h] : helpers_)
        if (h.fd >= 0 && now >= h.deadline) late.push_back(pid);
    for (pid_t pid : late) finish_helper(pid, true);

    std::lock_guard<std::mutex> g(st_.mu);
    for (auto it = st_.procs.begin(); it != st_.procs.end();) {
        Proc& p = it->second;
        const std::string name = it->first;
        ++it;
        if (p.pid < 0) continue;
        if (p.phase == "starting") {
            if (now >= p.deadline) {
                p.phase = "failed";
                p.reason = "RegisterTimeout no settings within " + std::to_string(cfg_.register_timeout) +
                           "s (last: " + (p.last_error.empty() ? "-" : p.last_error) + ")";
                if (p.external) {
                    // 外來的：不送訊號、不卸掛載，只記下來、不再看它
                    if (p.pidfd >= 0) close(p.pidfd);
                    p.pidfd = -1;
                    p.pid = -1;
                } else {
                    force_kill(p, "");
                }
            } else if (p.inflight == 0 && now >= p.next_try) {
                double left = std::chrono::duration<double>(p.deadline - now).count();
                p.next_try = now + secs(0.2);
                unsigned long long id = p.id;
                helper(p, cwd_of(p.pid) + "/settings", false, "", std::min(cfg_.check_timeout, left), [this, name, id](bool ok, int err, const std::string& d) {
                    if (ok) registered(name, id, d);
                    else if (Proc* q = find(name, id)) q->last_error = err == ETIMEDOUT ? "timeout" : std::strerror(err);
                });
            }
        } else if ((p.phase == "running" || p.phase == "stopping") && p.inflight == 0 && now >= p.next_try) {
            p.next_try = now + secs(cfg_.check_interval);
            unsigned long long id = p.id;
            helper(p, cwd_of(p.pid) + "/status", false, "", cfg_.check_timeout, [this, name, id](bool ok, int, const std::string&) {
                Proc* q = find(name, id);
                if (!q || q->pid < 0) return;
                if (ok && q->stuck != "no") {
                    q->stuck = "no";
                    link(*q);
                } else if (!ok && q->stuck == "no") {
                    // 卡住（或讀了回錯）：只記、不收；從 procs/ 拿掉免得後來的人踩進去
                    q->stuck = now_iso();
                    unlink(*q);
                }
            });
        }
        if (p.removing && now >= p.deadline && p.pid > 0 && p.killed.empty()) force_kill(p, "killed by rm (did not stop in time)");
    }
}

}  // namespace aosd
