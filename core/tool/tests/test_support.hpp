#pragma once

#include <chrono>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

#include <unistd.h>

namespace aos::tool::test {

class TempWorld {
public:
    explicit TempWorld(std::string_view label = "world") {
        const auto stamp = std::chrono::steady_clock::now()
                               .time_since_epoch()
                               .count();
        path = std::filesystem::temp_directory_path() /
               ("aos-tool-" + std::string(label) + "-" +
                std::to_string(getpid()) + "-" + std::to_string(stamp));
        std::filesystem::create_directories(path);
    }

    ~TempWorld() { std::filesystem::remove_all(path); }

    std::filesystem::path write_script(std::string_view name,
                                       std::string_view contents) const {
        const std::filesystem::path script = path / name;
        std::ofstream output(script);
        output << contents;
        output.close();
        std::filesystem::permissions(
            script, std::filesystem::perms::owner_exec |
                        std::filesystem::perms::group_exec |
                        std::filesystem::perms::others_exec,
            std::filesystem::perm_options::add);
        return script;
    }

    std::filesystem::path path;
};

inline int run_cli(int (*entry)(int, char **),
                   std::vector<std::string> arguments) {
    std::vector<char *> argv;
    argv.reserve(arguments.size());
    for (std::string &argument : arguments) argv.push_back(argument.data());
    return entry(static_cast<int>(argv.size()), argv.data());
}

}  // namespace aos::tool::test
