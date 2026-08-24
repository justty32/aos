#include "run.hpp"
#include "run_internal.hpp"

#include <charconv>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <new>
#include <stdexcept>

namespace aos {
namespace {

bool parse_interval(const char *text, std::uint64_t &interval) {
    if (text == nullptr || *text == '\0') return false;
    const char *end = text + std::strlen(text);
    const auto parsed = std::from_chars(text, end, interval);
    return parsed.ec == std::errc{} && parsed.ptr == end;
}

}  // namespace

int run_exec(int argc, char *argv[]) {
    const bool current = argc == 1 && argv != nullptr;
    const bool one_shot = argc == 2 && argv != nullptr && argv[1] != nullptr &&
                          std::strcmp(argv[1], "--loop") != 0;
    const bool loop = (argc == 3 || argc == 4) && argv != nullptr &&
                      argv[1] != nullptr &&
                      std::strcmp(argv[1], "--loop") == 0 &&
                      argv[2] != nullptr &&
                      (argc == 3 || argv[3] != nullptr);
    std::uint64_t interval = 0;
    if ((!current && !one_shot && !loop) ||
        (loop && !parse_interval(argv[2], interval))) {
        const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
                                  ? argv[0]
                                  : "aos exec";
        std::fprintf(stderr,
                     "usage: %s [--loop <milliseconds>] [folder]\n", program);
        return 2;
    }
    try {
        if (loop) {
            if (interval == 0) {
                std::fprintf(stderr,
                             "aos exec: warning: --loop 0 would busy-poll and "
                             "consume one CPU core; using 1 ms instead\n");
                interval = 1;
            }
            return detail::run_exec_loop(argc == 4 ? argv[3] : ".", interval);
        }
        bool did_work = false;
        return detail::run_exec_once(one_shot ? argv[1] : ".", did_work);
    } catch (const std::bad_alloc &) {
        std::fprintf(stderr, "aos exec: out of memory\n");
        return 1;
    } catch (const std::length_error &) {
        std::fprintf(stderr, "aos exec: out of memory\n");
        return 1;
    }
}

int run_init(int argc, char *argv[]) {
    const bool current = argc == 1 && argv != nullptr;
    const bool explicit_folder = argc == 2 && argv != nullptr && argv[1] != nullptr;
    if (!current && !explicit_folder) {
        const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
                                  ? argv[0]
                                  : "aos init";
        std::fprintf(stderr, "usage: %s [folder]\n", program);
        return 2;
    }
    return detail::run_init_world(explicit_folder ? argv[1] : ".");
}

}  // namespace aos

extern "C" int aos_exec_cli_main(int argc, char *argv[]) {
    return aos::run_exec(argc, argv);
}

extern "C" int aos_init_cli_main(int argc, char *argv[]) {
    return aos::run_init(argc, argv);
}
