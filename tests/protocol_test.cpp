#include "aos/channel.hpp"
#include "aos/protocol.hpp"

#include <asio/io_context.hpp>
#include <asio/local/connect_pair.hpp>

#include <cassert>
#include <cstddef>
#include <string>

int main() {
    const aos::Request request{
        .arguments = {"new", "bot alpha", "", "A \"special\" bot", "繁體中文"},
        .working_directory = "/tmp/a directory",
        .standard_input = {},
    };
    const auto request_json = aos::encode_request_start(request);
    assert(request_json);
    assert(request_json->contains("\"arguments\""));
    const auto decoded_request = aos::decode_request_start(*request_json);
    assert(decoded_request);
    assert(*decoded_request == request);
    assert(!aos::decode_request_start("not json"));

    const auto exit_json = aos::encode_exit(-7);
    const auto decoded_exit = aos::decode_exit(exit_json);
    assert(decoded_exit && *decoded_exit == -7);

    asio::io_context context;
    aos::LocalSocket first{context};
    aos::LocalSocket second{context};
    asio::local::connect_pair(first, second);
    const std::string bytes{"文字\0binary", 13};
    aos::write_frame(first, aos::FrameKind::stdin_chunk, bytes);
    const auto frame = aos::read_frame(second);
    assert(frame.kind == aos::FrameKind::stdin_chunk);
    assert(frame.payload == bytes);
}
