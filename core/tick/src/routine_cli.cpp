#include "cli_common.hpp"

#include <algorithm>
#include <cstdio>
#include <exception>
#include <string>
#include <utility>
#include <vector>

namespace {

using aos::tick::Config;
using aos::tick::Instant;
using aos::tick::Paths;
using aos::tick::Routine;

int usage(const char *program) {
    std::fprintf(
        stderr,
        "用法：%s add [folder] (--every D | --slot S) [--id ID] "
        "[--note 文字] (--ask 文字 | -- argv...)\n"
        "      %s ls [folder]\n"
        "      %s rm [folder] <id>\n",
        program, program, program);
    return 2;
}

int fail(const char *program, const std::string &error) {
    std::fprintf(stderr, "%s: %s\n", program, error.c_str());
    return 1;
}

std::vector<std::string> ids_of(const std::vector<Routine> &rows) {
    std::vector<std::string> ids;
    ids.reserve(rows.size());
    for (const auto &row : rows) ids.push_back(row.id);
    return ids;
}

int add(const char *program, const std::vector<std::string> &words,
        std::size_t index, const aos::loop::Layout &layout, const Paths &paths,
        const Config &config) {
    std::string every;
    std::string slot;
    std::string id;
    std::string note;
    bool have_every = false;
    bool have_slot = false;
    bool have_id = false;
    bool have_note = false;
    aos::tick::cli::RunSpec run;
    bool have_run = false;
    while (index < words.size()) {
        const std::string &option = words[index];
        if (option == "--ask" || option == "--") {
            have_run = aos::tick::cli::parse_run(words, index, run);
            break;
        }
        if (index + 1 >= words.size()) return usage(program);
        const std::string value = words[index + 1];
        if (option == "--every" && !have_every) {
            every = value;
            have_every = true;
        } else if (option == "--slot" && !have_slot) {
            slot = value;
            have_slot = true;
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
    if (index != words.size() || !have_run || have_every == have_slot) {
        return usage(program);
    }
    std::int64_t ignored_seconds = 0;
    aos::tick::SlotSpec ignored_slot;
    if ((have_every && !aos::tick::parse_duration(every, ignored_seconds)) ||
        (have_slot && !aos::tick::parse_slot(slot, ignored_slot))) {
        std::fprintf(stderr, "%s: %s不合法: %s\n", program,
                     have_every ? "期間" : "時段",
                     (have_every ? every : slot).c_str());
        return usage(program);
    }

    const Instant now = aos::tick::cli::now_seconds();
    std::string error;
    if (!aos::loop::ensure_layout(layout, error)) return fail(program, error);
    if (!aos::tick::ensure_heartbeat(paths, now, config.tz, error)) {
        return fail(program, error);
    }
    std::vector<Routine> rows;
    if (!aos::tick::read_routines(paths.routines_file, rows, error)) {
        return fail(program, error);
    }
    const std::vector<std::string> ids = ids_of(rows);
    if (have_id && (!aos::tick::valid_id(id) ||
                    std::find(ids.begin(), ids.end(), id) != ids.end())) {
        std::fprintf(stderr, "%s: id 不合法或已存在: %s\n", program, id.c_str());
        return usage(program);
    }
    if (!have_id) id = aos::tick::make_id("r", now, ids);

    Routine row;
    row.id = id;
    row.kind = have_every ? "interval" : "slot";
    row.every = every;
    row.slot = slot;
    row.run = {std::move(run.argv), std::move(run.ask)};
    row.note = note;
    rows.push_back(std::move(row));
    if (!aos::tick::write_routines(paths.routines_file, rows, now, config.tz,
                                   error)) {
        return fail(program, error);
    }
    std::printf("已登記常規事務 %s（id: %s）\n",
                have_every ? every.c_str() : slot.c_str(), id.c_str());
    return 0;
}

int list(const char *program, const Paths &paths, const Config &config) {
    std::vector<Routine> routines;
    std::string error;
    if (!aos::tick::read_routines(paths.routines_file, routines, error)) {
        return fail(program, error);
    }
    if (routines.empty()) {
        std::puts("（沒有登記任何常規事務）");
        return 0;
    }
    const Instant now = aos::tick::cli::now_seconds();
    std::vector<std::vector<std::string>> rows;
    for (const auto &routine : routines) {
        std::string due_error;
        const bool due = aos::tick::routine_due(routine, now, config.tz, due_error);
        const auto next = aos::tick::routine_next(routine, now, config.tz);
        std::string next_text = due ? "到期" : due_error.empty() && next
                                               ? aos::tick::format_at(*next, config.tz)
                                               : "無效";
        rows.push_back({routine.id, routine.kind,
                        routine.kind == "interval" ? routine.every : routine.slot,
                        routine.last_run.empty() ? "—" : routine.last_run,
                        std::move(next_text), aos::tick::cli::run_text(routine.run),
                        routine.note});
    }
    aos::tick::cli::print_table(
        {"ID", "KIND", "EVERY/SLOT", "LAST_RUN", "NEXT", "RUN", "NOTE"}, rows);
    return 0;
}

int remove(const char *program, const std::vector<std::string> &words,
           std::size_t index, const Paths &paths, const Config &config) {
    if (index + 1 != words.size() || !aos::tick::valid_id(words[index])) {
        return usage(program);
    }
    const std::string id = words[index];
    std::vector<Routine> rows;
    std::string error;
    if (!aos::tick::read_routines(paths.routines_file, rows, error)) {
        return fail(program, error);
    }
    const auto found = std::find_if(rows.begin(), rows.end(),
                                    [&](const Routine &row) { return row.id == id; });
    if (found == rows.end()) return fail(program, "找不到 id: " + id);
    rows.erase(found);
    if (!aos::tick::write_routines(paths.routines_file, rows,
                                   aos::tick::cli::now_seconds(), config.tz, error)) {
        return fail(program, error);
    }
    std::printf("已移除常規事務 %s\n", id.c_str());
    return 0;
}

int dispatch(int argc, char *argv[]) {
    const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
                              ? argv[0]
                              : "aos routine";
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
    if (command == "add") return add(program, args.words, index, layout, paths, config);
    if (command == "ls") return index == args.words.size() ? list(program, paths, config)
                                                            : usage(program);
    return remove(program, args.words, index, paths, config);
}

}  // namespace

extern "C" int aos_routine_cli_main(int argc, char *argv[]) {
    try {
        return dispatch(argc, argv);
    } catch (const std::exception &error) {
        const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
                                  ? argv[0]
                                  : "aos routine";
        std::fprintf(stderr, "%s: %s\n", program, error.what());
        return 1;
    } catch (...) {
        const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
                                  ? argv[0]
                                  : "aos routine";
        std::fprintf(stderr, "%s: 發生未知錯誤\n", program);
        return 1;
    }
}
