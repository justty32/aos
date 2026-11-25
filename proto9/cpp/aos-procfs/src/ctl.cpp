// ctl.cpp：指令檔（ctl、procs_ctl）——一次寫入一道、從收下到做完都鎖住、回饋四行、指令交給做事的線。
#include "internal.hpp"

#include <algorithm>
#include <cerrno>
#include <sstream>

namespace aos::procfs {

namespace {

std::string trim(std::string_view s) {
    size_t b = 0, e = s.size();
    while (b < e && (s[b] == ' ' || s[b] == '\t' || s[b] == '\n' || s[b] == '\r')) ++b;
    while (e > b && (s[e - 1] == ' ' || s[e - 1] == '\t' || s[e - 1] == '\n' || s[e - 1] == '\r')) --e;
    return std::string(s.substr(b, e - b));
}

}  // namespace

Ctl::Ctl(std::string prefix) : impl_(std::make_shared<Impl>()) { impl_->prefix = std::move(prefix); }

Ctl::~Ctl() { impl_->stop(); }

void Ctl::on(std::string word, Action action, Check check) {
    impl_->table[std::move(word)] = Impl::Entry{std::move(action), std::move(check)};
}

std::string Ctl::feedback() const {
    std::lock_guard<std::mutex> g(impl_->mu);
    const std::string& p = impl_->prefix;
    return kv_line(p + "cmd", impl_->cmd) + kv_line(p + "state", impl_->state) +
           kv_line(p + "error", impl_->error) + kv_line(p + "count", std::to_string(impl_->count));
}

bool Ctl::locked() const {
    std::lock_guard<std::mutex> g(impl_->mu);
    return impl_->busy;
}

bool Ctl::Impl::open_ok() const {
    std::lock_guard<std::mutex> g(mu);
    return !busy;
}

int Ctl::Impl::write(std::string_view data) {
    std::string line = trim(data);
    std::lock_guard<std::mutex> g(mu);
    // 鎖著時一律先擋、不動回饋：先搶到的人的回饋才不會被蓋掉（草稿第 6 節）
    if (busy) return EBUSY;
    if (line.empty()) return 0;   // `echo > ctl` 這種空寫入：沒有指令，什麼都不動

    auto reject = [&](std::string why) {
        ++count;
        cmd = line;
        state = "rejected";
        error = std::move(why);
        return EINVAL;
    };
    size_t nl = std::count(line.begin(), line.end(), '\n');
    if (nl > 0) return reject("LinesTooMany " + std::to_string(nl + 1) + " lines in one write");

    Command c;
    c.line = line;
    std::istringstream in(line);
    for (std::string w; in >> w;) c.words.push_back(w);
    auto it = table.find(c.words[0]);
    if (it == table.end()) return reject("CommandUnknown " + c.words[0]);
    if (it->second.check) {
        std::string why = it->second.check(c);
        if (!why.empty()) return reject(why);
    }
    ++count;
    cmd = line;
    state = "doing";
    error = "-";
    busy = true;
    job = std::move(c);
    has_job = true;
    cv.notify_one();
    return 0;   // 寫回來＝收到，不等做完
}

void Ctl::Impl::start() {
    // 線手上拿一份 shared_ptr：stop 時那道指令還在跑也不會懸空
    worker = std::thread([self = shared_from_this()] { self->run(); });
}

void Ctl::Impl::stop() {
    {
        std::lock_guard<std::mutex> g(mu);
        quit = true;
    }
    cv.notify_one();
    // 不 join：正在跑久的指令（例 slow 100）不該卡住 unmount；線閒著就自己醒來結束，
    // 還在跑就跑完再結束，或行程結束時一起收。Impl 由線手上那份 shared_ptr 撐著。
    if (worker.joinable()) worker.detach();
}

void Ctl::Impl::run() {
    for (;;) {
        Command c;
        Action act;
        {
            std::unique_lock<std::mutex> lk(mu);
            cv.wait(lk, [&] { return has_job || quit; });
            if (quit && !has_job) return;
            has_job = false;
            c = std::move(job);
            act = table.at(c.words[0]).act;
        }
        Result r;
        try {
            r = act(c);
        } catch (const std::exception& e) {
            r = Result::failed(std::string("Internal ") + e.what());
        }
        std::lock_guard<std::mutex> g(mu);
        if (r.hold) continue;   // stop：鎖到行程結束，state 停在 doing
        state = "done";
        error = r.error.empty() ? "-" : r.error;
        busy = false;
    }
}

}  // namespace aos::procfs
