#include <aos/agent.hpp>
#include <aos/tool.hpp>

#include "run.hpp"

#include <chrono>
#include <cstdio>
#include <filesystem>
#include <stdexcept>
#include <string>
#include <thread>

namespace {

using Dispatch = int (*)(int argc, char *argv[], const char *program);

bool has_help(int argc, char *argv[]) {
    for (int index = 1; index < argc; ++index) {
        if (argv[index] == nullptr)
            continue;
        const std::string_view argument = argv[index];
        if (argument == "--help" || argument == "-h")
            return true;
    }
    return false;
}

/* say 的其餘參數是使用者要說的話，掃全部會把「--help」這個字從訊息裡吃掉，
 * 所以只認第一個位置。 */
bool leading_help(int argc, char *argv[]) {
    return argc > 1 && argv[1] != nullptr &&
           (std::string_view(argv[1]) == "--help" ||
            std::string_view(argv[1]) == "-h");
}

int say_usage(const char *program, FILE *stream, int result) {
    std::fprintf(stream,
                 "usage: %s [--to <name>] <text...>\n"
                 "  --to <name>  look up the name in this world's contacts and deliver across worlds\n"
                 "  -h, --help   show this usage (only as the first argument; --help\n"
                 "               anywhere else is part of the message)\n",
                 program);
    return result;
}

int listen_usage(const char *program, FILE *stream, int result) {
    std::fprintf(stream,
                 "usage: %s [--once]\n"
                 "  --once       print the current log and unread messages, then exit\n"
                 "  -h, --help   show this usage\n",
                 program);
    return result;
}

int talk_usage(const char *program, FILE *stream, int result) {
    std::fprintf(stream,
                 "usage: %s [--interface <name>]\n"
                 "  --interface pi  use the pi interface (not built in yet)\n"
                 "  -h, --help      show this usage\n",
                 program);
    return result;
}

int state_usage(const char *program, FILE *stream, int result) {
    std::fprintf(stream,
                 "usage: %s\n"
                 "  -h, --help  show this usage\n",
                 program);
    return result;
}


bool validate_world(const std::filesystem::path &folder,
                    std::string_view contact_name = {}) {
    const std::filesystem::path absolute = aos::agent::absolute_folder(folder);
    if (!std::filesystem::is_directory(absolute)) {
        if (contact_name.empty()) {
            std::fprintf(stderr, "aos say: folder %s does not exist\n",
                         absolute.c_str());
        } else {
            std::fprintf(stderr,
                         "aos say: contact %.*s points to %s, which does not exist\n",
                         static_cast<int>(contact_name.size()),
                         contact_name.data(), absolute.c_str());
        }
        return false;
    }
    if (!std::filesystem::is_directory(absolute / ".aos")) {
        std::fprintf(stderr, "aos say: %s is not an aos world (no .aos/)\n",
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
                     "aos say: %s has no agent yet; run aos agent init there first\n",
                     absolute.c_str());
        return false;
    }
    return true;
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

int say_dispatch(int argc, char *argv[], const char *program) {
    if (leading_help(argc, argv))
        return say_usage(program, stdout, 0);
    if (argc < 2)
        return say_usage(program, stderr, 2);
    const std::filesystem::path folder = aos::agent::resolve_folder();
    const std::string from = aos::agent::say_from().string();
    if (std::string_view(argv[1]) != "--to") {
        if (aos::agent::is_user_folder(folder)) {
            aos::agent::say_to_user(joined_text(argc, argv, 1), from);
        } else {
            if (!validate_world(folder))
                return 1;
            aos::agent::say(folder, aos::agent::resolve_name(folder),
                            joined_text(argc, argv, 1), from);
        }
        return 0;
    }
    if (argc < 4)
        return say_usage(program, stderr, 2);

    const std::string contact_name = argv[2];
    const std::optional<aos::tool::Contact> contact =
        aos::tool::find_contact(folder, contact_name);
    if (!contact) {
        std::fprintf(stderr, "aos say: no contact named %s\n",
                     contact_name.c_str());
        return 1;
    }
    const std::filesystem::path target_folder = aos::agent::absolute_folder(
        (folder / contact->folder).lexically_normal());
    if (aos::agent::is_user_folder(target_folder)) {
        aos::agent::say_to_user(joined_text(argc, argv, 3), from);
        const std::string destination =
            (aos::agent::user_folder() / ".aos" / "say").string();
        std::printf("sent to %s (%s)\n", contact_name.c_str(),
                    destination.c_str());
        return 0;
    }
    if (!validate_world(target_folder, contact_name))
        return 1;
    const std::string target_agent =
        contact->agent.empty() ? aos::agent::resolve_name(target_folder)
                               : contact->agent;
    aos::agent::say(target_folder, target_agent, joined_text(argc, argv, 3),
                    from);
    const std::string destination =
        (target_folder / ".aos" / "agents" / target_agent / "say").string();
    std::printf("sent to %s (%s)\n", contact_name.c_str(), destination.c_str());
    return 0;
}

int listen_dispatch(int argc, char *argv[], const char *program) {
    if (has_help(argc, argv))
        return listen_usage(program, stdout, 0);
    if (argc > 2 || (argc == 2 && std::string_view(argv[1]) != "--once")) {
        return listen_usage(program, stderr, 2);
    }
    const std::filesystem::path folder = aos::agent::resolve_folder();
    if (aos::agent::is_user_folder(folder)) {
        aos::agent::drain_user_say();
        std::string log = aos::agent::read_user_log();
        if (!log.empty())
            std::fwrite(log.data(), 1, log.size(), stdout);
        std::fflush(stdout);
        if (argc == 2)
            return 0;
        std::size_t offset = log.size();
        while (true) {
            std::this_thread::sleep_for(std::chrono::milliseconds(200));
            aos::agent::drain_user_say();
            log = aos::agent::read_user_log();
            if (log.size() < offset)
                offset = 0;
            if (log.size() > offset) {
                std::fwrite(log.data() + offset, 1, log.size() - offset,
                            stdout);
                std::fflush(stdout);
                offset = log.size();
            }
        }
    }
    return aos::agent::cli::run_listen(folder, aos::agent::resolve_name(folder),
                                       argc == 2);
}

int talk_dispatch(int argc, char *argv[], const char *program) {
    if (has_help(argc, argv))
        return talk_usage(program, stdout, 0);
    if (argc == 3 && std::string_view(argv[1]) == "--interface") {
        const std::string_view interface = argv[2];
        if (interface == "pi") {
            std::fprintf(stderr,
                         "%s: the pi interface needs an extension adapter, which is not built in yet; see "
                         "core/agent/docs/pi-interface.md\n",
                         program);
        } else {
            std::fprintf(stderr,
                         "aos talk: unknown --interface %.*s (the only one is "
                         "pi, and it is not built in yet)\n",
                         static_cast<int>(interface.size()), interface.data());
        }
        return 2;
    }
    if (argc != 1)
        return talk_usage(program, stderr, 2);
    const std::filesystem::path folder = aos::agent::resolve_folder();
    return aos::agent::cli::run_talk(folder, aos::agent::resolve_name(folder));
}

int state_dispatch(int argc, char *argv[], const char *program) {
    if (has_help(argc, argv))
        return state_usage(program, stdout, 0);
    if (argc != 1)
        return state_usage(program, stderr, 2);
    const std::filesystem::path folder = aos::agent::resolve_folder();
    const std::string name = aos::agent::resolve_name(folder);
    const std::string status = aos::agent::cli::state_text(folder, name);
    if (!status.empty())
        std::fwrite(status.data(), 1, status.size(), stdout);
    std::fflush(stdout);
    return 0;
}

int run_entry(int argc, char *argv[], const char *fallback, Dispatch dispatch) {
    const char *program =
        argc > 0 && argv != nullptr && argv[0] != nullptr ? argv[0] : fallback;
    if (argc < 1 || argv == nullptr) {
        std::fprintf(stderr, "usage: %s\n", program);
        return 2;
    }
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
