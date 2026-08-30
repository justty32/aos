#pragma once

#include <aos/loop.hpp>

#include <catch2/catch_test_macros.hpp>

#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

#include <stdlib.h>

namespace aos::loop::test {

inline std::string make_temp_dir() {
    std::string pattern = "/tmp/aos_loop_test_XXXXXX";
    std::vector<char> buffer(pattern.begin(), pattern.end());
    buffer.push_back('\0');
    REQUIRE(::mkdtemp(buffer.data()) != nullptr);
    return buffer.data();
}

struct TempDir {
    TempDir() : path(make_temp_dir()) {}
    ~TempDir() { std::filesystem::remove_all(path); }
    std::string path;
};

inline void write_file(const std::string &path, const std::string &text) {
    std::ofstream output(path, std::ios::binary | std::ios::trunc);
    REQUIRE(output.good());
    output << text;
    REQUIRE(output.good());
}

inline std::string read_file(const std::string &path) {
    std::ifstream input(path, std::ios::binary);
    REQUIRE(input.good());
    std::ostringstream buffer;
    buffer << input.rdbuf();
    return buffer.str();
}

inline std::vector<std::filesystem::path> json_files(
    const std::string &directory) {
    std::vector<std::filesystem::path> files;
    for (const auto &entry : std::filesystem::directory_iterator(directory)) {
        if (entry.path().extension() == ".json") files.push_back(entry.path());
    }
    return files;
}

inline wire::Inst command(std::string id,
                          std::vector<std::string> argv) {
    wire::Inst inst;
    inst.id = std::move(id);
    inst.argv = std::move(argv);
    return inst;
}

inline void deliver_command(const Layout &layout, wire::Inst inst) {
    std::string error;
    REQUIRE(deliver(layout, inst, error));
}

inline wire::State read_state(const Layout &layout) {
    std::string error;
    auto state = wire::parse_state(read_file(layout.state_file), error);
    REQUIRE(state.has_value());
    return std::move(*state);
}

inline wire::Outcome read_outcome(const std::string &path) {
    std::string error;
    auto outcome = wire::parse_outcome(read_file(path), error);
    REQUIRE(outcome.has_value());
    return std::move(*outcome);
}

}  // namespace aos::loop::test
