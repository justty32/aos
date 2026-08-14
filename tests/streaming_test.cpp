// 這支測試證明兩件事：
//   1. 訊框在真的 socket 上進出後內容不變，包含含 NUL 的二進位資料。
//   2. 命令是「邊讀邊寫」的，不是先把 stdin 收完才輸出。
#include "aos/channel.hpp"
#include "aos/command.hpp"
#include "aos/runtime.hpp"

#include "check.hpp"

#include <asio/co_spawn.hpp>
#include <asio/detached.hpp>
#include <asio/io_context.hpp>
#include <asio/local/connect_pair.hpp>
#include <asio/use_awaitable.hpp>

#include <format>
#include <string>
#include <string_view>
#include <vector>

namespace {

// 假的 Session：把每一次讀寫依序記下來，之後就能檢查交錯順序。
class RecordingSession final : public aos::Session {
public:
    explicit RecordingSession(std::vector<std::string> input)
        : input_{std::move(input)} {}

    asio::awaitable<std::string> read_input() override {
        if (next_ == input_.size()) {
            events_.emplace_back("read:eof");
            co_return std::string{};
        }
        auto chunk = input_[next_++];
        events_.push_back(std::format("read:{}", chunk));
        co_return chunk;
    }

    asio::awaitable<void> write_output(std::string_view text) override {
        events_.push_back(std::format("out:{}", text));
        output_ += text;
        co_return;
    }

    asio::awaitable<void> write_error(std::string_view text) override {
        events_.push_back(std::format("err:{}", text));
        error_ += text;
        co_return;
    }

    [[nodiscard]] const std::vector<std::string>& events() const { return events_; }
    [[nodiscard]] const std::string& output() const { return output_; }
    [[nodiscard]] const std::string& error() const { return error_; }

private:
    std::vector<std::string> input_;
    std::size_t next_ = 0;
    std::vector<std::string> events_;
    std::string output_;
    std::string error_;
};

[[nodiscard]] std::int32_t run_command(const aos::Request& request,
                                       RecordingSession& session) {
    asio::io_context context;
    aos::Runtime runtime{context};
    std::int32_t exit_code = -1;
    asio::co_spawn(context, aos::handle_command(request, session, runtime),
                   [&](std::exception_ptr failure, std::int32_t code) {
                       AOS_CHECK(!failure);
                       exit_code = code;
                   });
    context.run();
    return exit_code;
}

void test_echo_interleaves_input_and_output() {
    RecordingSession session{{"one", "two", "three"}};
    const aos::Request request{.arguments = {"echo"}, .working_directory = "/tmp"};

    AOS_CHECK(run_command(request, session) == 0);
    AOS_CHECK(session.output() == "onetwothree");

    // 關鍵斷言：讀一塊就寫一塊。如果實作偷偷先收完 stdin，
    // 事件會變成 read,read,read,...,out，這裡就會失敗。
    const std::vector<std::string> expected{
        "read:one", "out:one", "read:two", "out:two",
        "read:three", "out:three", "read:eof",
    };
    AOS_CHECK(session.events() == expected);
}

void test_ping_does_not_touch_input() {
    RecordingSession session{{"ignored"}};
    const aos::Request request{.arguments = {"ping"}, .working_directory = "/tmp"};

    AOS_CHECK(run_command(request, session) == 0);
    AOS_CHECK(session.output() == "pong\n");
    AOS_CHECK(session.events() == std::vector<std::string>{"out:pong\n"});
}

void test_empty_arguments_report_usage() {
    RecordingSession session{{}};
    const aos::Request request{.arguments = {}, .working_directory = "/tmp"};

    AOS_CHECK(run_command(request, session) == 2);
    AOS_CHECK(session.output().empty());
    AOS_CHECK(session.error().starts_with("用法："));
    AOS_CHECK(session.error().contains("ping"));
}

void test_frames_survive_a_real_socket() {
    asio::io_context context;
    aos::LocalSocket writer{context};
    aos::LocalSocket reader{context};
    asio::local::connect_pair(writer, reader);

    // 含 NUL 的二進位資料，確認長度是靠 header 而不是靠終止字元。
    const std::string payload{"文字\0binary", 13};
    // 空 payload 也要能正確往返，stdin_end 就是這種訊框。
    const std::string empty;

    std::string received_payload;
    std::string received_empty;
    bool kinds_match = false;

    asio::co_spawn(context, [&]() -> asio::awaitable<void> {
        co_await aos::write_frame(writer, aos::FrameKind::stdin_chunk, payload);
        co_await aos::write_frame(writer, aos::FrameKind::stdin_end, empty);
    }, asio::detached);

    asio::co_spawn(context, [&]() -> asio::awaitable<void> {
        const auto first = co_await aos::read_frame(reader);
        const auto second = co_await aos::read_frame(reader);
        received_payload = first.payload;
        received_empty = second.payload;
        kinds_match = first.kind == aos::FrameKind::stdin_chunk &&
                      second.kind == aos::FrameKind::stdin_end;
    }, asio::detached);

    context.run();

    AOS_CHECK(kinds_match);
    AOS_CHECK(received_payload == payload);
    AOS_CHECK(received_empty.empty());
}

// 超過單一訊框上限的資料要被自動切塊，而不是丟例外。
void test_large_output_is_split_into_chunks() {
    asio::io_context context;
    aos::LocalSocket writer{context};
    aos::LocalSocket reader{context};
    asio::local::connect_pair(writer, reader);

    const std::string bytes(aos::stream_chunk_size * 3 + 7, 'x');
    std::string received;
    int frame_count = 0;

    asio::co_spawn(context, [&]() -> asio::awaitable<void> {
        co_await aos::write_stream(writer, aos::FrameKind::stdout_chunk, bytes);
        writer.close();
    }, asio::detached);

    asio::co_spawn(context, [&]() -> asio::awaitable<void> {
        try {
            while (true) {
                const auto frame = co_await aos::read_frame(reader);
                received += frame.payload;
                ++frame_count;
            }
        } catch (const std::system_error&) {
            // 對方關閉連線，讀到 eof 就是正常結束。
        }
    }, asio::detached);

    context.run();

    AOS_CHECK(frame_count == 4);
    AOS_CHECK(received == bytes);
}

}  // namespace

int main() {
    test_echo_interleaves_input_and_output();
    test_ping_does_not_touch_input();
    test_empty_arguments_report_usage();
    test_frames_survive_a_real_socket();
    test_large_output_is_split_into_chunks();
    return aos::testing::report();
}
