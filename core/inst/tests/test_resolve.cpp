#include <aos/inst.hpp>

#include <catch2/catch_test_macros.hpp>

#include <string>
#include <filesystem>
#include <fstream>
#include <vector>

namespace {

aos::inst_t parse(const std::string &document) {
    aos::inst_t inst;
    REQUIRE(aos::read_one(document.data(), document.size(), inst) ==
            aos::InstState::Ok);
    return inst;
}

aos::ResolveContext context() {
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

void write_file(const TempDir &dir, const std::string &name,
                const std::string &content) {
    std::ofstream output(dir.path + "/" + name);
    REQUIRE(static_cast<bool>(output));
    output << content;
    REQUIRE(static_cast<bool>(output));
}

aos::ResolveContext file_context(const TempDir &dir) {
    aos::ResolveContext value = context();
    value.base_path = dir.path;
    return value;
}

}  // namespace

TEST_CASE("environment directives resolve in every string value position") {
    aos::inst_t inst = parse(
        R"({"argv":["command",{"$env":"ARG"}],"stdin":{"$env":"IN"},"stdout":{"$env":"OUT"},"stderr":{"$env":"ERR"},"exit":{"$env":"EXIT"},"cwd":{"$env":"CWD"},"env":{"KEY":{"$env":"VALUE"}}})");
    aos::ResolveResult result;

    REQUIRE(aos::resolve(inst, context(), result) == aos::ResolveState::Ok);
    CHECK(inst.argv == std::vector<std::string>{"command", "argument"});
    CHECK(inst.stdin_path == "input");
    CHECK(inst.stdout_path == "output");
    CHECK(inst.stderr_path == "error");
    CHECK_FALSE(inst.stderr_merge);
    CHECK(inst.exit_path == "status");
    CHECK(inst.cwd == "work");
    CHECK(inst.env == std::map<std::string, std::string>{{"KEY", "env-value"}});
    CHECK(inst.pending_directives.empty());
}

TEST_CASE("missing environment variable reports its variable and position") {
    aos::inst_t inst = parse(
        R"({"argv":["command",{"$env":"MISSING"}]})");
    aos::ResolveResult result;

    CHECK(aos::resolve(inst, context(), result) ==
          aos::ResolveState::EnvironmentVariableMissing);
    CHECK(result.variable == "MISSING");
    CHECK(result.field == aos::DirectiveField::Argv);
    CHECK(result.argv_index == 1);
    CHECK(inst.pending_directives.size() == 1);
}

TEST_CASE("empty resolved argv zero is rejected after resolution") {
    aos::inst_t inst = parse(R"({"argv":[{"$env":"EMPTY"}]})");
    aos::ResolveContext ctx;
    ctx.environment["EMPTY"] = "";
    aos::ResolveResult result;

    CHECK(aos::resolve(inst, ctx, result) ==
          aos::ResolveState::ValidationFailed);
    CHECK(result.validation_state == aos::InstState::EmptyArgv);
    CHECK(inst.pending_directives.size() == 1);
}

TEST_CASE("unresolved environment directives round trip without loss") {
    const std::string document =
        R"({"argv":["command",{"$env":"ARG"}],"stderr":{"$env":"ERR"},"env":{"KEY":{"$env":"VALUE"}}})";
    aos::inst_t inst = parse(document);
    std::string encoded;

    REQUIRE(aos::write_one(inst, encoded) == aos::InstState::Ok);
    CHECK(encoded == document + "\n");
}

TEST_CASE("stderr accepts literal merge and environment directive forms") {
    aos::inst_t literal = parse(R"({"argv":["x"],"stderr":"error"})");
    aos::inst_t merge = parse(
        R"({"argv":["x"],"stderr":{"$opt":"merge"}})");
    aos::inst_t environment = parse(
        R"({"argv":["x"],"stderr":{"$env":"ERR"}})");
    aos::ResolveResult result;

    CHECK(literal.stderr_path == "error");
    CHECK(merge.stderr_merge);
    REQUIRE(aos::resolve(environment, context(), result) ==
            aos::ResolveState::Ok);
    CHECK(environment.stderr_path == "error");
    CHECK_FALSE(environment.stderr_merge);
}

TEST_CASE("directives remain forbidden in non string value positions") {
    aos::inst_t inst;
    const std::string timeout =
        R"({"argv":["x"],"timeout_ms":{"$env":"TIMEOUT"}})";
    CHECK(aos::read_one(timeout.data(), timeout.size(), inst) ==
          aos::InstState::FieldTypeMismatch);

    const std::string env_not_an_object =
        R"({"argv":["x"],"env":[{"$env":"ENV_KEY"}]})";
    CHECK(aos::read_one(env_not_an_object.data(), env_not_an_object.size(),
                        inst) == aos::InstState::FieldTypeMismatch);
}

TEST_CASE("capture environment keeps empty values and explicit base path") {
    const char *values[] = {"A=one", "EMPTY=", nullptr};
    aos::ResolveContext ctx;

    REQUIRE(aos::capture_environment(values, "/world", ctx) ==
            aos::ResolveState::Ok);
    CHECK(ctx.environment.at("A") == "one");
    CHECK(ctx.environment.at("EMPTY").empty());
    CHECK(ctx.base_path == "/world");
}

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
