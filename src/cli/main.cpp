#include "aos/client.hpp"
#include "aos/socket_path.hpp"

#include <exception>
#include <filesystem>
#include <print>
#include <span>

int main(int argc, char* argv[]) {
    // argc 可能是 0（execve 允許），所以先包成 span 再切掉程式名稱，
    // 不要直接算 argc - 1。
    const std::span command_line{argv, static_cast<std::size_t>(argc < 0 ? 0 : argc)};
    const auto arguments = command_line.empty() ? command_line
                                                : command_line.subspan(1);

    std::error_code error;
    const auto working_directory = std::filesystem::current_path(error);
    if (error) {
        std::println(stderr, "aos：無法取得目前工作目錄：{}", error.message());
        return 1;
    }

    const aos::Request request{
        .arguments = {arguments.begin(), arguments.end()},
        .working_directory = working_directory,
    };

    try {
        return aos::run_client(request, aos::socket_path_from_environment());
    } catch (const std::exception& failure) {
        std::println(stderr, "aos：{}", failure.what());
        return 1;
    }
}
