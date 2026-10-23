// test_lib.cpp：函式庫的測試：一個執行檔，第一個參數挑跑哪一條（ctest 每條各叫一次，見 CMakeLists.txt）。
//
//   test_lib 條名 inst.schema.json tests/data
//
// 不靠測試框架：CHECK 不過就印出哪一行、退 1。一條＝一個普通函數，main 用 if 鏈挑。
#include "aos/schema.hpp"

#include <cstdio>
#include <cstdlib>
#include <string>

using nlohmann::json;
using aos::schema::Problem;

#define CHECK(cond)                                                                      \
    do {                                                                                 \
        if (!(cond)) {                                                                   \
            std::fprintf(stderr, "%s:%d 不成立：%s\n", __FILE__, __LINE__, #cond);          \
            std::exit(1);                                                                \
        }                                                                                \
    } while (0)

namespace {

json schema;        // examples/inst.schema.json
std::string data;   // tests/data 資料夾

// 驗 doc，回第一個問題的 pointer（沒問題＝"<ok>"）
std::string first_pointer(const json& doc) {
    std::vector<Problem> ps = aos::schema::validate(schema, doc);
    if (ps.empty()) {
        return "<ok>";
    }
    return ps[0].pointer;
}

void test_valid() {
    CHECK(aos::schema::validate(schema, aos::schema::load_file(data + "/inst_ok.json")).empty());
    CHECK(first_pointer({{"argv", {"x"}}, {"whatever", 1}}) == "<ok>");   // 多的 key 不管
}

void test_missing_required() {
    std::vector<Problem> ps = aos::schema::validate(schema, json::object());
    CHECK(ps.size() == 1);
    CHECK(ps[0].pointer == "");   // 缺必填報在上一層（整份）
    CHECK(ps[0].message.find("argv") != std::string::npos);
}

void test_wrong_type() {
    CHECK(first_pointer({{"argv", {"a", 3}}}) == "/argv/1");
    CHECK(first_pointer({{"argv", json::array()}}) == "/argv");                    // 空陣列
    CHECK(first_pointer({{"argv", {"a"}}, {"envs", {{"A", 1}}}}) == "/envs");      // additionalProperties 報在上一層
    CHECK(first_pointer({{"argv", {"a"}}, {"cwd", 5}}) == "/cwd");                 // 經 $ref 的定義
    CHECK(first_pointer({{"argv", {"a"}}, {"cwd_mkdir", "yes"}}) == "/cwd_mkdir");
    CHECK(first_pointer("not an object") == "");
}

void test_out_of_range() {
    CHECK(first_pointer({{"argv", {"a"}}, {"timeout_ms", 0}}) == "/timeout_ms");
    CHECK(first_pointer({{"argv", {"a"}}, {"timeout_ms", nullptr}}) == "<ok>");
    CHECK(first_pointer({{"argv", {"a"}}, {"grace_ms", -1}}) == "/grace_ms");
    CHECK(first_pointer({{"argv", {"a"}}, {"grace_ms", 0}}) == "<ok>");
    std::vector<Problem> ps = aos::schema::validate(schema, {{"argv", {"a"}}, {"timeout_ms", 0}, {"grace_ms", -1}});
    CHECK(ps.size() == 2);   // 全部收齊，不在第一個就停
}

void test_local_ref() {
    json s = {{"definitions", {{"n", {{"type", "integer"}}}}}, {"$ref", "#/definitions/n"}};
    CHECK(aos::schema::validate(s, 3).empty());
    CHECK(aos::schema::validate(s, "x").size() == 1);
}

// 驗 doc，回丟出來的 Error 代號（沒丟＝"<none>"）
std::string validate_error(const json& s, const json& doc) {
    try {
        aos::schema::validate(s, doc);
    } catch (const aos::Error& e) {
        return e.code;
    }
    return "<none>";
}

// 讀檔，回丟出來的 Error 代號（沒丟＝"<none>"）
std::string load_error(const std::string& path) {
    try {
        aos::schema::load_file(path);
    } catch (const aos::Error& e) {
        return e.code;
    }
    return "<none>";
}

void test_schema_bad() {
    json bad = aos::schema::load_file(data + "/bad.schema.json");
    CHECK(validate_error(bad, json::object()) == "SchemaBad");
    json bad_ref = aos::schema::load_file(data + "/bad_ref.schema.json");
    CHECK(validate_error(bad_ref, {{"a", 1}}) == "SchemaBad");
}

void test_file_missing() {
    CHECK(load_error(data + "/no_such.json") == "ReadFailed");
}

void test_file_bad_json() {
    CHECK(load_error(data + "/broken.txt") == "JsonSyntax");
}

}  // namespace

int main(int argc, char** argv) {
    if (argc != 4) {
        std::fprintf(stderr, "用法：test_lib 條名 inst.schema.json 資料夾\n");
        return 2;
    }
    std::string name = argv[1];
    schema = aos::schema::load_file(argv[2]);
    data = argv[3];
    if (name == "valid") {
        test_valid();
    } else if (name == "missing_required") {
        test_missing_required();
    } else if (name == "wrong_type") {
        test_wrong_type();
    } else if (name == "out_of_range") {
        test_out_of_range();
    } else if (name == "local_ref") {
        test_local_ref();
    } else if (name == "schema_bad") {
        test_schema_bad();
    } else if (name == "file_missing") {
        test_file_missing();
    } else if (name == "file_bad_json") {
        test_file_bad_json();
    } else {
        std::fprintf(stderr, "沒有這條：%s\n", argv[1]);
        return 2;
    }
    return 0;
}
