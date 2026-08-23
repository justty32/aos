#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

/* 子命令表由 CMake 產生（見 app/CMakeLists.txt）。每個小專案在自己的
 * CMakeLists 裡呼叫 aos_add_subcommand()，這個檔案不需要跟著改。 */

extern "C" {
#define AOS_SUBCOMMAND(name, entry, summary) int entry(int, char **);
#include <aos_subcommands.inc>
#undef AOS_SUBCOMMAND
}

namespace {

struct Subcommand {
    const char *name;
    int (*entry)(int, char **);
    const char *summary;
};

constexpr Subcommand kSubcommands[] = {
#define AOS_SUBCOMMAND(name, entry, summary) {#name, entry, summary},
#include <aos_subcommands.inc>
#undef AOS_SUBCOMMAND
};

void print_usage(std::FILE *stream, const char *program) {
    std::fprintf(stream, "usage: %s <command> [args...]\n\ncommands:\n", program);
    for (const Subcommand &subcommand : kSubcommands) {
        std::fprintf(stream, "  %-12s %s\n", subcommand.name, subcommand.summary);
    }
}

}  // namespace

int main(int argc, char *argv[]) {
    const char *program =
        argc > 0 && argv != nullptr && argv[0] != nullptr ? argv[0] : "aos";
    if (argc < 2) {
        print_usage(stderr, program);
        return 2;
    }

    const char *command = argv[1];
    if (std::strcmp(command, "-h") == 0 || std::strcmp(command, "--help") == 0) {
        print_usage(stdout, program);
        return 0;
    }

    for (const Subcommand &subcommand : kSubcommands) {
        if (std::strcmp(command, subcommand.name) != 0) {
            continue;
        }
        /* 子命令自己印用法訊息時會用 argv[0]，所以把「aos inst」整串傳下去，
         * 而不是只傳 "inst" 或原本的 "aos"。 */
        std::string invocation = std::string(program) + " " + command;
        std::vector<char *> forwarded;
        forwarded.reserve(static_cast<std::size_t>(argc));
        forwarded.push_back(invocation.data());
        for (int index = 2; index < argc; ++index) {
            forwarded.push_back(argv[index]);
        }
        forwarded.push_back(nullptr);
        return subcommand.entry(static_cast<int>(forwarded.size()) - 1,
                                forwarded.data());
    }

    std::fprintf(stderr, "%s: unknown command '%s'\n", program, command);
    print_usage(stderr, program);
    return 2;
}
