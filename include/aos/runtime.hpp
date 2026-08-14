#pragma once

#include <asio/any_io_executor.hpp>
#include <asio/io_context.hpp>

#include <chrono>
#include <cstdint>
#include <functional>
#include <utility>

namespace aos {

// daemon 從啟動到關閉都活著的共用狀態。每個命令拿到的都是同一個實例，
// 所以放在這裡的東西可以跨多次 CLI 呼叫存活 —— 這正是常駐 daemon 的意義。
//
// io_context 目前只跑在單一執行緒上，所以這裡不需要鎖。
// 哪天真的開多執行緒，要動的是這個類別，而不是每個命令。
class Runtime {
public:
    explicit Runtime(asio::io_context& context)
        : context_{context}, started_at_{std::chrono::steady_clock::now()} {}

    Runtime(const Runtime&) = delete;
    Runtime& operator=(const Runtime&) = delete;

    // 命令可以用它開背景工作或計時器；那些工作在命令回傳之後仍然活著。
    [[nodiscard]] asio::any_io_executor executor() const {
        return context_.get_executor();
    }

    [[nodiscard]] std::chrono::steady_clock::duration uptime() const {
        return std::chrono::steady_clock::now() - started_at_;
    }

    [[nodiscard]] std::uint64_t served_requests() const {
        return served_requests_;
    }

    void count_request() { ++served_requests_; }

    // 由 run_daemon 填入。命令不該直接碰 acceptor，所以透過這個間接層。
    void set_stop_handler(std::function<void()> handler) {
        stop_handler_ = std::move(handler);
    }

    // 請 daemon 收工：停止接受新連線。已經在跑的連線會做完，
    // io_context 沒事可做之後 run() 自然返回，所以是乾淨的收尾而不是硬砍。
    void request_stop() {
        if (stop_handler_) {
            stop_handler_();
        }
    }

private:
    asio::io_context& context_;
    std::chrono::steady_clock::time_point started_at_;
    std::uint64_t served_requests_ = 0;
    std::function<void()> stop_handler_;
};

}  // namespace aos
