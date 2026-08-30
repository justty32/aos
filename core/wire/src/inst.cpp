#include <aos/wire.hpp>

#include "json_io.hpp"

#include <optional>
#include <string>

namespace aos::wire {

std::optional<Inst> parse_inst(const std::string &json_text,
                               const std::string &default_id,
                               std::string &error) {
    error.clear();
    detail::Json document;
    if (!detail::parse_object(json_text, document, error)) {
        return std::nullopt;
    }

    Inst inst;
    inst.id = default_id;
    if (!detail::take_string(document, "id", inst.id, error, false) ||
        !detail::take_string_array(document, "argv", inst.argv, error) ||
        !detail::take_string_map(document, "env", inst.env, error, false) ||
        !detail::take_string(document, "cwd", inst.cwd, error, false) ||
        !detail::take_string(document, "stdin", inst.stdin_data, error, false) ||
        !detail::take_uint(document, "timeout_ms", inst.timeout_ms, error,
                           false)) {
        return std::nullopt;
    }
    if (inst.argv.empty()) {
        error = "欄位 'argv' 不可為空陣列";
        return std::nullopt;
    }
    return inst;
}

std::string to_json_text(const Inst &inst) {
    detail::Json document = detail::Json::object();
    document["id"] = inst.id;
    document["argv"] = inst.argv;
    if (!inst.env.empty()) {
        document["env"] = inst.env;
    }
    if (!inst.cwd.empty()) {
        document["cwd"] = inst.cwd;
    }
    if (!inst.stdin_data.empty()) {
        document["stdin"] = inst.stdin_data;
    }
    document["timeout_ms"] = inst.timeout_ms;
    return detail::dump_text(document);
}

}  // namespace aos::wire
