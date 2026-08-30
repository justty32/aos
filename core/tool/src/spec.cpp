#include <aos/tool.hpp>

#include <nlohmann/json.hpp>

#include <array>
#include <stdexcept>
#include <string>

namespace aos::tool {
namespace {

using Json = nlohmann::json;

std::string label(std::string_view source_hint) {
    return source_hint.empty() ? "tool spec" : std::string(source_hint);
}

[[noreturn]] void invalid(std::string_view source_hint,
                          const std::string &message) {
    throw std::runtime_error(label(source_hint) + ": " + message);
}

std::string required_string(const Json &root, const char *key,
                            std::string_view source_hint) {
    if (!root.contains(key) || !root[key].is_string()) {
        invalid(source_hint, std::string("缺少字串欄位 ") + key);
    }
    const std::string value = root[key].get<std::string>();
    if (value.empty()) {
        invalid(source_hint, std::string(key) + " 不可為空");
    }
    return value;
}

std::string optional_string(const Json &root, const char *key,
                            std::string default_value,
                            std::string_view source_hint) {
    if (!root.contains(key)) return default_value;
    if (!root[key].is_string()) {
        invalid(source_hint, std::string(key) + " 必須是字串");
    }
    return root[key].get<std::string>();
}

std::vector<std::string> string_array(const Json &root, const char *key,
                                      bool required,
                                      std::string_view source_hint) {
    if (!root.contains(key)) {
        if (required) invalid(source_hint, std::string("缺少陣列欄位 ") + key);
        return {};
    }
    if (!root[key].is_array()) {
        invalid(source_hint, std::string(key) + " 必須是字串陣列");
    }
    std::vector<std::string> values;
    for (const Json &item : root[key]) {
        if (!item.is_string()) {
            invalid(source_hint, std::string(key) + " 必須是字串陣列");
        }
        values.push_back(item.get<std::string>());
    }
    if (required && values.empty()) {
        invalid(source_hint, std::string(key) + " 不可為空");
    }
    return values;
}

bool one_of(std::string_view value,
            std::initializer_list<std::string_view> choices) {
    for (std::string_view choice : choices) {
        if (value == choice) return true;
    }
    return false;
}

void validate_spec(const Spec &spec, std::string_view source_hint) {
    try {
        validate_tool_name(spec.name);
    } catch (const std::exception &error) {
        invalid(source_hint, error.what());
    }
    if (spec.argv.empty()) invalid(source_hint, "argv 不可為空");
    if (spec.description.empty()) invalid(source_hint, "description 不可為空");
    if (!one_of(spec.args, {"list", "string", "none"})) {
        invalid(source_hint, "args 只能是 list、string 或 none");
    }
    if (!one_of(spec.stdin_mode, {"none", "text"})) {
        invalid(source_hint, "stdin 只能是 none 或 text");
    }
    if (!one_of(spec.source, {"manual", "metainfo", "header"})) {
        invalid(source_hint, "source 只能是 manual、metainfo 或 header");
    }
}

void put_if_nonempty(Json &root, const char *key, const std::string &value) {
    if (!value.empty()) root[key] = value;
}

}  // namespace

void validate_tool_name(std::string_view name) {
    if (name.empty()) throw std::runtime_error("工具名稱不可為空");
    for (const unsigned char character : name) {
        const bool valid = (character >= 'A' && character <= 'Z') ||
                           (character >= 'a' && character <= 'z') ||
                           (character >= '0' && character <= '9') ||
                           character == '_' || character == '.' ||
                           character == '-';
        if (!valid) {
            throw std::runtime_error(
                "工具名稱只能包含英文字母、數字、底線、句點與連字號");
        }
    }
}

Spec parse_spec(std::string_view json_text, std::string_view source_hint) {
    Json root;
    try {
        root = Json::parse(json_text);
    } catch (const Json::exception &error) {
        invalid(source_hint, std::string("JSON 無法解析: ") + error.what());
    }
    if (!root.is_object()) invalid(source_hint, "頂層必須是 JSON object");

    Spec spec;
    spec.name = required_string(root, "name", source_hint);
    spec.argv = string_array(root, "argv", true, source_hint);
    spec.description = required_string(root, "description", source_hint);
    spec.args = optional_string(root, "args", "list", source_hint);
    spec.stdin_mode = optional_string(root, "stdin", "none", source_hint);
    spec.cwd = optional_string(root, "cwd", "", source_hint);
    spec.source = optional_string(root, "source", "manual", source_hint);
    spec.lifecycle = optional_string(root, "lifecycle", "", source_hint);
    spec.state = optional_string(root, "state", "", source_hint);
    spec.guarantee = optional_string(root, "guarantee", "", source_hint);
    spec.interruptible =
        optional_string(root, "interruptible", "", source_hint);
    spec.predictability =
        optional_string(root, "predictability", "", source_hint);
    spec.stage = optional_string(root, "stage", "", source_hint);
    spec.env_allow = string_array(root, "env_allow", false, source_hint);

    if (root.contains("timeout_ms")) {
        if (!root["timeout_ms"].is_number_unsigned()) {
            invalid(source_hint, "timeout_ms 必須是非負整數");
        }
        spec.timeout_ms = root["timeout_ms"].get<std::uint64_t>();
    }
    if (root.contains("network")) {
        if (!root["network"].is_boolean()) {
            invalid(source_hint, "network 必須是 bool");
        }
        spec.network = root["network"].get<bool>();
        spec.network_declared = true;
    }

    validate_spec(spec, source_hint);
    return spec;
}

std::string spec_to_json(const Spec &spec) {
    validate_spec(spec, spec.name.empty() ? "tool spec" : spec.name);
    Json root = {{"name", spec.name},
                 {"argv", spec.argv},
                 {"description", spec.description},
                 {"args", spec.args},
                 {"stdin", spec.stdin_mode},
                 {"source", spec.source}};
    put_if_nonempty(root, "cwd", spec.cwd);
    if (spec.timeout_ms != 0) root["timeout_ms"] = spec.timeout_ms;
    put_if_nonempty(root, "lifecycle", spec.lifecycle);
    put_if_nonempty(root, "state", spec.state);
    put_if_nonempty(root, "guarantee", spec.guarantee);
    put_if_nonempty(root, "interruptible", spec.interruptible);
    put_if_nonempty(root, "predictability", spec.predictability);
    put_if_nonempty(root, "stage", spec.stage);
    if (spec.network_declared) root["network"] = spec.network;
    if (!spec.env_allow.empty()) root["env_allow"] = spec.env_allow;
    return root.dump(2) + "\n";
}

}  // namespace aos::tool
