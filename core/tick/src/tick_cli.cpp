#include "cli_common.hpp"

#include <charconv>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <exception>
#include <string>

namespace {

int usage(const char *program) {
    std::fprintf(stderr, "用法：%s [folder] [--dry-run]\n", program);
    return 2;
}

bool parse_turn(const char *text, std::uint64_t &turn) {
    if (text == nullptr || *text == '\0') return false;
    const char *end = text + std::strlen(text);
    const auto parsed = std::from_chars(text, end, turn);
    return parsed.ec == std::errc{} && parsed.ptr == end;
}

int dispatch(int argc, char *argv[]) {
    const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
                              ? argv[0]
                              : "aos tick";
    aos::tick::cli::Args args(argc, argv);
    std::size_t index = 0;
    std::string folder;
    aos::tick::cli::take_folder(args.words, index, folder);

    bool dry_run = false;
    if (index < args.words.size() && args.words[index] == "--dry-run") {
        dry_run = true;
        ++index;
    }
    if (index != args.words.size()) return usage(program);

    aos::loop::Layout layout;
    aos::tick::Paths paths;
    aos::tick::Config config;
    std::string error;
    if (!aos::tick::cli::load_context(folder, layout, paths, config, error)) {
        std::fprintf(stderr, "%s: %s\n", program, error.c_str());
        return 1;
    }

    aos::tick::TickOptions options;
    options.dry_run = dry_run;
    if (!parse_turn(std::getenv("AOS_TURN"), options.turn)) {
        options.turn = aos::loop::read_turn(layout);
    }
    aos::tick::TickReport report;
    if (!aos::tick::run_tick(layout, aos::tick::cli::now_seconds(), options,
                             report, error)) {
        std::fprintf(stderr, "%s: %s\n", program, error.c_str());
        return 1;
    }

    if (report.line.empty()) {
        // 空報告仍印「無事」，讓手動執行者知道命令確實已完成。
        std::printf("%s無事\n", dry_run ? "[dry-run] " : "");
    } else {
        if (dry_run) std::fputs("[dry-run] ", stdout);
        std::fwrite(report.line.data(), 1, report.line.size(), stdout);
    }
    for (const auto &event : report.events) {
        if (event.kind == "error") return 1;
    }
    return 0;
}

}  // namespace

extern "C" int aos_tick_cli_main(int argc, char *argv[]) {
    try {
        return dispatch(argc, argv);
    } catch (const std::exception &error) {
        const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
                                  ? argv[0]
                                  : "aos tick";
        std::fprintf(stderr, "%s: %s\n", program, error.what());
        return 1;
    } catch (...) {
        const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
                                  ? argv[0]
                                  : "aos tick";
        std::fprintf(stderr, "%s: 發生未知錯誤\n", program);
        return 1;
    }
}
