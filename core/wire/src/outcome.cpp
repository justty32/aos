#include <aos/wire.hpp>

#include "json_io.hpp"

#include <optional>
#include <string>

namespace aos::wire {

std::optional<Outcome> parse_outcome(const std::string &json_text,
                                     std::string &error) {
    error.clear();
    detail::Json document;
    if (!detail::parse_object(json_text, document, error)) {
        return std::nullopt;
    }

    Outcome outcome;
    if (!detail::take_string(document, "id", outcome.id, error) ||
        !detail::take_opt_int(document, "exit", outcome.exit, error) ||
        !detail::take_opt_int(document, "signal", outcome.signal, error) ||
        !detail::take_string(document, "stdout", outcome.stdout_text, error) ||
        !detail::take_string(document, "stderr", outcome.stderr_text, error) ||
        !detail::take_string(document, "started_at", outcome.started_at, error) ||
        !detail::take_string(document, "ended_at", outcome.ended_at, error)) {
        return std::nullopt;
    }
    if (outcome.exit.has_value() == outcome.signal.has_value()) {
        error = "欄位 'exit' 與 'signal' 必須恰有一個非 null";
        return std::nullopt;
    }
    return outcome;
}

std::string to_json_text(const Outcome &outcome) {
    detail::Json document = detail::Json::object();
    document["id"] = outcome.id;
    document["exit"] = outcome.exit.has_value()
                           ? detail::Json(*outcome.exit)
                           : detail::Json(nullptr);
    document["signal"] = outcome.signal.has_value()
                             ? detail::Json(*outcome.signal)
                             : detail::Json(nullptr);
    document["stdout"] = outcome.stdout_text;
    document["stderr"] = outcome.stderr_text;
    document["started_at"] = outcome.started_at;
    document["ended_at"] = outcome.ended_at;
    return detail::dump_text(document);
}

}  // namespace aos::wire
