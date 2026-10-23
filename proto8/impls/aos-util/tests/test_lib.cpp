// test_lib.cpp：aos-util 函式庫的測試（目前只測入口尋址：split_hash、read_json_at）。
//
//   test_lib 條名
//
// 一個執行檔，第一個參數挑跑哪一條（ctest 每條各叫一次，見 CMakeLists.txt；寫法照 aos-schema 的 test_lib.cpp）。
// 不靠測試框架：CHECK 不過就印出哪一行、退 1。要用的檔自己在暫存資料夾裡寫。
#include "aos/files.hpp"

#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <string>

#include <unistd.h>

#define CHECK(cond)                                                                      \
    do {                                                                                 \
        if (!(cond)) {                                                                   \
            std::fprintf(stderr, "%s:%d 不成立：%s\n", __FILE__, __LINE__, #cond);          \
            std::exit(1);                                                                \
        }                                                                                \
    } while (0)

namespace {

std::string tmp;   // 這一條的暫存資料夾

std::string put(const std::string& name, const std::string& text) {
    std::string path = tmp + "/" + name;
    std::ofstream(path) << text;
    return path;
}

// 跑 split_hash，回丟出來的代號（沒丟＝"<none>"）
std::string split_error(const std::string& spec) {
    try {
        aos::split_hash(spec);
    } catch (const aos::Error& e) {
        return e.code;
    }
    return "<none>";
}

// 跑 read_json_at，回丟出來的代號（沒丟＝"<none>"）
std::string read_error(const std::string& path, const std::string& pointer) {
    try {
        aos::read_json_at(path, pointer);
    } catch (const aos::Error& e) {
        return e.code;
    }
    return "<none>";
}

void test_split() {
    aos::Spec s = aos::split_hash("a/b.json");
    CHECK(s.path == "a/b.json" && s.pointer.empty());
    s = aos::split_hash("a/b.json#/x/0");
    CHECK(s.path == "a/b.json" && s.pointer == "/x/0");
    s = aos::split_hash("a.json#/x#y");   // 第一個 # 就切，後面的 # 是指標的一部分
    CHECK(s.path == "a.json" && s.pointer == "/x#y");
    s = aos::split_hash("a.json#/");      // 指向 key ""（RFC 6901）
    CHECK(s.path == "a.json" && s.pointer == "/");
}

void test_split_bad() {
    CHECK(split_error("a.json#") == "FieldType");
    CHECK(split_error("a.json#_exec") == "FieldType");
    CHECK(split_error("a.json##/x") == "FieldType");
}

void test_shebang() {
    std::string p = put("s.json", "#!/usr/bin/env aos-inst\n{\"argv\": [\"echo\"]}\n");
    CHECK(aos::read_json_at(p, "") == aos::Json({{"argv", {"echo"}}}));
    CHECK(aos::read_json_at(p, "/argv/0") == "echo");
    std::string only = put("only.json", "#!/bin/x");   // 只有 shebang＝空的，不是 JSON
    CHECK(read_error(only, "") == "JsonSyntax");
    std::string plain = put("p.json", "[1, 2]");
    CHECK(aos::read_json_at(plain, "/1") == 2);
}

void test_escape() {
    std::string p = put("e.json", "{\"a/b\": {\"c~d\": 7}}");
    CHECK(aos::read_json_at(p, "/a~1b/c~0d") == 7);
}

void test_missing() {
    std::string p = put("m.json", "{\"a\": {\"b\": 1}, \"l\": [0]}");
    CHECK(read_error(p, "/nope") == "FieldType");
    CHECK(read_error(p, "/a/b/c") == "FieldType");   // 往純量裡面指
    CHECK(read_error(p, "/l/5") == "FieldType");
    CHECK(read_error(p, "/a~2") == "FieldType");     // 指標本身寫壞
    CHECK(read_error(tmp + "/no_such.json", "") == "ReadFailed");
    CHECK(read_error(tmp, "") == "ReadFailed");       // 資料夾
    CHECK(read_error(put("bad.json", "{"), "") == "JsonSyntax");
}

}  // namespace

int main(int argc, char** argv) {
    if (argc != 2) {
        std::fprintf(stderr, "用法：test_lib 條名\n");
        return 2;
    }
    char dir[] = "/tmp/aos-util-test-XXXXXX";
    if (mkdtemp(dir) == nullptr) {
        std::perror("mkdtemp");
        return 2;
    }
    tmp = dir;
    std::string name = argv[1];
    if (name == "split") {
        test_split();
    } else if (name == "split_bad") {
        test_split_bad();
    } else if (name == "shebang") {
        test_shebang();
    } else if (name == "escape") {
        test_escape();
    } else if (name == "missing") {
        test_missing();
    } else {
        std::fprintf(stderr, "沒有這條：%s\n", argv[1]);
        return 2;
    }
    std::filesystem::remove_all(tmp);   // CHECK 不過時留著，方便看
    return 0;
}
