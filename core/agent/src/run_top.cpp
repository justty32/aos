#include <aos/agent.hpp>

#include "run.hpp"

#include <cstdio>
#include <filesystem>
#include <stdexcept>
#include <string>

namespace {

using Dispatch = int (*)(int argc, char *argv[], const char *program);

int usage(const char *program, std::string_view arguments) {
    std::fprintf(stderr, "usage: %s %.*s\n", program,
                 static_cast<int>(arguments.size()), arguments.data());
    return 2;
}

std::string joined_text(int argc, char *argv[]) {
    std::string text;
    for (int index = 1; index < argc; ++index) {
        if (index != 1) text.push_back(' ');
        text += argv[index];
    }
    return text;
}

int say_dispatch(int argc, char *argv[], const char *program) {
    if (argc < 2) return usage(program, "<text...>");
    const std::filesystem::path folder = aos::agent::resolve_folder();
    aos::agent::say(folder, aos::agent::resolve_name(folder),
                    joined_text(argc, argv));
    return 0;
}

int listen_dispatch(int argc, char *argv[], const char *program) {
    if (argc > 2 || (argc == 2 && std::string_view(argv[1]) != "--once")) {
        return usage(program, "[--once]");
    }
    const std::filesystem::path folder = aos::agent::resolve_folder();
    return aos::agent::cli::run_listen(
        folder, aos::agent::resolve_name(folder), argc == 2);
}

int talk_dispatch(int argc, char *[], const char *program) {
    if (argc != 1) return usage(program, "");
    const std::filesystem::path folder = aos::agent::resolve_folder();
    return aos::agent::cli::run_talk(folder,
                                     aos::agent::resolve_name(folder));
}

int state_dispatch(int argc, char *[], const char *program) {
    if (argc != 1) return usage(program, "");
    const std::filesystem::path folder = aos::agent::resolve_folder();
    const std::string status = aos::agent::read_status_file(
        folder, aos::agent::resolve_name(folder));
    if (!status.empty()) std::fwrite(status.data(), 1, status.size(), stdout);
    std::fflush(stdout);
    return 0;
}

int run_entry(int argc, char *argv[], const char *fallback,
              Dispatch dispatch) {
    const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
                              ? argv[0]
                              : fallback;
    if (argc < 1 || argv == nullptr) return usage(program, "");
    try {
        return dispatch(argc, argv, program);
    } catch (const std::exception &error) {
        std::fprintf(stderr, "%s: %s\n", program, error.what());
        return 1;
    }
}

}  // namespace

extern "C" int aos_say_cli_main(int argc, char *argv[]) {
    return run_entry(argc, argv, "aos say", say_dispatch);
}

extern "C" int aos_listen_cli_main(int argc, char *argv[]) {
    return run_entry(argc, argv, "aos listen", listen_dispatch);
}

extern "C" int aos_talk_cli_main(int argc, char *argv[]) {
    return run_entry(argc, argv, "aos talk", talk_dispatch);
}

extern "C" int aos_state_cli_main(int argc, char *argv[]) {
    return run_entry(argc, argv, "aos state", state_dispatch);
}
