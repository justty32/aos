#include <aos/tooljson.hpp>

#include "test_support.hpp"

#include <catch2/catch_test_macros.hpp>

#include <filesystem>
#include <string>
#include <vector>

TEST_CASE("spec accepts one object and strips _extra from schema") {
    const std::string input = exec_spec();
    aos::tooljson::Spec spec;
    std::string message;

    REQUIRE(aos::tooljson::load(input.data(), input.size(), "/tmp", spec,
                                message) == aos::tooljson::SpecState::Ok);
    CHECK(spec.name() == "probe");
    CHECK(spec.description() == "說明 probe");
    CHECK(spec.type() == "exec");
    CHECK(spec.schema_json().find("_extra") == std::string::npos);
    CHECK(spec.schema_json().find("\"name\":\"probe\"") != std::string::npos);
    CHECK(spec.extra_json().find("\"_type\":\"exec\"") != std::string::npos);
}

TEST_CASE("spec accepts arrays and rejects duplicate names in one file") {
    const std::string first = exec_spec("first");
    const std::string second = exec_spec("second");
    const std::string input = "[" + first + "," + second + "]";
    std::vector<aos::tooljson::Spec> specs;
    std::string message;

    REQUIRE(aos::tooljson::load_all(input.data(), input.size(), "/tmp", specs,
                                    message) == aos::tooljson::SpecState::Ok);
    REQUIRE(specs.size() == 2);
    CHECK(specs[0].name() == "first");
    CHECK(specs[1].name() == "second");

    const std::string duplicate = "[" + first + "," + first + "]";
    CHECK(aos::tooljson::load_all(duplicate.data(), duplicate.size(), "/tmp",
                                  specs, message) ==
          aos::tooljson::SpecState::DuplicateName);
    CHECK(message.find("重複的 function.name ['first']") != std::string::npos);
    CHECK(specs.empty());
}

TEST_CASE("empty arrays and incompatible versions are rejected") {
    std::vector<aos::tooljson::Spec> specs;
    std::string message;
    const std::string empty = "[]";
    CHECK(aos::tooljson::load_all(empty.data(), empty.size(), "/tmp", specs,
                                  message) ==
          aos::tooljson::SpecState::InvalidFormat);
    CHECK(message.find("空的 array") != std::string::npos);

    std::string wrong = exec_spec();
    const std::size_t version = wrong.find("0.1.0");
    REQUIRE(version != std::string::npos);
    wrong.replace(version, 5, "0.2.0");
    CHECK(aos::tooljson::load_all(wrong.data(), wrong.size(), "/tmp", specs,
                                  message) ==
          aos::tooljson::SpecState::InvalidFormat);
    CHECK(message.find("這支只認得 '0.1.0'") != std::string::npos);
}

TEST_CASE("relative exec and cwd paths use the JSON directory") {
    const std::string input = exec_spec(
        "resize", R"("path":{"type":"string"})", "[]",
        R"("exec":["../resize","fixed"],"argv":{"path":{"position":1}},"cwd":"../work")");
    const aos::tooljson::Spec spec = parse_spec(input, "/tmp/project/specs");
    const std::string args = R"({"path":"image.png"})";
    aos::tooljson::ExpandedArgs expanded;

    REQUIRE(aos::tooljson::expand_args(spec, args.data(), args.size(), expanded)
                .empty());
    REQUIRE(expanded.argv.size() == 3);
    CHECK(expanded.argv[0] == "/tmp/project/resize");
    CHECK(expanded.argv[1] == "fixed");
    CHECK(expanded.argv[2] == "image.png");

    const aos::tooljson::Spec path_lookup = parse_spec(exec_spec());
    REQUIRE(aos::tooljson::expand_args(path_lookup, "{}", 2, expanded).empty());
    CHECK(expanded.argv[0] == "probe");
}

TEST_CASE("cross-file duplicate names keep the earlier file") {
    TooljsonTempDir dir;
    const std::string first = dir.path + "/first.json";
    const std::string second = dir.path + "/second.json";
    write_tooljson_file(first, exec_spec("same", {}, "[]",
                                        R"("exec":["first"],"argv":{})"));
    write_tooljson_file(second, exec_spec("same", {}, "[]",
                                         R"("exec":["second"],"argv":{})"));

    std::vector<aos::tooljson::Spec> specs;
    std::string message;
    REQUIRE(aos::tooljson::load_all(std::vector<std::string>{first, second},
                                    specs, message) ==
            aos::tooljson::SpecState::Ok);
    REQUIRE(specs.size() == 1);
    aos::tooljson::ExpandedArgs expanded;
    REQUIRE(aos::tooljson::expand_args(specs[0], "{}", 2, expanded).empty());
    REQUIRE(expanded.argv == std::vector<std::string>{"first"});
}

TEST_CASE("save writes JSON which can be loaded") {
    TooljsonTempDir dir;
    const std::string nested = dir.path + "/nested/probe.json";
    const std::string input = exec_spec();
    std::string message;
    REQUIRE(aos::tooljson::save(input.data(), input.size(), nested.c_str(),
                                message) == aos::tooljson::SpecState::Ok);
    aos::tooljson::Spec loaded;
    REQUIRE(aos::tooljson::load(nested.c_str(), loaded, message) ==
            aos::tooljson::SpecState::Ok);
    CHECK(loaded.name() == "probe");
}

TEST_CASE("stale compares source sha256 and reports unknown when unusable") {
    TooljsonTempDir dir;
    const std::string program = dir.path + "/program";
    write_tooljson_file(program, "abc");
    const std::string input = exec_spec(
        "fingerprint", {}, "[]",
        R"("exec":["./program"],"argv":{},"source":{"sha256":"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"})");
    const aos::tooljson::Spec spec = parse_spec(input, dir.path.c_str());
    REQUIRE(spec.stale().has_value());
    CHECK_FALSE(*spec.stale());

    write_tooljson_file(program, "changed");
    REQUIRE(spec.stale().has_value());
    CHECK(*spec.stale());

    const aos::tooljson::Spec malformed = parse_spec(exec_spec(
        "unknown", {}, "[]",
        R"("exec":["./program"],"argv":{},"source":{})"),
        dir.path.c_str());
    CHECK_FALSE(malformed.stale().has_value());
}
