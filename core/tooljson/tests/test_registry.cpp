#include <aos/tooljson.hpp>

#include "test_support.hpp"

#include <catch2/catch_test_macros.hpp>

#include <algorithm>
#include <memory>
#include <string>

namespace {

class EchoBody final : public aos::tooljson::Body {
public:
    explicit EchoBody(std::string extra) : extra_(std::move(extra)) {}

    std::string run(const char *args, std::size_t size) const override {
        return "echo " + std::string(args, size) + " via " + extra_;
    }

    std::string target() const override { return {}; }

private:
    std::string extra_;
};

}  // namespace

TEST_CASE("unknown and python types report all currently registered types") {
    const std::string input =
        R"({"type":"function","function":{"name":"py"},"_extra":{"_version":"0.1.0","_type":"python"}})";
    aos::tooljson::Spec spec;
    std::string message;
    CHECK(aos::tooljson::load(input.data(), input.size(), "/tmp", spec,
                              message) == aos::tooljson::SpecState::UnknownType);
    CHECK(message.find("目前登記的只有") != std::string::npos);
    CHECK(message.find("'exec'") != std::string::npos);
    CHECK(message.find("'python'") != std::string::npos);
}

TEST_CASE("third-party types use the public registry and string JSON boundary") {
    std::string message;
    REQUIRE(aos::tooljson::register_type(
                "echo",
                [](const aos::tooljson::Spec &spec,
                   aos::tooljson::BodyPtr &body,
                   std::string &error) {
                    const std::string extra = spec.extra_json();
                    if (extra.find("\"prefix\":\"說\"") == std::string::npos) {
                        error = "_extra.prefix 缺了";
                        return aos::tooljson::SpecState::InvalidFormat;
                    }
                    body = std::make_shared<EchoBody>(extra);
                    return aos::tooljson::SpecState::Ok;
                },
                message) == aos::tooljson::SpecState::Ok);

    const std::string input =
        R"({"type":"function","function":{"name":"say"},"_extra":{"_version":"0.1.0","_type":"echo","prefix":"說"}})";
    aos::tooljson::Spec spec;
    REQUIRE(aos::tooljson::load(input.data(), input.size(), "/tmp", spec,
                                message) == aos::tooljson::SpecState::Ok);
    CHECK(spec.type() == "echo");
    CHECK(spec.run("{\"x\":1}", 7).find("echo {\"x\":1}") == 0);
    CHECK(spec.target().empty());

    const auto types = aos::tooljson::registered_types();
    CHECK(std::is_sorted(types.begin(), types.end()));
    CHECK(std::find(types.begin(), types.end(), "echo") != types.end());
}

TEST_CASE("exec body is registered through the same public registry") {
    const auto types = aos::tooljson::registered_types();
    CHECK(std::find(types.begin(), types.end(), "exec") != types.end());

    const aos::tooljson::Spec spec = parse_spec(exec_spec());
    CHECK(spec.run("{}", 2) ==
          "Error: exec execution is not implemented in S1");
}
