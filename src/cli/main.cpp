#include "aos/client.hpp"
#include "aos/socket_path.hpp"

#include <filesystem>
#include <iostream>

int main(int argc, char* argv[]) {
    aos::Request request;
    request.arguments.reserve(static_cast<std::size_t>(argc - 1));
    for (int index = 1; index < argc; ++index) {
        request.arguments.emplace_back(argv[index]);
    }

    std::error_code error;
    request.working_directory = std::filesystem::current_path(error);
    if (error) {
        std::cerr << "aos：無法取得目前工作目錄：" << error.message() << '\n';
        return 1;
    }

    try {
        return aos::run_client(std::move(request),
                               aos::socket_path_from_environment());
    } catch (const std::exception& failure) {
        std::cerr << "aos：" << failure.what() << '\n';
        return 1;
    }
}
