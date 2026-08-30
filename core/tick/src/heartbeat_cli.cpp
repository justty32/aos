#include "cli_common.hpp"

#include <cstdio>
#include <exception>
#include <limits>
#include <string>

namespace {

int usage(const char *program) {
    std::fprintf(stderr,
                 "用法：%s init [folder] [--interval 30m]\n", program);
    return 2;
}

int dispatch(int argc, char *argv[]) {
    const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
                              ? argv[0]
                              : "aos heartbeat";
    aos::tick::cli::Args args(argc, argv);
    if (args.words.empty() || args.words[0] != "init") return usage(program);

    std::size_t index = 1;
    std::string folder;
    aos::tick::cli::take_folder(args.words, index, folder);
    std::string interval = "30m";
    if (index < args.words.size()) {
        if (args.words[index] != "--interval" ||
            index + 2 != args.words.size()) {
            return usage(program);
        }
        interval = args.words[index + 1];
    }

    aos::loop::Layout layout;
    aos::tick::Paths paths;
    aos::tick::Config config;
    std::string error;
    if (!aos::tick::cli::load_context(folder, layout, paths, config, error)) {
        std::fprintf(stderr, "%s: %s\n", program, error.c_str());
        return 1;
    }

    std::int64_t seconds = 0;
    if (!aos::tick::parse_duration(interval, seconds) ||
        seconds > static_cast<std::int64_t>(
                      std::numeric_limits<std::uint64_t>::max() / 1000)) {
        std::fprintf(stderr, "%s: 期間不合法: %s\n", program,
                     interval.c_str());
        return usage(program);
    }
    const auto every_ms = static_cast<std::uint64_t>(seconds) * 1000;
    if (!aos::tick::heartbeat_init(layout, aos::tick::cli::now_seconds(),
                                   every_ms, error)) {
        std::fprintf(stderr, "%s: %s\n", program, error.c_str());
        return 1;
    }
    std::printf("已建立心跳設定 %s/every/tick.json，週期 %s\n",
                layout.aos.c_str(), interval.c_str());
    return 0;
}

}  // namespace

extern "C" int aos_heartbeat_cli_main(int argc, char *argv[]) {
    try {
        return dispatch(argc, argv);
    } catch (const std::exception &error) {
        const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
                                  ? argv[0]
                                  : "aos heartbeat";
        std::fprintf(stderr, "%s: %s\n", program, error.what());
        return 1;
    } catch (...) {
        const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
                                  ? argv[0]
                                  : "aos heartbeat";
        std::fprintf(stderr, "%s: 發生未知錯誤\n", program);
        return 1;
    }
}
