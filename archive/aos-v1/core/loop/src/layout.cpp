#include <aos/loop.hpp>

#include "fs.hpp"

#include <cstdlib>
#include <filesystem>
#include <string>
#include <system_error>

namespace aos::loop {

Layout layout_of(const std::string &folder) {
    Layout layout;
    layout.folder = fs::realpath_of(folder);
    layout.aos = fs::join(layout.folder, ".aos");
    layout.inbox = fs::join(layout.aos, "inbox");
    layout.every = fs::join(layout.aos, "every");
    layout.turn_file = fs::join(layout.aos, "turn");
    layout.state_file = fs::join(layout.aos, "state.json");
    layout.agents_dir = fs::join(layout.aos, "agents");
    return layout;
}

std::string find_folder(const std::string &start) {
    std::error_code code;
    std::filesystem::path current = std::filesystem::absolute(start, code);
    if (code) return {};
    current = current.lexically_normal();

    while (true) {
        code.clear();
        if (std::filesystem::is_directory(current / ".aos", code)) {
            return fs::realpath_of(current.string());
        }
        const std::filesystem::path parent = current.parent_path();
        if (parent == current || parent.empty()) return {};
        current = parent;
    }
}

std::string current_folder() {
    const char *from_environment = std::getenv("AOS_FOLDER");
    if (from_environment != nullptr && *from_environment != '\0') {
        return from_environment;
    }

    std::error_code code;
    std::string cwd = std::filesystem::current_path(code).string();
    if (code || cwd.empty()) cwd = fs::realpath_of(".");
    if (cwd.empty()) cwd = ".";
    const std::string found = find_folder(cwd);
    return found.empty() ? cwd : found;
}

std::string insts_dir(const Layout &layout, std::uint64_t turn) {
    return fs::join(fs::join(fs::join(layout.aos, "batch"),
                             std::to_string(turn)),
                    "insts");
}

std::string out_dir(const Layout &layout, std::uint64_t turn) {
    return fs::join(fs::join(fs::join(layout.aos, "batch"),
                             std::to_string(turn)),
                    "out");
}

bool ensure_layout(const Layout &layout, std::string &error) {
    error.clear();
    if (!fs::mkdir_p(layout.inbox, error) ||
        !fs::mkdir_p(layout.every, error) ||
        !fs::mkdir_p(layout.agents_dir, error)) {
        return false;
    }
    std::string ignored;
    std::string turn_text;
    if (!fs::read_file(layout.turn_file, turn_text, ignored)) {
        return write_turn(layout, 1, error);
    }
    return true;
}

std::uint64_t read_turn(const Layout &layout) {
    std::string text;
    std::string error;
    if (!fs::read_file(layout.turn_file, text, error)) return 1;
    try {
        std::size_t consumed = 0;
        const std::uint64_t turn = std::stoull(text, &consumed);
        return consumed == 0 ? 1 : turn;
    } catch (...) {
        return 1;
    }
}

bool write_turn(const Layout &layout, std::uint64_t turn,
                std::string &error) {
    return fs::write_atomic(layout.turn_file, std::to_string(turn) + "\n",
                            error);
}

}  // namespace aos::loop
