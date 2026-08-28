#pragma once

// handoff 層測試共用的 helper：暫存世界目錄與整檔讀寫。
// （測試不看 src/ 的內部標頭，這裡刻意用 <fstream> 自己寫檔，不借 handoff_fs 的實作。）

#include <catch2/catch_test_macros.hpp>

#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

#include <unistd.h>

namespace aos::handoff_test {

inline std::string make_temp_dir() {
    std::string pattern = "/tmp/aos_handoff_test_XXXXXX";
    std::vector<char> buffer(pattern.begin(), pattern.end());
    buffer.push_back('\0');
    REQUIRE(mkdtemp(buffer.data()) != nullptr);
    return buffer.data();
}

struct TempDir {
    TempDir() : path(make_temp_dir()) {}
    ~TempDir() { std::filesystem::remove_all(path); }
    std::string path;
};

inline void write_file(const std::string &path, const std::string &content) {
    std::ofstream output(path, std::ios::out | std::ios::trunc);
    output << content;
}

inline std::string read_file(const std::string &path) {
    std::ifstream input(path);
    std::ostringstream content;
    content << input.rdbuf();
    return content.str();
}

}  // namespace aos::handoff_test
