#include "aos/daemon.hpp"
#include "aos/socket_path.hpp"

#include <exception>
#include <iostream>

int main() {
    try {
        return aos::run_daemon(aos::socket_path_from_environment());
    } catch (const std::exception& failure) {
        std::cerr << "aos-daemon：" << failure.what() << '\n';
        return 1;
    }
}
