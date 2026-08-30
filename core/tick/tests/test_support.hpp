#pragma once

/* core/tick 測試的共用工具。照 core/loop/tests/test_support.hpp 的樣子抄一份——
 * 跨小專案不共用 tests/ 底下的標頭（那不是公開 API）。 */

#include <aos/loop.hpp>
#include <aos/tick.hpp>

#include <catch2/catch_test_macros.hpp>

#include <algorithm>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

#include <stdlib.h>

namespace aos::tick::test {

inline std::string make_temp_dir() {
    std::string pattern = "/tmp/aos_tick_test_XXXXXX";
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

inline bool exists(const std::string &path) {
    return std::filesystem::exists(path);
}

/* 建一個已 ensure_layout 的空世界。 */
inline loop::Layout make_world(const std::string &folder) {
    const loop::Layout layout = loop::layout_of(folder);
    std::string error;
    REQUIRE(loop::ensure_layout(layout, error));
    return layout;
}

/* 在世界裡放一隻「看起來已初始化」的 agent：agent::say() 只要求 say/ 存在。 */
inline void make_agent(const loop::Layout &layout, const std::string &name) {
    std::filesystem::create_directories(
        std::filesystem::path(layout.agents_dir) / name / "say");
}

/* agents/<name>/say/ 底下的檔案數——ask 有沒有真的投出去就看它。 */
inline std::size_t say_count(const loop::Layout &layout,
                             const std::string &name) {
    const std::filesystem::path say =
        std::filesystem::path(layout.agents_dir) / name / "say";
    if (!std::filesystem::is_directory(say)) return 0;
    std::size_t count = 0;
    for (const auto &entry : std::filesystem::directory_iterator(say)) {
        if (entry.is_regular_file()) ++count;
    }
    return count;
}

/* inbox 裡的 .json 檔名（不含副檔名），排序後回傳。 */
inline std::vector<std::string> inbox_ids(const loop::Layout &layout) {
    std::vector<std::string> ids;
    if (!std::filesystem::is_directory(layout.inbox)) return ids;
    for (const auto &entry : std::filesystem::directory_iterator(layout.inbox)) {
        if (entry.path().extension() == ".json") {
            ids.push_back(entry.path().stem().string());
        }
    }
    std::sort(ids.begin(), ids.end());
    return ids;
}

}  // namespace aos::tick::test
