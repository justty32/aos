#include <aos/wire.hpp>

#include "json_io.hpp"

#include <cstddef>
#include <optional>
#include <string>
#include <utility>

namespace aos::wire {
namespace {

bool parse_running(const detail::Json &value, std::size_t index,
                   RunningEntry &entry, std::string &error) {
    if (!value.is_object()) {
        error = "欄位 'running[" + std::to_string(index) + "]' 必須是物件";
        return false;
    }
    if (!detail::take_string(value, "id", entry.id, error) ||
        !detail::take_string(value, "argv0", entry.argv0, error) ||
        !detail::take_nullable_int64(value, "pid", entry.pid, error) ||
        !detail::take_string(value, "started_at", entry.started_at, error) ||
        !detail::take_string(value, "status", entry.status, error) ||
        !detail::take_opt_int(value, "exit", entry.exit, error)) {
        error = "running[" + std::to_string(index) + "]: " + error;
        return false;
    }
    return true;
}

detail::Json running_json(const RunningEntry &entry) {
    detail::Json value = detail::Json::object();
    value["id"] = entry.id;
    value["argv0"] = entry.argv0;
    value["pid"] = entry.pid == -1 ? detail::Json(nullptr)
                                    : detail::Json(entry.pid);
    value["started_at"] = entry.started_at;
    value["status"] = entry.status;
    value["exit"] = entry.exit.has_value() ? detail::Json(*entry.exit)
                                            : detail::Json(nullptr);
    return value;
}

}  // namespace

std::optional<State> parse_state(const std::string &json_text,
                                 std::string &error) {
    error.clear();
    detail::Json document;
    if (!detail::parse_object(json_text, document, error)) {
        return std::nullopt;
    }

    State state;
    if (!detail::take_uint(document, "turn", state.turn, error) ||
        !detail::take_string(document, "phase", state.phase, error)) {
        return std::nullopt;
    }

    const auto running = document.find("running");
    if (running == document.end() || !running->is_array()) {
        error = "欄位 'running' 必須是陣列";
        return std::nullopt;
    }
    state.running.reserve(running->size());
    for (std::size_t index = 0; index < running->size(); ++index) {
        RunningEntry entry;
        if (!parse_running((*running)[index], index, entry, error)) {
            return std::nullopt;
        }
        state.running.push_back(std::move(entry));
    }

    const auto agents = document.find("agents");
    if (agents == document.end() || !agents->is_object()) {
        error = "欄位 'agents' 必須是物件";
        return std::nullopt;
    }
    for (const auto &[name, value] : agents->items()) {
        state.agents.emplace(
            name, value.dump(-1, ' ', false,
                             detail::Json::error_handler_t::replace));
    }
    return state;
}

std::string to_json_text(const State &state) {
    detail::Json document = detail::Json::object();
    document["turn"] = state.turn;
    document["phase"] = state.phase;

    detail::Json running = detail::Json::array();
    for (const RunningEntry &entry : state.running) {
        running.push_back(running_json(entry));
    }
    document["running"] = std::move(running);

    detail::Json agents = detail::Json::object();
    for (const auto &[name, text] : state.agents) {
        detail::Json value = detail::Json::parse(text, nullptr, false);
        agents[name] = value.is_discarded() ? detail::Json(nullptr)
                                            : std::move(value);
    }
    document["agents"] = std::move(agents);
    return detail::dump_text(document);
}

}  // namespace aos::wire
