#include <aos/agent.hpp>
#include <aos/loop.hpp>

#include <cerrno>
#include <charconv>
#include <chrono>
#include <csignal>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <string_view>
#include <system_error>
#include <thread>

#include <unistd.h>

namespace {

struct Options {
    aos::agent::Engine engine;
    std::uint64_t timeout_ms = 300000;
    bool engine_given = false;
    bool provider_given = false;
    bool model_given = false;
    int text_start = 1;
};

int usage(const char *program) {
    std::fprintf(stderr,
                 "usage: %s [--engine lmstudio|pi] [--provider P] "
                 "[--model M] [--timeout MS] <text...>\n",
                 program);
    return 2;
}

bool parse_unsigned(const char *text, std::uint64_t &value) {
    if (text == nullptr || *text == '\0') return false;
    const std::string_view input(text);
    const auto parsed =
        std::from_chars(input.data(), input.data() + input.size(), value);
    return parsed.ec == std::errc{} &&
           parsed.ptr == input.data() + input.size();
}

bool parse_options(int argc, char *argv[], Options &options) {
    int index = 1;
    while (index < argc && argv[index] != nullptr &&
           std::string_view(argv[index]).starts_with("--")) {
        if (index + 1 >= argc || argv[index + 1] == nullptr) return false;
        const std::string_view option(argv[index]);
        if (option == "--engine") {
            options.engine.kind = argv[index + 1];
            options.engine_given = true;
        } else if (option == "--provider") {
            options.engine.provider = argv[index + 1];
            options.provider_given = true;
        } else if (option == "--model") {
            options.engine.model = argv[index + 1];
            options.model_given = true;
        } else if (option == "--timeout") {
            if (!parse_unsigned(argv[index + 1], options.timeout_ms)) {
                return false;
            }
        } else {
            return false;
        }
        index += 2;
    }
    if (options.engine.kind != "lmstudio" && options.engine.kind != "pi") {
        return false;
    }
    options.text_start = index;
    return index < argc;
}

std::string joined_text(int argc, char *argv[], int first) {
    std::string text;
    for (int index = first; index < argc; ++index) {
        if (index != first) text.push_back(' ');
        text += argv[index];
    }
    return text;
}

std::string find_agent(const std::filesystem::path &folder) {
    const std::filesystem::path agents = folder / ".aos" / "agents";
    std::error_code error;
    std::filesystem::directory_iterator entries(agents, error);
    const std::filesystem::directory_iterator end;
    std::string name;
    while (!error && entries != end) {
        if (entries->is_directory(error) && !error) {
            if (!name.empty()) {
                throw std::runtime_error("這個資料夾有不只一隻 agent");
            }
            name = entries->path().filename().string();
        }
        entries.increment(error);
    }
    return name;
}

bool parse_pid(std::string_view text, pid_t &pid) {
    while (!text.empty() && (text.back() == '\n' || text.back() == '\r')) {
        text.remove_suffix(1);
    }
    long long value = 0;
    const auto parsed =
        std::from_chars(text.data(), text.data() + text.size(), value);
    if (text.empty() || parsed.ec != std::errc{} ||
        parsed.ptr != text.data() + text.size() || value <= 0) {
        return false;
    }
    pid = static_cast<pid_t>(value);
    return static_cast<long long>(pid) == value;
}

bool loop_is_alive(const std::filesystem::path &folder) {
    std::ifstream input(folder / ".aos" / "run.pid", std::ios::binary);
    if (!input) return false;
    const std::string text{std::istreambuf_iterator<char>(input),
                           std::istreambuf_iterator<char>()};
    pid_t pid = -1;
    if (!parse_pid(text, pid)) return false;
    if (::kill(pid, 0) == 0) return true;
    return errno != ESRCH;
}

bool print_reply(const std::vector<aos::agent::Message> &history,
                 std::size_t baseline) {
    if (history.size() <= baseline || history.back().role != "assistant") {
        return false;
    }
    const std::string &content = history.back().content;
    std::fwrite(content.data(), 1, content.size(), stdout);
    if (content.empty() || content.back() != '\n') std::fputc('\n', stdout);
    std::fflush(stdout);
    return true;
}

int check_result(const std::filesystem::path &folder, const std::string &name,
                 std::size_t baseline, aos::agent::Status &status) {
    if (print_reply(aos::agent::read_history(folder, name), baseline)) {
        return 0;
    }
    status = aos::agent::read_status(folder, name);
    if (!status.last_error.empty()) {
        std::fprintf(stderr, "aos chat: 上一回合失敗 — %s\n",
                     status.last_error.c_str());
        std::fputs("你的訊息還留在 say/，修好之後 aos run "
                   "一回合就會被回答\n",
                   stderr);
        return 1;
    }
    return -1;
}

void warn_ignored(const Options &options, const std::string &name) {
    std::string ignored;
    const auto add = [&ignored](std::string_view option) {
        if (!ignored.empty()) ignored += "、";
        ignored.append(option);
    };
    if (options.engine_given) add("--engine");
    if (options.provider_given) add("--provider");
    if (options.model_given) add("--model");
    if (!ignored.empty()) {
        std::fprintf(stderr, "aos chat: 已沿用 agent %s，忽略 %s\n",
                     name.c_str(), ignored.c_str());
    }
}

int run_chat(int argc, char *argv[], const char *program) {
    Options options;
    if (!parse_options(argc, argv, options)) return usage(program);

    const std::filesystem::path folder = aos::agent::resolve_folder();
    std::string name = find_agent(folder);
    if (name.empty()) {
        name = folder.filename().string();
        if (name.empty()) name = "agent";
        aos::agent::initialize(folder, name,
                               "你是一個可靠、好奇且言簡意賅的助手。",
                               options.engine);
        std::printf("已建立 agent %s（%s，%s）\n", name.c_str(),
                    folder.string().c_str(), options.engine.kind.c_str());
        std::fflush(stdout);
    } else {
        warn_ignored(options, name);
    }

    const std::size_t baseline =
        aos::agent::read_history(folder, name).size();
    aos::agent::say(folder, name,
                    joined_text(argc, argv, options.text_start),
                    aos::agent::say_from().string());

    const aos::loop::Layout layout =
        aos::loop::layout_of(folder.string());
    const auto started = std::chrono::steady_clock::now();
    const auto deadline =
        started + std::chrono::milliseconds(options.timeout_ms);
    auto next_progress = started + std::chrono::seconds(5);
    aos::agent::Status status = aos::agent::read_status(folder, name);

    while (true) {
        const int checked = check_result(folder, name, baseline, status);
        if (checked >= 0) return checked;

        const auto now = std::chrono::steady_clock::now();
        if (now >= deadline) {
            const auto seconds = (options.timeout_ms + 999) / 1000;
            std::fprintf(stderr,
                         "aos chat: 等了 %llu 秒還沒有回覆（狀態：%s）；"
                         "用 aos state 看、用 aos listen 跟讀\n",
                         static_cast<unsigned long long>(seconds),
                         status.status.c_str());
            return 1;
        }
        if (now >= next_progress) {
            std::fprintf(stderr, "…第 %llu 回合，%s\n",
                         static_cast<unsigned long long>(status.turn),
                         status.status.c_str());
            do {
                next_progress += std::chrono::seconds(5);
            } while (next_progress <= now);
        }

        if (loop_is_alive(folder)) {
            std::this_thread::sleep_for(std::chrono::milliseconds(200));
            continue;
        }

        aos::loop::TurnSummary summary;
        std::string error;
        if (!aos::loop::run_turn(layout, summary, error)) {
            std::fprintf(stderr, "aos chat: %s\n", error.c_str());
            return 1;
        }
        const int after_turn = check_result(folder, name, baseline, status);
        if (after_turn >= 0) return after_turn;
        aos::loop::wait_for_delivery(layout, 100);
    }
}

}  // namespace

extern "C" int aos_chat_cli_main(int argc, char *argv[]) {
    const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
                              ? argv[0]
                              : "aos chat";
    if (argv == nullptr) return usage(program);
    try {
        return run_chat(argc, argv, program);
    } catch (const std::exception &error) {
        std::fprintf(stderr, "aos chat: %s\n", error.what());
        return 1;
    }
}
