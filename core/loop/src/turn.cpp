#include <aos/loop.hpp>

#include "fs.hpp"
#include "state.hpp"

#include <chrono>
#include <cctype>
#include <cstdint>
#include <string>
#include <utility>
#include <vector>

namespace aos::loop {
namespace {

exec::Spawn to_spawn(const Layout &layout, std::uint64_t turn,
                     const wire::Inst &inst) {
    exec::Spawn spawn;
    spawn.argv = inst.argv;
    spawn.env = inst.env;
    spawn.env["AOS_FOLDER"] = layout.folder;
    spawn.env["AOS_TURN"] = std::to_string(turn);
    spawn.cwd = inst.cwd.empty() ? layout.folder
                                 : fs::join(layout.folder, inst.cwd);
    spawn.stdin_data = inst.stdin_data;
    spawn.timeout_ms = inst.timeout_ms;
    return spawn;
}

wire::Outcome to_outcome(const wire::Inst &inst,
                         const exec::Result &result) {
    wire::Outcome outcome;
    outcome.id = inst.id;
    if (result.signal == 0) {
        outcome.exit = result.exit;
    } else {
        outcome.signal = result.signal;
    }
    outcome.stdout_text = result.stdout_text;
    outcome.stderr_text = result.stderr_text;
    outcome.started_at = result.started_at;
    outcome.ended_at = result.ended_at;
    return outcome;
}

std::uint64_t elapsed_since(
    const std::chrono::steady_clock::time_point &started) {
    return static_cast<std::uint64_t>(
        std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now() - started)
            .count());
}

std::string first_nonblank_line(const std::string &text) {
    std::size_t line_start = 0;
    while (line_start < text.size()) {
        std::size_t line_end = text.find('\n', line_start);
        if (line_end == std::string::npos) line_end = text.size();

        std::size_t content_start = line_start;
        while (content_start < line_end &&
               std::isspace(static_cast<unsigned char>(text[content_start]))) {
            ++content_start;
        }
        std::size_t content_end = line_end;
        while (content_end > content_start &&
               std::isspace(static_cast<unsigned char>(text[content_end - 1]))) {
            --content_end;
        }
        if (content_start != content_end) {
            return text.substr(content_start, content_end - content_start);
        }
        line_start = line_end + 1;
    }
    return {};
}

void collect_failures(const std::vector<wire::Inst> &insts,
                      const std::vector<exec::Result> &results,
                      TurnSummary &summary) {
    for (std::size_t index = 0; index < insts.size(); ++index) {
        const auto &result = results[index];
        if (result.signal == 0 && (result.exit == 0 || result.exit == 75)) {
            continue;
        }
        InstFailure failure;
        failure.id = insts[index].id;
        failure.exit = result.exit;
        failure.signal = result.signal;
        if (!insts[index].argv.empty()) {
            failure.argv0 = insts[index].argv.front();
        }
        failure.stderr_line = first_nonblank_line(result.stderr_text);
        summary.failures.push_back(std::move(failure));
    }
}

}  // namespace

bool run_turn(const Layout &layout, TurnSummary &summary,
              std::string &error) {
    const auto started = std::chrono::steady_clock::now();
    summary = {};
    error.clear();
    if (!ensure_layout(layout, error)) return false;

    const std::uint64_t turn = read_turn(layout);
    summary.turn = turn;
    auto insts = aggregate(layout, turn, error, &summary.every_count);
    if (!error.empty()) return false;
    summary.count = insts.size();

    if (insts.empty()) {
        wire::State state;
        state.turn = turn;
        state.phase = "idle";
        state.agents = mirror_agents(layout);
        if (!write_state(layout, state, error) ||
            !write_turn(layout, turn + 1, error)) {
            return false;
        }
        summary.elapsed_ms = elapsed_since(started);
        return true;
    }

    std::vector<exec::Spawn> spawns;
    spawns.reserve(insts.size());
    for (const auto &inst : insts) {
        spawns.push_back(to_spawn(layout, turn, inst));
    }

    auto running = exec::start_all(spawns);
    wire::State state;
    state.turn = turn;
    state.phase = "running";
    state.running = detail::running_entries(insts, running);
    state.agents = mirror_agents(layout);
    if (!write_state(layout, state, error)) {
        // 已經 fork 的子行程仍須收乾淨，否則呼叫者會留下 zombie。
        exec::wait_all(running);
        return false;
    }

    const auto results = exec::wait_all(running);
    const std::string outputs = out_dir(layout, turn);
    if (!fs::mkdir_p(outputs, error)) return false;
    for (std::size_t index = 0; index < insts.size(); ++index) {
        const wire::Outcome outcome = to_outcome(insts[index], results[index]);
        const std::string path = fs::join(outputs, insts[index].id + ".json");
        if (!fs::write_atomic(path, wire::to_json_text(outcome), error)) {
            return false;
        }
    }
    collect_failures(insts, results, summary);

    state.phase = "idle";
    detail::mark_done(state.running, results);
    state.agents = mirror_agents(layout);
    if (!write_state(layout, state, error) ||
        !write_turn(layout, turn + 1, error)) {
        return false;
    }
    summary.elapsed_ms = elapsed_since(started);
    return true;
}

}  // namespace aos::loop
