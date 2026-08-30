#include "cli_common.hpp"

#include <algorithm>
#include <cstdio>
#include <exception>
#include <string>
#include <utility>
#include <vector>

namespace {

using aos::tick::Config;
using aos::tick::Paths;
using aos::tick::ScheduleItem;

int usage(const char *program) {
    std::fprintf(stderr,
                 "用法：%s add [folder] --at 時刻 [--id ID] [--note 文字] "
                 "(--ask 文字 | -- argv...)\n"
                 "      %s ls [folder]\n"
                 "      %s rm [folder] <id>\n",
                 program, program, program);
    return 2;
}

int fail(const char *program, const std::string &error) {
    std::fprintf(stderr, "%s: %s\n", program, error.c_str());
    return 1;
}

std::vector<std::string> ids_of(const std::vector<ScheduleItem> &rows) {
    std::vector<std::string> ids;
    ids.reserve(rows.size());
    for (const auto &row : rows) ids.push_back(row.id);
    return ids;
}

int add(const char *program, const std::vector<std::string> &words,
        std::size_t index, const aos::loop::Layout &layout, const Paths &paths,
        const Config &config) {
    std::string at_text;
    std::string id;
    std::string note;
    bool have_at = false;
    bool have_id = false;
    bool have_note = false;
    bool have_run = false;
    aos::tick::cli::RunSpec run;
    while (index < words.size()) {
        const std::string &option = words[index];
        if (option == "--ask" || option == "--") {
            have_run = aos::tick::cli::parse_run(words, index, run);
            break;
        }
        if (index + 1 >= words.size()) return usage(program);
        const std::string value = words[index + 1];
        if (option == "--at" && !have_at) {
            at_text = value;
            have_at = true;
        } else if (option == "--id" && !have_id) {
            id = value;
            have_id = true;
        } else if (option == "--note" && !have_note) {
            note = value;
            have_note = true;
        } else {
            return usage(program);
        }
        index += 2;
    }
    if (index != words.size() || !have_at || !have_run) return usage(program);
    aos::tick::Instant parsed_at = 0;
    if (!aos::tick::parse_at(at_text, config.tz, parsed_at)) {
        std::fprintf(stderr, "%s: 時刻不合法: %s\n", program, at_text.c_str());
        return usage(program);
    }

    const aos::tick::Instant now = aos::tick::cli::now_seconds();
    std::string error;
    if (!aos::loop::ensure_layout(layout, error)) return fail(program, error);
    if (!aos::tick::ensure_heartbeat(paths, now, config.tz, error)) {
        return fail(program, error);
    }
    std::vector<ScheduleItem> rows;
    if (!aos::tick::read_schedule(paths.schedule_file, rows, error)) {
        return fail(program, error);
    }
    const std::vector<std::string> ids = ids_of(rows);
    if (have_id && (!aos::tick::valid_id(id) ||
                    std::find(ids.begin(), ids.end(), id) != ids.end())) {
        std::fprintf(stderr, "%s: id 不合法或已存在: %s\n", program, id.c_str());
        return usage(program);
    }
    if (!have_id) id = aos::tick::make_id("s", now, ids);
    rows.push_back({id, at_text, {std::move(run.argv), std::move(run.ask)}, note});
    if (!aos::tick::write_schedule(paths.schedule_file, rows, now, config.tz,
                                   error)) {
        return fail(program, error);
    }
    std::printf("已登記一次性行程 %s（id: %s）\n", at_text.c_str(), id.c_str());
    return 0;
}

int list(const char *program, const Paths &paths, const Config &config) {
    std::vector<ScheduleItem> schedule;
    std::string error;
    if (!aos::tick::read_schedule(paths.schedule_file, schedule, error)) {
        return fail(program, error);
    }
    if (schedule.empty()) {
        std::puts("（沒有登記任何一次性行程）");
        return 0;
    }
    const aos::tick::Instant now = aos::tick::cli::now_seconds();
    std::vector<std::vector<std::string>> rows;
    for (const auto &item : schedule) {
        std::string state_error;
        const auto state = aos::tick::schedule_state(item, now, config, state_error);
        std::string state_text = "無效";
        if (state_error.empty()) {
            if (state == aos::tick::ScheduleState::pending) state_text = "pending";
            else if (state == aos::tick::ScheduleState::due) state_text = "due";
            else state_text = "missed";
        }
        rows.push_back({item.id, item.at, std::move(state_text),
                        aos::tick::cli::run_text(item.run), item.note});
    }
    aos::tick::cli::print_table({"ID", "AT", "STATE", "RUN", "NOTE"}, rows);
    return 0;
}

int remove(const char *program, const std::vector<std::string> &words,
           std::size_t index, const Paths &paths, const Config &config) {
    if (index + 1 != words.size() || !aos::tick::valid_id(words[index])) {
        return usage(program);
    }
    const std::string id = words[index];
    std::vector<ScheduleItem> rows;
    std::string error;
    if (!aos::tick::read_schedule(paths.schedule_file, rows, error)) {
        return fail(program, error);
    }
    const auto found = std::find_if(rows.begin(), rows.end(),
                                    [&](const ScheduleItem &row) { return row.id == id; });
    if (found == rows.end()) return fail(program, "找不到 id: " + id);
    rows.erase(found);
    if (!aos::tick::write_schedule(paths.schedule_file, rows,
                                   aos::tick::cli::now_seconds(), config.tz, error)) {
        return fail(program, error);
    }
    std::printf("已移除一次性行程 %s\n", id.c_str());
    return 0;
}

int dispatch(int argc, char *argv[]) {
    const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
                              ? argv[0]
                              : "aos schedule";
    aos::tick::cli::Args args(argc, argv);
    if (args.words.empty()) return usage(program);
    const std::string command = args.words[0];
    if (command != "add" && command != "ls" && command != "rm") return usage(program);
    std::size_t index = 1;
    std::string folder;
    aos::tick::cli::take_folder(args.words, index, folder);
    aos::loop::Layout layout;
    Paths paths;
    Config config;
    std::string error;
    if (!aos::tick::cli::load_context(folder, layout, paths, config, error)) {
        return fail(program, error);
    }
    if (command == "add") {
        return add(program, args.words, index, layout, paths, config);
    }
    if (command == "ls") return index == args.words.size() ? list(program, paths, config)
                                                            : usage(program);
    return remove(program, args.words, index, paths, config);
}

}  // namespace

extern "C" int aos_schedule_cli_main(int argc, char *argv[]) {
    try {
        return dispatch(argc, argv);
    } catch (const std::exception &error) {
        const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
                                  ? argv[0]
                                  : "aos schedule";
        std::fprintf(stderr, "%s: %s\n", program, error.what());
        return 1;
    } catch (...) {
        const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
                                  ? argv[0]
                                  : "aos schedule";
        std::fprintf(stderr, "%s: 發生未知錯誤\n", program);
        return 1;
    }
}
