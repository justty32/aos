#include <aos/agent.hpp>

#include <chrono>
#include <cstdio>
#include <iostream>
#include <stdexcept>
#include <string>
#include <thread>

namespace {

int usage(const char *program) {
    std::fprintf(stderr,
                 "usage: %s init <folder> --name N [--persona TEXT]\n"
                 "       %s step <folder> <name>\n"
                 "       %s say <folder> <name> <text...>\n"
                 "       %s listen <folder> <name> [--once]\n"
                 "       %s talk <folder> <name> [--interface pi]\n"
                 "       %s state <folder> <name>\n",
                 program, program, program, program, program, program);
    return 2;
}

void print_text(const std::string &text) {
    if (!text.empty()) std::fwrite(text.data(), 1, text.size(), stdout);
    std::fflush(stdout);
}

std::string joined_text(int argc, char *argv[], int first) {
    std::string text;
    for (int index = first; index < argc; ++index) {
        if (index != first) text.push_back(' ');
        text += argv[index];
    }
    return text;
}

int run_init(int argc, char *argv[], const char *program) {
    if (argc < 5 || argv[2] == nullptr) return usage(program);
    std::string name;
    std::string persona = "你是一個可靠、好奇且言簡意賅的助手。";
    for (int index = 3; index < argc; ++index) {
        const std::string option = argv[index];
        if ((option == "--name" || option == "--persona") &&
            index + 1 < argc) {
            const std::string value = argv[++index];
            if (option == "--name") name = value;
            else persona = value;
        } else {
            return usage(program);
        }
    }
    if (name.empty()) return usage(program);
    aos::agent::initialize(argv[2], name, persona);
    return 0;
}

int run_listen(int argc, char *argv[], const char *program) {
    if ((argc != 4 && argc != 5) ||
        (argc == 5 && std::string(argv[4]) != "--once")) {
        return usage(program);
    }
    std::string log = aos::agent::read_log(argv[2], argv[3]);
    print_text(log);
    if (argc == 5) return 0;
    std::size_t offset = log.size();
    while (true) {
        std::this_thread::sleep_for(std::chrono::milliseconds(200));
        log = aos::agent::read_log(argv[2], argv[3]);
        if (log.size() < offset) offset = 0;
        if (log.size() > offset) {
            print_text(log.substr(offset));
            offset = log.size();
        }
    }
}

bool has_assistant_record(std::string_view text) {
    std::size_t position = 0;
    while ((position = text.find("## turn ", position)) !=
           std::string_view::npos) {
        const std::size_t end = text.find('\n', position);
        if (end == std::string_view::npos) return false;
        if (text.substr(position, end - position).ends_with(" assistant")) {
            return true;
        }
        position = end + 1;
    }
    return false;
}

int run_talk(int argc, char *argv[], const char *program) {
    if (argc == 6 && std::string(argv[4]) == "--interface" &&
        std::string(argv[5]) == "pi") {
        std::fprintf(stderr,
                     "%s: pi 介面需要 extension adapter，尚未內建；見 "
                     "core/agent/docs/pi-interface.md\n",
                     program);
        return 2;
    }
    if (argc != 4) return usage(program);
    std::string line;
    while (std::getline(std::cin, line)) {
        const std::size_t offset = aos::agent::read_log(argv[2], argv[3]).size();
        aos::agent::say(argv[2], argv[3], line);
        while (true) {
            std::this_thread::sleep_for(std::chrono::milliseconds(200));
            const std::string log = aos::agent::read_log(argv[2], argv[3]);
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

int dispatch(int argc, char *argv[]) {
    const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
                              ? argv[0]
                              : "aos agent";
    if (argc < 2 || argv == nullptr || argv[1] == nullptr) return usage(program);
    const std::string command = argv[1];
    if (command == "init") return run_init(argc, argv, program);
    if (command == "step") {
        if (argc != 4) return usage(program);
        std::string error;
        const int result = aos::agent::step(argv[2], argv[3], {}, &error);
        if (result != 0) std::fprintf(stderr, "%s: %s\n", program, error.c_str());
        return result;
    }
    if (command == "say") {
        if (argc < 5) return usage(program);
        aos::agent::say(argv[2], argv[3], joined_text(argc, argv, 4));
        return 0;
    }
    if (command == "listen") return run_listen(argc, argv, program);
    if (command == "talk") return run_talk(argc, argv, program);
    if (command == "state") {
        if (argc != 4) return usage(program);
        print_text(aos::agent::read_status_file(argv[2], argv[3]));
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
