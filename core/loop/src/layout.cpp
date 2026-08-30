#include <aos/loop.hpp>

#include "fs.hpp"

#include <string>

namespace aos::loop {

Layout layout_of(const std::string &folder) {
    Layout layout;
    layout.folder = fs::realpath_of(folder);
    layout.aos = fs::join(layout.folder, ".aos");
    layout.inbox = fs::join(layout.aos, "inbox");
    layout.turn_file = fs::join(layout.aos, "turn");
    layout.state_file = fs::join(layout.aos, "state.json");
    layout.agents_dir = fs::join(layout.aos, "agents");
    return layout;
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
