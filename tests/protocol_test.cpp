#include "aos/protocol.hpp"

#include "check.hpp"

#include <string>

int main() {
    const aos::Request request{
        .arguments = {"new", "bot alpha", "", R"(A "special" bot)", "繁體中文"},
        .working_directory = "/tmp/a directory",
    };

    const auto encoded = aos::encode_request_start(request);
    AOS_CHECK(encoded.has_value());
    if (encoded) {
        AOS_CHECK(encoded->contains(R"("arguments")"));
        const auto decoded = aos::decode_request_start(*encoded);
        AOS_CHECK(decoded.has_value());
        // Request 已經沒有 standard_input 了，所以這是真正的完整 round trip。
        AOS_CHECK(decoded && *decoded == request);
    }

    AOS_CHECK(!aos::decode_request_start("not json"));
    AOS_CHECK(!aos::decode_request_start("[]"));
    AOS_CHECK(!aos::decode_request_start(R"({"version":999})"));
    AOS_CHECK(!aos::decode_request_start(R"({"version":1,"arguments":[]})"));

    const auto exit_json = aos::encode_exit(-7);
    const auto exit_code = aos::decode_exit(exit_json);
    AOS_CHECK(exit_code && *exit_code == -7);
    AOS_CHECK(!aos::decode_exit("{}"));
    AOS_CHECK(!aos::decode_exit(R"({"exit_code":"nope"})"));

    AOS_CHECK(aos::is_known_frame_kind(aos::FrameKind::request_start));
    AOS_CHECK(!aos::is_known_frame_kind(static_cast<aos::FrameKind>(99)));

    return aos::testing::report();
}
