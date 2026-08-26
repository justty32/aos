#pragma once

// resolve 層測試共用的 helper：解析一筆 instruction、固定的明示 context、
// 暫存目錄與被引用檔案的寫入。

#include <aos/inst.hpp>

#include <catch2/catch_test_macros.hpp>

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

namespace aos::resolve_test {

inline aos::inst_t parse(const std::string &document) {
    aos::inst_t inst;
    REQUIRE(aos::read_one(document.data(), document.size(), inst) ==
            aos::InstState::Ok);
    return inst;
}

inline aos::ResolveContext context() {
    aos::ResolveContext value;
    value.environment = {
        {"ARG", "argument"}, {"IN", "input"}, {"OUT", "output"},
        {"ERR", "error"}, {"EXIT", "status"}, {"CWD", "work"},
        {"VALUE", "env-value"},
    };
    value.base_path = "/world";
    return value;
}

struct TempDir {
    TempDir() {
        std::string pattern = "/tmp/aos_resolve_test_XXXXXX";
        std::vector<char> buffer(pattern.begin(), pattern.end());
        buffer.push_back('\0');
        REQUIRE(mkdtemp(buffer.data()) != nullptr);
        path = buffer.data();
    }
    ~TempDir() { std::filesystem::remove_all(path); }
    std::string path;
};

inline void write_file(const TempDir &dir, const std::string &name,
                       const std::string &content) {
    std::ofstream output(dir.path + "/" + name);
    REQUIRE(static_cast<bool>(output));
    output << content;
    REQUIRE(static_cast<bool>(output));
}

inline aos::ResolveContext file_context(const TempDir &dir) {
    aos::ResolveContext value = context();
    value.base_path = dir.path;
    return value;
}

}  // namespace aos::resolve_test
