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

int usage(const char *program, std::string_view arguments) {
    std::fprintf(stderr, "usage: %s %.*s\n", program,
                 static_cast<int>(arguments.size()), arguments.data());
    return 2;
}

std::string joined_text(int argc, char *argv[], int first) {
    std::string text;
    for (int index = first; index < argc; ++index) {
        if (index != first) text.push_back(' ');
        text += argv[index];
    }
    return text;
}

int say_dispatch(int argc, char *argv[], const char *program) {
    if (argc < 2) return usage(program, "[--to <名字>] <text...>");
    const std::filesystem::path folder = aos::agent::resolve_folder();
    const std::string from = aos::agent::say_from().string();
    if (std::string_view(argv[1]) != "--to") {
        if (aos::agent::is_user_folder(folder)) {
            aos::agent::say_to_user(joined_text(argc, argv, 1), from);
        } else {
            aos::agent::say(folder, aos::agent::resolve_name(folder),
                            joined_text(argc, argv, 1), from);
        }
        return 0;
    }
    if (argc < 4) return usage(program, "[--to <名字>] <text...>");

    const std::string contact_name = argv[2];
    const std::optional<aos::tool::Contact> contact =
        aos::tool::find_contact(folder, contact_name);
    if (!contact) {
        std::fprintf(stderr, "aos say: 通訊錄裡沒有 %s\n",
                     contact_name.c_str());
        return 1;
    }
    const std::filesystem::path target_folder =
        (folder / contact->folder).lexically_normal();
    if (aos::agent::is_user_folder(target_folder)) {
        aos::agent::say_to_user(joined_text(argc, argv, 3), from);
        const std::string destination =
            (aos::agent::user_folder() / ".aos").string();
        std::printf("已送給 %s（%s）\n", contact_name.c_str(),
                    destination.c_str());
        return 0;
    }
    const std::string target_agent =
        contact->agent.empty() ? aos::agent::resolve_name(target_folder)
                               : contact->agent;
    aos::agent::say(target_folder, target_agent, joined_text(argc, argv, 3),
                    from);
    const std::string destination =
        (target_folder / target_agent).lexically_normal().string();
    std::printf("已送給 %s（%s）\n", contact_name.c_str(), destination.c_str());
    return 0;
}

int listen_dispatch(int argc, char *argv[], const char *program) {
    if (argc > 2 || (argc == 2 && std::string_view(argv[1]) != "--once")) {
        return usage(program, "[--once]");
    }
    const std::filesystem::path folder = aos::agent::resolve_folder();
    if (aos::agent::is_user_folder(folder)) {
        aos::agent::drain_user_say();
        std::string log = aos::agent::read_user_log();
        if (!log.empty()) std::fwrite(log.data(), 1, log.size(), stdout);
        std::fflush(stdout);
        if (argc == 2) return 0;
        std::size_t offset = log.size();
        while (true) {
            std::this_thread::sleep_for(std::chrono::milliseconds(200));
            aos::agent::drain_user_say();
            log = aos::agent::read_user_log();
            if (log.size() < offset) offset = 0;
            if (log.size() > offset) {
                std::fwrite(log.data() + offset, 1, log.size() - offset,
                            stdout);
                std::fflush(stdout);
                offset = log.size();
            }
        }
    }
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
