#include <aos/agent.hpp>

#include "run.hpp"

#include <algorithm>
#include <cerrno>
#include <charconv>
#include <chrono>
#include <cstdio>
#include <fcntl.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <sys/file.h>
#include <thread>
#include <unistd.h>
#include <vector>

namespace {

int usage(const char *program, FILE *stream = stderr, int result = 2) {
    std::fprintf(
        stream,
        "usage: %s init [folder] [--name N] [--persona TEXT] "
        "[--engine lmstudio|pi] [--provider P] [--model M] "
        "[--priority N]\n"
        "       %s step [folder] [name]\n"
        "       %s say <folder> <name> <text...>\n"
        "       %s listen <folder> <name> [--once]\n"
        "       %s talk <folder> <name> [--interface pi]\n"
        "       %s state <folder> <name>\n"
        "  init    在指定資料夾建立世界與 agent；省略 folder 時使用目前資料夾\n"
        "  step    推進 agent 一回合\n"
        "  say     投遞一則訊息給 agent\n"
        "  listen  顯示對話記錄與尚未處理的訊息\n"
        "  talk    從標準輸入逐行對話\n"
        "  state   顯示狀態、未讀數、引擎與模型\n"
        "  -h, --help  顯示這份用法\n",
        program, program, program, program, program, program);
    return result;
}

/* `aos agent say <folder> <name> <text...>` 的第 4 個參數之後是使用者要說的話，
 * 掃到那裡會把「--help」這個字從訊息裡吃掉，所以 say 只掃到第 3 個參數為止。 */
bool has_help(int argc, char *argv[]) {
    int limit = argc;
    if (argc > 1 && argv[1] != nullptr &&
        std::string_view(argv[1]) == "say" && limit > 4) {
        limit = 4;
    }
    for (int index = 1; index < limit; ++index) {
        if (argv[index] == nullptr)
            continue;
        const std::string_view argument = argv[index];
        if (argument == "--help" || argument == "-h")
            return true;
    }
    return false;
}


bool validate_world(const std::filesystem::path &folder) {
    const std::filesystem::path absolute = aos::agent::absolute_folder(folder);
    if (!std::filesystem::is_directory(absolute)) {
        std::fprintf(stderr, "aos say: %s 那個資料夾不存在\n",
                     absolute.c_str());
        return false;
    }
    if (!std::filesystem::is_directory(absolute / ".aos")) {
        std::fprintf(stderr, "aos say: %s 不是一個 aos 世界（沒有 .aos/）\n",
                     absolute.c_str());
        return false;
    }
    const std::filesystem::path agents = absolute / ".aos" / "agents";
    bool found = false;
    if (std::filesystem::is_directory(agents)) {
        for (const auto &entry : std::filesystem::directory_iterator(agents)) {
            if (entry.is_directory()) {
                found = true;
                break;
            }
        }
    }
    if (!found) {
        std::fprintf(stderr,
                     "aos say: %s 還沒有 agent；請先在那裡跑 aos agent init\n",
                     absolute.c_str());
        return false;
    }
    return true;
}

/* 這個世界是不是有一條 aos run 正在推？拿得到獨佔鎖就代表沒有。 */
bool world_has_runner(const std::filesystem::path &folder) {
    const std::filesystem::path lock =
        aos::agent::absolute_folder(folder) / ".aos" / "run.lock";
    const int descriptor = open(lock.c_str(), O_CREAT | O_RDWR, 0644);
    if (descriptor < 0)
        return false;
    if (flock(descriptor, LOCK_EX | LOCK_NB) == 0) {
        flock(descriptor, LOCK_UN);
        close(descriptor);
        return false;
    }
    const int error = errno;
    close(descriptor);
    return error == EWOULDBLOCK || error == EAGAIN;
}

void print_text(const std::string &text) {
    if (!text.empty())
        std::fwrite(text.data(), 1, text.size(), stdout);
    std::fflush(stdout);
}

std::string joined_text(int argc, char *argv[], int first) {
    std::string text;
    for (int index = first; index < argc; ++index) {
        if (index != first)
            text.push_back(' ');
        text += argv[index];
    }
    return text;
}

int run_init(int argc, char *argv[], const char *program) {
    std::filesystem::path folder;
    std::string name;
    std::string persona = "你是一個可靠、好奇且言簡意賅的助手。";
    aos::agent::Engine engine;
    int option_start = 2;
    if (argc > 2 && argv[2] != nullptr &&
        !std::string_view(argv[2]).starts_with("--")) {
        folder = argv[2];
        option_start = 3;
    }
    for (int index = option_start; index < argc; ++index) {
        if (argv[index] == nullptr)
            return usage(program);
        const std::string option = argv[index];
        if ((option == "--name" || option == "--persona" ||
             option == "--engine" || option == "--provider" ||
             option == "--model" || option == "--priority") &&
            index + 1 < argc && argv[index + 1] != nullptr) {
            const std::string value = argv[++index];
            if (option == "--name")
                name = value;
            else if (option == "--persona")
                persona = value;
            else if (option == "--engine")
                engine.kind = value;
            else if (option == "--provider")
                engine.provider = value;
            else if (option == "--model")
                engine.model = value;
            else {
                const auto [end, error] = std::from_chars(
                    value.data(), value.data() + value.size(), engine.priority);
                if (error != std::errc{} ||
                    end != value.data() + value.size()) {
                    return usage(program);
                }
            }
        } else {
            return usage(program);
        }
    }
    if (engine.kind != "lmstudio" && engine.kind != "pi") {
        return usage(program);
    }
    folder = folder.empty() ? std::filesystem::current_path()
                            : aos::agent::absolute_folder(folder);
    if (name.empty())
        name = folder.filename().string();
    aos::agent::initialize(folder, name, persona, engine);
    return 0;
}

int run_agent_listen(int argc, char *argv[], const char *program) {
    if ((argc != 4 && argc != 5) ||
        (argc == 5 && std::string(argv[4]) != "--once")) {
        return usage(program);
    }
    return aos::agent::cli::run_listen(argv[2], argv[3], argc == 5);
}

bool has_assistant_record(std::string_view text) {
    std::size_t position = 0;
    while ((position = text.find("## turn ", position)) !=
           std::string_view::npos) {
        const std::size_t end = text.find('\n', position);
        if (end == std::string_view::npos)
            return false;
        if (text.substr(position, end - position).ends_with(" assistant")) {
            return true;
        }
        position = end + 1;
    }
    return false;
}

int run_agent_talk(int argc, char *argv[], const char *program) {
    if (argc == 6 && std::string(argv[4]) == "--interface" &&
        std::string(argv[5]) == "pi") {
        std::fprintf(stderr,
                     "%s: pi 介面需要 extension adapter，尚未內建；見 "
                     "core/agent/docs/pi-interface.md\n",
                     program);
        return 2;
    }
    if (argc != 4)
        return usage(program);
    return aos::agent::cli::run_talk(argv[2], argv[3]);
}

}  // namespace

namespace aos::agent::cli {

std::vector<std::filesystem::path>
unread_files(const std::filesystem::path &folder, std::string_view name) {
    const std::filesystem::path say = aos::agent::absolute_folder(folder) /
                                      ".aos" / "agents" / std::string(name) /
                                      "say";
    std::vector<std::filesystem::path> files;
    if (!std::filesystem::is_directory(say))
        return files;
    for (const auto &entry : std::filesystem::directory_iterator(say)) {
        if (entry.is_regular_file() && entry.path().extension() == ".md") {
            files.push_back(entry.path());
        }
    }
    std::sort(files.begin(), files.end());
    return files;
}

std::string unread_line(const std::filesystem::path &path) {
    std::ifstream input(path, std::ios::binary);
    std::string text{std::istreambuf_iterator<char>(input),
                     std::istreambuf_iterator<char>()};
    if (text.starts_with("from:")) {
        const std::size_t end = text.find('\n');
        text.erase(0, end == std::string::npos ? text.size() : end + 1);
        while (!text.empty() &&
               (text.front() == '\r' || text.front() == '\n')) {
            text.erase(text.begin());
        }
    }
    for (char &character : text) {
        if (character == '\r' || character == '\n')
            character = ' ';
    }
    if (text.size() > 200) {
        text.resize(200);
        text += "…";
    }
    return text;
}

void print_unread(const std::filesystem::path &folder, std::string_view name) {
    const std::vector<std::filesystem::path> files = unread_files(folder, name);
    if (files.empty())
        return;
    std::printf("## 未讀 (%zu)\n", files.size());
    for (const std::filesystem::path &path : files) {
        const std::string line = unread_line(path);
        std::printf("- %s\n", line.c_str());
    }
    std::fflush(stdout);
}

std::string json_string(std::string_view text) {
    std::string escaped = "\"";
    for (const unsigned char character : text) {
        switch (character) {
        case '\"':
            escaped += "\\\"";
            break;
        case '\\':
            escaped += "\\\\";
            break;
        case '\b':
            escaped += "\\b";
            break;
        case '\f':
            escaped += "\\f";
            break;
        case '\n':
            escaped += "\\n";
            break;
        case '\r':
            escaped += "\\r";
            break;
        case '\t':
            escaped += "\\t";
            break;
        default:
            if (character < 0x20) {
                char unicode[7];
                std::snprintf(unicode, sizeof(unicode), "\\u%04x",
                              static_cast<unsigned int>(character));
                escaped += unicode;
            } else {
                escaped.push_back(static_cast<char>(character));
            }
        }
    }
    escaped.push_back('\"');
    return escaped;
}

std::string state_text(const std::filesystem::path &folder,
                       std::string_view name) {
    const aos::agent::Status saved = aos::agent::read_status(folder, name);
    const std::size_t unread = unread_files(folder, name).size();
    std::string status = saved.status;
    std::string detail = saved.detail;
    /* 停在 error 的 agent 比未讀更急：不要被 pending 蓋掉。 */
    if (unread > 0 && status != "error") {
        status = "pending";
        detail = std::to_string(unread) + " 封未讀，等下一回合處理";
    }

    std::string engine;
    std::string model;
    try {
        const std::filesystem::path path = aos::agent::absolute_folder(folder) /
                                           ".aos" / "agents" /
                                           std::string(name) / "engine.json";
        if (std::filesystem::is_regular_file(path)) {
            const aos::agent::Engine configured =
                aos::agent::read_engine(folder, name);
            engine = configured.kind;
            model = configured.model;
        }
    } catch (const std::exception &) {
        // engine.json 不該妨礙使用者查看 agent 的執行狀態。
    }
    return "{\n"
           "  \"detail\": " +
           json_string(detail) +
           ",\n"
           "  \"engine\": " +
           json_string(engine) +
           ",\n"
           "  \"last_error\": " +
           json_string(saved.last_error) +
           ",\n"
           "  \"model\": " +
           json_string(model) +
           ",\n"
           "  \"status\": " +
           json_string(status) +
           ",\n"
           "  \"turn\": " +
           std::to_string(saved.turn) +
           ",\n"
           "  \"unread\": " +
           std::to_string(unread) +
           ",\n"
           "  \"updated_at\": " +
           json_string(saved.updated_at) +
           "\n"
           "}\n";
}

int run_listen(const std::filesystem::path &folder, std::string_view name,
               bool once) {
    std::string log = aos::agent::read_log(folder, name);
    print_text(log);
    print_unread(folder, name);
    if (once)
        return 0;
    std::size_t offset = log.size();
    while (true) {
        std::this_thread::sleep_for(std::chrono::milliseconds(200));
        log = aos::agent::read_log(folder, name);
        if (log.size() < offset)
            offset = 0;
        if (log.size() > offset) {
            print_text(log.substr(offset));
            offset = log.size();
        }
    }
}

int run_talk(const std::filesystem::path &folder, std::string_view name) {
    const std::filesystem::path absolute = aos::agent::absolute_folder(folder);
    if (!world_has_runner(absolute)) {
        std::fprintf(
            stderr,
            "aos talk: 這個世界沒有 aos run 在推進，說出去的話不會有人處理。\n"
            "請另開一個終端機跑：aos run %s --step 0\n",
            absolute.c_str());
        return 1;
    }
    std::string line;
    while (std::getline(std::cin, line)) {
        const std::size_t offset = aos::agent::read_log(folder, name).size();
        aos::agent::say(folder, name, line, aos::agent::say_from().string());
        while (true) {
            std::this_thread::sleep_for(std::chrono::milliseconds(200));
            const std::string log = aos::agent::read_log(folder, name);
            const std::string_view added =
                offset <= log.size() ? std::string_view(log).substr(offset)
                                     : std::string_view(log);
            if (has_assistant_record(added)) {
                print_text(std::string(added));
                break;
            }
        }
    }
    return 0;
}

}  // namespace aos::agent::cli

namespace {

int dispatch(int argc, char *argv[]) {
    const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
                              ? argv[0]
                              : "aos agent";
    if (argc >= 1 && argv != nullptr && has_help(argc, argv)) {
        return usage(program, stdout, 0);
    }
    if (argc < 2 || argv == nullptr || argv[1] == nullptr)
        return usage(program);
    const std::string command = argv[1];
    if (command == "init")
        return run_init(argc, argv, program);
    if (command == "step") {
        if (argc < 2 || argc > 4)
            return usage(program);
        const std::filesystem::path folder = aos::agent::resolve_folder(
            argc >= 3 ? std::filesystem::path(argv[2])
                      : std::filesystem::path{});
        const std::string name = aos::agent::resolve_name(
            folder, argc == 4 ? std::string_view(argv[3]) : std::string_view{});
        std::string error;
        const int result = aos::agent::step(folder, name, {}, &error);
        if (result == 75)
            std::fputs("waiting-llm\n", stderr);
        else if (result != 0)
            std::fprintf(stderr, "%s: %s\n", program, error.c_str());
        return result;
    }
    if (command == "say") {
        if (argc < 5)
            return usage(program);
        if (!validate_world(argv[2]))
            return 1;
        aos::agent::say(argv[2], argv[3], joined_text(argc, argv, 4),
                        aos::agent::say_from().string());
        return 0;
    }
    if (command == "listen")
        return run_agent_listen(argc, argv, program);
    if (command == "talk")
        return run_agent_talk(argc, argv, program);
    if (command == "state") {
        if (argc != 4)
            return usage(program);
        print_text(aos::agent::cli::state_text(argv[2], argv[3]));
        return 0;
    }
    return usage(program);
}

}  // namespace

extern "C" int aos_agent_cli_main(int argc, char *argv[]) {
    try {
        return dispatch(argc, argv);
    } catch (const std::exception &error) {
        const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
                                  ? argv[0]
                                  : "aos agent";
        std::fprintf(stderr, "%s: %s\n", program, error.what());
        return 1;
    }
}
