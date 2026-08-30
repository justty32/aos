#include <aos/loop.hpp>

#include <charconv>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <system_error>

#include <time.h>

namespace {

bool parse_number(const char *text, std::uint64_t &value) {
    if (text == nullptr || *text == '\0') return false;
    const char *end = text + std::strlen(text);
    const auto result = std::from_chars(text, end, value);
    return result.ec == std::errc{} && result.ptr == end;
}

void usage(const char *program) {
    std::fprintf(stderr,
                 "usage: %s [folder] [--step N] [--interval MS]\n",
                 program);
}

void wait_interval(std::uint64_t milliseconds) {
    timespec delay{};
    delay.tv_sec = static_cast<time_t>(milliseconds / 1000);
    delay.tv_nsec = static_cast<long>((milliseconds % 1000) * 1000000);
    ::nanosleep(&delay, nullptr);
}

}  // namespace

extern "C" int aos_run_cli_main(int argc, char *argv[]) {
    const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
                              ? argv[0]
                              : "aos run";
    if (argv == nullptr) {
        usage(program);
        return 2;
    }

    std::string folder = aos::loop::current_folder();
    int option_start = 1;
    if (argc > 1 && argv[1] != nullptr &&
        std::strncmp(argv[1], "--", 2) != 0) {
        folder = argv[1];
        option_start = 2;
    }

    std::uint64_t steps = 1;
    std::uint64_t interval = 100;
    for (int index = option_start; index < argc; index += 2) {
        if (index + 1 >= argc || argv[index] == nullptr ||
            argv[index + 1] == nullptr) {
            usage(program);
            return 2;
        }
        if (std::strcmp(argv[index], "--step") == 0) {
            if (!parse_number(argv[index + 1], steps)) {
                usage(program);
                return 2;
            }
        } else if (std::strcmp(argv[index], "--interval") == 0) {
            if (!parse_number(argv[index + 1], interval)) {
                usage(program);
                return 2;
            }
        } else {
            usage(program);
            return 2;
        }
    }

    const aos::loop::Layout layout = aos::loop::layout_of(folder);
    for (std::uint64_t completed = 0; steps == 0 || completed < steps;
         ++completed) {
        aos::loop::TurnSummary summary;
        std::string error;
        if (!aos::loop::run_turn(layout, summary, error)) {
            std::fprintf(stderr, "%s: %s\n", program, error.c_str());
            return 1;
        }
        if (summary.count == 0) {
            std::printf("turn %llu: idle\n",
                        static_cast<unsigned long long>(summary.turn));
        } else {
            std::printf("turn %llu: %zu insts, %llu ms\n",
                        static_cast<unsigned long long>(summary.turn),
                        summary.count,
                        static_cast<unsigned long long>(summary.elapsed_ms));
        }
        std::fflush(stdout);
        if (steps == 0 || completed + 1 < steps) wait_interval(interval);
    }
    return 0;
}
