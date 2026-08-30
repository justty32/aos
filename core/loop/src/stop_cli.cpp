#include <aos/loop.hpp>

#include "fs.hpp"

#include <cerrno>
#include <charconv>
#include <csignal>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iterator>
#include <string>
#include <string_view>
#include <system_error>

#include <time.h>
#include <unistd.h>

namespace {

bool parse_pid(std::string_view text, pid_t &pid) {
    while (!text.empty() && (text.back() == '\n' || text.back() == '\r')) {
        text.remove_suffix(1);
    }
    long long value = 0;
    const auto parsed =
        std::from_chars(text.data(), text.data() + text.size(), value);
    if (text.empty() || parsed.ec != std::errc{} ||
        parsed.ptr != text.data() + text.size() || value <= 0) {
        return false;
    }
    pid = static_cast<pid_t>(value);
    return static_cast<long long>(pid) == value;
}

bool is_alive(pid_t pid) {
    if (::kill(pid, 0) == 0) return true;
    return errno != ESRCH;
}

void wait_100_ms() {
    timespec delay{};
    delay.tv_nsec = 100000000;
    while (::nanosleep(&delay, &delay) != 0 && errno == EINTR) {
    }
}

void usage(const char *program) {
    std::fprintf(stderr, "usage: %s [folder]\n", program);
}

}  // namespace

extern "C" int aos_stop_cli_main(int argc, char *argv[]) {
    const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
                              ? argv[0]
                              : "aos stop";
    if (argv == nullptr || argc > 2) {
        usage(program);
        return 2;
    }

    const std::string folder =
        argc == 2 ? argv[1] : aos::loop::current_folder();
    const aos::loop::Layout layout = aos::loop::layout_of(folder);
    const std::string pid_path = layout.aos + "/run.pid";
    std::ifstream input(pid_path, std::ios::binary);
    const bool opened = input.good();
    const std::string text{std::istreambuf_iterator<char>(input),
                           std::istreambuf_iterator<char>()};
    pid_t pid = -1;
    if (!opened || !parse_pid(text, pid) || !is_alive(pid)) {
        std::remove(pid_path.c_str());
        std::fputs("aos stop: 沒有在跑的 loop\n", stdout);
        return 0;
    }

    if (::kill(pid, SIGTERM) != 0 && errno != ESRCH) {
        std::fprintf(stderr, "aos stop: 無法停止 pid %lld: %s\n",
                     static_cast<long long>(pid), std::strerror(errno));
        return 1;
    }
    for (int attempt = 0; attempt < 50; ++attempt) {
        wait_100_ms();
        if (!is_alive(pid)) {
            std::remove(pid_path.c_str());
            std::printf("已停止 loop（pid %lld）\n",
                        static_cast<long long>(pid));
            return 0;
        }
    }

    ::kill(pid, SIGKILL);
    std::remove(pid_path.c_str());
    std::printf("已強制停止 loop（pid %lld）\n",
                static_cast<long long>(pid));
    return 0;
}
