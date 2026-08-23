#include <aos/tooljson.hpp>

#include "test_support.hpp"

#include <catch2/catch_test_macros.hpp>

#include <string>
#include <vector>

namespace {

aos::tooljson::ExpandedArgs expand(const aos::tooljson::Spec &spec,
                                    const std::string &json) {
    aos::tooljson::ExpandedArgs out;
    const std::string error =
        aos::tooljson::expand_args(spec, json.data(), json.size(), out);
    INFO(error);
    REQUIRE(error.empty());
    return out;
}

}  // namespace

TEST_CASE("argv order uses position then Unicode code point") {
    const aos::tooljson::Spec spec = parse_spec(exec_spec(
        "order",
        R"("😀":{"type":"string"},"later":{"type":"string"},"中":{"type":"string"},"ascii":{"type":"string"},"first":{"type":"string"})",
        "[]",
        R"("exec":["cmd"],"argv":{"😀":{"position":2},"later":{"position":9},"中":{"position":2},"ascii":{"position":2},"first":{"position":-1}})"));

    const auto out = expand(
        spec,
        R"({"later":"L","中":"C","first":"F","😀":"E","ascii":"A"})");
    CHECK(out.argv ==
          std::vector<std::string>{"cmd", "F", "A", "C", "E", "L"});
}

TEST_CASE("JSON literals flags switches repeat and separate expand exactly") {
    const aos::tooljson::Spec spec = parse_spec(exec_spec(
        "shape",
        R"("text":{"type":"string"},"count":{"type":"integer"},"ratio":{"type":"number"},"plain_bool":{"type":"boolean"},"width":{"type":"integer"},"force":{"type":"boolean"},"tag":{"type":"string"},"note":{"type":"string"})",
        "[]",
        R"("exec":["cmd"],"argv":{"text":{"position":1},"count":{"position":2},"ratio":{"position":3},"plain_bool":{"position":4},"width":{"position":5,"flag":"--width"},"force":{"position":6,"flag":"--force"},"tag":{"position":7,"flag":"--tag","repeat":true},"note":{"position":8,"flag":"--note","separate":false}})"));

    const auto out = expand(
        spec,
        R"({"text":"a b","count":800,"ratio":1.5,"plain_bool":false,"width":800,"force":true,"tag":["a","b"],"note":"one"})");
    CHECK(out.argv == std::vector<std::string>{
                          "cmd", "a b", "800", "1.5", "false", "--width",
                          "800", "--force", "--tag", "a", "--tag", "b",
                          "--note=one"});

    const auto disabled = expand(spec, R"({"force":false})");
    CHECK(disabled.argv == std::vector<std::string>{"cmd"});
}

TEST_CASE("coercion distinguishes failures from explicit null and absence") {
    const aos::tooljson::Spec spec = parse_spec(exec_spec(
        "coerce",
        R"("width":{"type":"integer"},"ratio":{"type":"number"},"force":{"type":"boolean"},"optional":{"type":"string"})",
        R"(["width"])",
        R"("exec":["cmd"],"argv":{"width":{"position":1},"ratio":{"position":2},"force":{"position":3,"flag":"--force"},"optional":{"position":4,"flag":"--optional"}})"));

    const auto out = expand(
        spec, R"({"width":" 800 ","ratio":"1.5","force":"TRUE","optional":null})");
    CHECK(out.argv ==
          std::vector<std::string>{"cmd", "800", "1.5", "--force"});

    aos::tooljson::ExpandedArgs unused;
    std::string bad = R"({"width":"eight"})";
    CHECK(aos::tooljson::expand_args(spec, bad.data(), bad.size(), unused)
              .find("width have the wrong type") != std::string::npos);
    const std::string null_value = R"({"width":null})";
    CHECK(aos::tooljson::expand_args(spec, null_value.data(), null_value.size(),
                                     unused)
              .find("missing required argument") != std::string::npos);
    const std::string absent = R"({})";
    CHECK(aos::tooljson::expand_args(spec, absent.data(), absent.size(), unused)
              .find("missing required argument") != std::string::npos);
}

TEST_CASE("bad arrays and unknown parameters return model-readable errors") {
    const aos::tooljson::Spec spec = parse_spec(exec_spec(
        "strict", R"("one":{"type":"string"})", "[]",
        R"("exec":["cmd"],"argv":{"one":{}})"));
    aos::tooljson::ExpandedArgs out;

    const std::string array = R"({"one":["a","b"]})";
    CHECK(aos::tooljson::expand_args(spec, array.data(), array.size(), out) ==
          "Error: argument 'one' does not take a list of values");
    const std::string unknown = R"({"zzz":1})";
    const std::string error =
        aos::tooljson::expand_args(spec, unknown.data(), unknown.size(), out);
    CHECK(error.find("Error: unknown argument(s): zzz") == 0);
    CHECK(error.find("This tool accepts: one") != std::string::npos);
}

TEST_CASE("stdin parameters are rendered but excluded from argv") {
    const aos::tooljson::Spec spec = parse_spec(exec_spec(
        "filter", R"("text":{"type":"string"},"mode":{"type":"string"})",
        "[]",
        R"("exec":["filter"],"argv":{"text":{"position":1},"mode":{"position":2}},"stdin":{"param":"text"})"));
    const auto out = expand(spec, R"({"text":"內容","mode":"fast"})");
    CHECK(out.argv == std::vector<std::string>{"filter", "fast"});
    REQUIRE(out.stdin_text.has_value());
    CHECK(*out.stdin_text == "內容");

    const auto absent = expand(spec, R"({"mode":"fast"})");
    CHECK_FALSE(absent.stdin_text.has_value());
}

TEST_CASE("limits count UTF-8 bytes and command-line items have a hard cap") {
    const aos::tooljson::Spec limited = parse_spec(exec_spec(
        "limited", R"("text":{"type":"string"},"width":{"type":"integer"})",
        "[]",
        R"("exec":["cmd"],"argv":{"text":{},"width":{"flag":"--width"}},"limits":{"text":{"max_bytes":3},"width":{"min":1,"max":10}})"));
    aos::tooljson::ExpandedArgs out;
    const std::string utf8 = R"({"text":"éé"})";
    CHECK(aos::tooljson::expand_args(limited, utf8.data(), utf8.size(), out) ==
          "Error: argument 'text' is 4 bytes, over the 3 limit");
    const std::string low = R"({"width":0})";
    CHECK(aos::tooljson::expand_args(limited, low.data(), low.size(), out)
              .find("below the minimum 1") != std::string::npos);

    const aos::tooljson::Spec uncapped = parse_spec(exec_spec(
        "uncapped", R"("text":{"type":"string"})", "[]",
        R"("exec":["cmd"],"argv":{"text":{}})"));
    const std::string huge_value(128 * 1024 + 1, 'x');
    const std::string huge = "{\"text\":\"" + huge_value + "\"}";
    CHECK(aos::tooljson::expand_args(uncapped, huge.data(), huge.size(), out)
              .find("limit 131072") != std::string::npos);
}
