// resolve 層：$ref 引用——所有合法位置、檔案／pointer／JSON 錯誤、巢狀
// ref+env、深鏈無上限、循環與路徑正規化、RFC 6901 跳脫、referenced $opt、
// 未解析 round trip、無 hash 的整份引用。

#include "resolve_test_support.hpp"

#include <string>

using namespace aos::resolve_test;

TEST_CASE("references resolve strings in every string value position") {
    TempDir dir;
    write_file(dir, "values.json",
               R"({"arg":"argument","in":"input","out":"output","err":"error","exit":"status","cwd":"work","env":"env-value"})");
    aos::inst_t inst = parse(
        R"({"argv":["command",{"$ref":"values.json#/arg"}],"stdin":{"$ref":"values.json#/in"},"stdout":{"$ref":"values.json#/out"},"stderr":{"$ref":"values.json#/err"},"exit":{"$ref":"values.json#/exit"},"cwd":{"$ref":"values.json#/cwd"},"env":{"KEY":{"$ref":"values.json#/env"}}})");
    aos::ResolveResult result;

    REQUIRE(aos::resolve(inst, file_context(dir), result) ==
            aos::ResolveState::Ok);
    CHECK(inst.argv[1] == "argument");
    CHECK(inst.stdin_path == "input");
    CHECK(inst.stdout_path == "output");
    CHECK(inst.stderr_path == "error");
    CHECK(inst.exit_path == "status");
    CHECK(inst.cwd == "work");
    CHECK(inst.env.at("KEY") == "env-value");
}

TEST_CASE("references reject structures missing files and missing pointers") {
    TempDir dir;
    write_file(dir, "values.json", R"({"array":[],"object":{}})");
    aos::ResolveResult result;

    auto array = parse(R"({"argv":["x",{"$ref":"values.json#/array"}]})");
    CHECK(aos::resolve(array, file_context(dir), result) ==
          aos::ResolveState::ReferenceValueInvalid);
    CHECK(result.reference_path == dir.path + "/values.json");
    CHECK(result.pointer == "/array");

    auto object = parse(
        R"({"argv":["x",{"$ref":"values.json#/object"}]})");
    CHECK(aos::resolve(object, file_context(dir), result) ==
          aos::ResolveState::ReferenceValueInvalid);

    auto missing_file = parse(
        R"({"argv":["x",{"$ref":"missing.json#/value"}]})");
    CHECK(aos::resolve(missing_file, file_context(dir), result) ==
          aos::ResolveState::ReferenceReadFailed);
    CHECK(result.reference_path == dir.path + "/missing.json");

    auto missing_pointer = parse(
        R"({"argv":["x",{"$ref":"values.json#/missing"}]})");
    CHECK(aos::resolve(missing_pointer, file_context(dir), result) ==
          aos::ResolveState::ReferencePointerInvalid);
    CHECK(result.pointer == "/missing");
}

TEST_CASE("references report invalid referenced JSON") {
    TempDir dir;
    write_file(dir, "bad.json", "{");
    auto inst = parse(R"({"argv":["x",{"$ref":"bad.json#/x"}]})");
    aos::ResolveResult result;

    CHECK(aos::resolve(inst, file_context(dir), result) ==
          aos::ResolveState::ReferenceJsonInvalid);
    CHECK(result.reference_path == dir.path + "/bad.json");
    CHECK(result.pointer == "/x");
}

TEST_CASE("unresolved references round trip without loss") {
    const std::string document =
        R"({"argv":["x",{"$ref":"values.json#/x"}]})";
    auto inst = parse(document);
    std::string encoded;

    REQUIRE(aos::write_one(inst, encoded) == aos::InstState::Ok);
    CHECK(encoded == document + "\n");
}

TEST_CASE("references recursively resolve references and environment values") {
    TempDir dir;
    write_file(dir, "first.json", R"({"x":{"$ref":"second.json#/y"}})");
    write_file(dir, "second.json", R"({"y":{"$env":"ARG"}})");
    auto inst = parse(R"({"argv":["x",{"$ref":"first.json#/x"}]})");
    aos::ResolveResult result;

    REQUIRE(aos::resolve(inst, file_context(dir), result) ==
            aos::ResolveState::Ok);
    CHECK(inst.argv[1] == "argument");
}

TEST_CASE("reference chains have no fixed depth limit") {
    TempDir dir;
    for (int index = 1; index <= 5; ++index) {
        write_file(dir, "level" + std::to_string(index) + ".json",
                   R"({"x":{"$ref":"level)" + std::to_string(index + 1) +
                       R"(.json#/x"}})");
    }
    write_file(dir, "level6.json", R"({"x":"deep-value"})");
    auto inst = parse(R"({"argv":["x",{"$ref":"level1.json#/x"}]})");
    aos::ResolveResult result;

    REQUIRE(aos::resolve(inst, file_context(dir), result) ==
            aos::ResolveState::Ok);
    CHECK(inst.argv[1] == "deep-value");
}

TEST_CASE("reference cycles report the complete normalized chain") {
    TempDir dir;
    write_file(dir, "a.json", R"({"x":{"$ref":"b.json#/y"}})");
    write_file(dir, "b.json", R"({"y":{"$ref":"a.json#/x"}})");
    auto inst = parse(R"({"argv":["x",{"$ref":"a.json#/x"}]})");
    aos::ResolveResult result;

    REQUIRE(aos::resolve(inst, file_context(dir), result) ==
            aos::ResolveState::ReferenceCycle);
    REQUIRE(result.reference_chain.size() == 3);
    CHECK(result.reference_chain.front() == dir.path + "/a.json#/x");
    CHECK(result.reference_chain[1] == dir.path + "/b.json#/y");
    CHECK(result.reference_chain.back() == dir.path + "/a.json#/x");
}

TEST_CASE("same file different pointers are not a cycle") {
    TempDir dir;
    write_file(dir, "a.json",
               R"({"x":{"$ref":"a.json#/y"},"y":"value"})");
    auto inst = parse(R"({"argv":["x",{"$ref":"a.json#/x"}]})");
    aos::ResolveResult result;

    REQUIRE(aos::resolve(inst, file_context(dir), result) ==
            aos::ResolveState::Ok);
    CHECK(inst.argv[1] == "value");
}

TEST_CASE("normalized path spelling cannot evade cycle detection") {
    TempDir dir;
    write_file(dir, "a.json", R"({"x":{"$ref":"./a.json#/x"}})");
    auto inst = parse(R"({"argv":["x",{"$ref":"a.json#/x"}]})");
    aos::ResolveResult result;

    REQUIRE(aos::resolve(inst, file_context(dir), result) ==
            aos::ResolveState::ReferenceCycle);
    REQUIRE(result.reference_chain.size() == 2);
    CHECK(result.reference_chain[0] == result.reference_chain[1]);
}

TEST_CASE("referenced merge option is legal only at stderr") {
    TempDir dir;
    write_file(dir, "option.json", R"({"merge":{"$opt":"merge"}})");
    auto stderr_inst = parse(
        R"({"argv":["x"],"stderr":{"$ref":"option.json#/merge"}})");
    auto argv_inst = parse(
        R"({"argv":["x",{"$ref":"option.json#/merge"}]})");
    aos::ResolveResult result;

    REQUIRE(aos::resolve(stderr_inst, file_context(dir), result) ==
            aos::ResolveState::Ok);
    CHECK(stderr_inst.stderr_merge);
    CHECK(aos::resolve(argv_inst, file_context(dir), result) ==
          aos::ResolveState::ReferenceValueInvalid);
}

TEST_CASE("references use base path and RFC 6901 pointer escaping") {
    TempDir dir;
    write_file(dir, "pointer.json", R"({"a/b":{"~key":"escaped"}})");
    auto inst = parse(
        R"({"argv":["x",{"$ref":"pointer.json#/a~1b/~0key"}]})");
    aos::ResolveResult result;

    REQUIRE(aos::resolve(inst, file_context(dir), result) ==
            aos::ResolveState::Ok);
    CHECK(inst.argv[1] == "escaped");
}

TEST_CASE("reference without hash may select a top level string") {
    TempDir dir;
    write_file(dir, "value.json", R"("whole-document")");
    auto inst = parse(R"({"argv":["x",{"$ref":"value.json"}]})");
    aos::ResolveResult result;

    REQUIRE(aos::resolve(inst, file_context(dir), result) ==
            aos::ResolveState::Ok);
    CHECK(inst.argv[1] == "whole-document");
}
