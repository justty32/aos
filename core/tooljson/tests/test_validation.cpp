#include <aos/tooljson.hpp>

#include "test_support.hpp"

#include <catch2/catch_test_macros.hpp>

#include <string>
#include <vector>

namespace {

std::string reject_message(const std::string &input) {
    std::vector<aos::tooljson::Spec> out;
    std::string message;
    const aos::tooljson::SpecState state = aos::tooljson::load_all(
        input.data(), input.size(), "/tmp", out, message);
    CHECK(state != aos::tooljson::SpecState::Ok);
    CHECK(out.empty());
    return message;
}

}  // namespace

TEST_CASE("function schema shape is validated at load time") {
    CHECK(reject_message(R"({"type":"function","function":{"name":"x","description":1},"_extra":{"_version":"0.1.0","_type":"exec","exec":["x"]}})")
              .find("description") != std::string::npos);
    CHECK(reject_message(R"({"type":"function","function":{"name":"x","parameters":null},"_extra":{"_version":"0.1.0","_type":"exec","exec":["x"]}})")
              .find("parameters") != std::string::npos);
    CHECK(reject_message(R"({"type":"function","function":{"name":"x","parameters":{"type":"array"}},"_extra":{"_version":"0.1.0","_type":"exec","exec":["x"]}})")
              .find("type") != std::string::npos);
    CHECK(reject_message(R"({"type":"function","function":{"name":"x","parameters":{"properties":[]}},"_extra":{"_version":"0.1.0","_type":"exec","exec":["x"]}})")
              .find("properties") != std::string::npos);
    CHECK(reject_message(R"({"type":"function","function":{"name":"x","parameters":{"properties":{"p":"string"}}},"_extra":{"_version":"0.1.0","_type":"exec","exec":["x"]}})")
              .find("schema object") != std::string::npos);
    CHECK(reject_message(R"({"type":"function","function":{"name":"x","parameters":{"properties":{"p":{}},"required":["p","p"]}},"_extra":{"_version":"0.1.0","_type":"exec","exec":["x"]}})")
              .find("重複") != std::string::npos);
    CHECK(reject_message(R"({"type":"function","function":{"name":"x","parameters":{"properties":{"p":{}},"required":["missing"]}},"_extra":{"_version":"0.1.0","_type":"exec","exec":["x"]}})")
              .find("未知參數") != std::string::npos);
}

TEST_CASE("exec recipe shape is validated at load time") {
    CHECK(reject_message(exec_spec("x", {}, "[]", R"("exec":[])"))
              .find("exec") != std::string::npos);
    CHECK(reject_message(exec_spec("x", {}, "[]",
                                   R"("exec":["x"],"argv":null)"))
              .find("argv") != std::string::npos);
    CHECK(reject_message(exec_spec("x", R"("p":{})", "[]",
                                   R"("exec":["x"],"argv":{"missing":{}})"))
              .find("parameters 裡沒這個") != std::string::npos);
    CHECK(reject_message(exec_spec("x", R"("p":{})", "[]",
                                   R"("exec":["x"],"argv":{"p":{"position":true}})"))
              .find("position") != std::string::npos);
    CHECK(reject_message(exec_spec("x", R"("p":{})", "[]",
                                   R"("exec":["x"],"stdin":{"param":"p","extra":1})"))
              .find("stdin") != std::string::npos);
    CHECK(reject_message(exec_spec("x", {}, "[]",
                                   R"("exec":["x"],"stdout":{"clip":"middle"})"))
              .find("clip") != std::string::npos);
    CHECK(reject_message(exec_spec("x", {}, "[]",
                                   R"("exec":["x"],"stderr":{"mode":"both"})"))
              .find("mode") != std::string::npos);
    CHECK(reject_message(exec_spec("x", {}, "[]",
                                   R"("exec":["x"],"ok_exit":[true])"))
              .find("ok_exit") != std::string::npos);
    CHECK(reject_message(exec_spec("x", {}, "[]",
                                   R"("exec":["x"],"timeout":0)"))
              .find("timeout") != std::string::npos);
    CHECK(reject_message(exec_spec("x", {}, "[]",
                                   R"("exec":["x"],"cwd":"")"))
              .find("cwd") != std::string::npos);
    CHECK(reject_message(exec_spec("x", {}, "[]",
                                   R"("exec":["x"],"source":"old metadata")"))
              .find("source") != std::string::npos);
    CHECK(reject_message(exec_spec("x", {}, "[]",
                                   R"("exec":["x"],"source":{"size":true})"))
              .find("source.size") != std::string::npos);
}

TEST_CASE("exec limits are validated at load time") {
    CHECK(reject_message(exec_spec("x", R"("p":{})", "[]",
                                   R"("exec":["x"],"limits":[])"))
              .find("limits") != std::string::npos);
    CHECK(reject_message(exec_spec("x", R"("p":{})", "[]",
                                   R"("exec":["x"],"limits":{"missing":{"max_bytes":1}})"))
              .find("未知參數") != std::string::npos);
    CHECK(reject_message(exec_spec("x", R"("p":{})", "[]",
                                   R"("exec":["x"],"limits":{"p":{"max_bytes":true}})"))
              .find("max_bytes") != std::string::npos);
    CHECK(reject_message(exec_spec("x", R"("p":{})", "[]",
                                   R"("exec":["x"],"limits":{"p":{"min":2,"max":1}})"))
              .find("min 不可大於 max") != std::string::npos);
}
