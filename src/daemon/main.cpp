#include "aos/daemon.hpp"
#include "aos/socket_path.hpp"

#include <exception>
#include <print>

int main() {
    try {
        return aos::run_daemon(aos::socket_path_from_environment());
    } catch (const std::exception& failure) {
        std::println(stderr, "aos-daemon：{}", failure.what());
        return 1;
    }
}
