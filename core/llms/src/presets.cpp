#include <aos/llms.hpp>

#include "llms_internal.hpp"
#include "presets_data.hpp"

#include <fstream>
#include <iterator>
#include <set>
#include <sstream>
#include <stdexcept>
#include <type_traits>
#include <utility>

namespace aos::llms {
namespace {

PresetState fail(PresetState state, std::string text, std::string &message) {
    message = std::move(text);
    return state;
}

PresetState validate(const std::string &text, json &presets,
                     std::string &message) {
    try {
        presets = json::parse(text);
    } catch (const json::parse_error &error) {
        return fail(PresetState::JsonSyntax,
                    "presets JSON 讀不起來：" + std::string(error.what()),
                    message);
    }
    if (!presets.is_object()) {
        return fail(PresetState::InvalidFormat,
                    "presets 最外層要是以 id 為 key 的 object", message);
    }
    const std::set<std::string> allowed = {
        "endpoint", "model", "parameters", "description"};
    const std::set<std::string> required = {
        "endpoint", "model", "parameters"};
    for (auto it = presets.begin(); it != presets.end(); ++it) {
        if (it.key().empty() || !it.value().is_object()) {
            return fail(PresetState::InvalidFormat,
                        "preset id 要是非空字串，而且每筆要是 object", message);
        }
        std::set<std::string> actual;
        for (auto field = it.value().begin(); field != it.value().end();
             ++field) {
            actual.insert(field.key());
        }
        std::vector<std::string> unknown;
        std::vector<std::string> missing;
        for (const std::string &field : actual) {
            if (!allowed.contains(field)) unknown.push_back(field);
        }
        for (const std::string &field : required) {
            if (!actual.contains(field)) missing.push_back(field);
        }
        if (!unknown.empty() || !missing.empty()) {
            return fail(PresetState::InvalidFormat,
                        "preset '" + it.key() +
                            "' 的欄位有多或少；必須含 endpoint / model / "
                            "parameters，另可含 description",
                        message);
        }
        const json &preset = it.value();
        if (!preset["endpoint"].is_string() ||
            preset["endpoint"].get_ref<const std::string &>().empty() ||
            !preset["model"].is_string() ||
            preset["model"].get_ref<const std::string &>().empty()) {
            return fail(PresetState::InvalidFormat,
                        "preset '" + it.key() +
                            "' 的 endpoint 與 model 要是非空字串",
                        message);
        }
        if (!preset["parameters"].is_object()) {
            return fail(PresetState::InvalidFormat,
                        "preset '" + it.key() +
                            "' 的 parameters 要是 object",
                        message);
        }
        if (preset.contains("description") &&
            !preset["description"].is_string()) {
            return fail(PresetState::InvalidFormat,
                        "preset '" + it.key() +
                            "' 的 description 要是字串",
                        message);
        }
    }
    return PresetState::Ok;
}

template <typename T>
void take_number(json &parameters, const char *name, std::optional<T> &out) {
    const auto found = parameters.find(name);
    if (found == parameters.end()) return;
    if constexpr (std::is_integral_v<T>) {
        if (!found->is_number_integer() && !found->is_number_unsigned()) {
            throw std::invalid_argument(std::string(name) + " 要是整數");
        }
    } else if (!found->is_number()) {
        throw std::invalid_argument(std::string(name) + " 要是數字");
    }
    out = found->get<T>();
    parameters.erase(found);
}

Params parse_params(json parameters) {
    Params result;
    take_number(parameters, "temperature", result.temperature);
    take_number(parameters, "top_p", result.top_p);
    take_number(parameters, "max_tokens", result.max_tokens);
    take_number(parameters, "seed", result.seed);
    take_number(parameters, "presence_penalty", result.presence_penalty);
    take_number(parameters, "frequency_penalty", result.frequency_penalty);
    const auto stop = parameters.find("stop");
    if (stop != parameters.end()) {
        result.stop_json = stop->dump();
        parameters.erase(stop);
    }
    result.extra_json = parameters.dump();
    /* 與一般 Params 走同一份形狀驗證。 */
    static_cast<void>(result.to_json());
    return result;
}

PresetState load_from_text(const std::string &id, const std::string &text,
                           LLM &out, std::string &message) {
    if (id.empty()) {
        return fail(PresetState::InvalidArgument,
                    "preset id 不可為空", message);
    }
    json presets;
    PresetState state = validate(text, presets, message);
    if (state != PresetState::Ok) return state;
    const auto found = presets.find(id);
    if (found == presets.end()) {
        return fail(PresetState::UnknownPreset,
                    "不認得的 preset '" + id + "'", message);
    }
    try {
        out = LLM((*found)["model"].get<std::string>(),
                  (*found)["endpoint"].get<std::string>(), std::nullopt,
                  parse_params((*found)["parameters"]));
    } catch (const std::bad_alloc &) {
        throw;
    } catch (const std::exception &error) {
        return fail(PresetState::InvalidFormat,
                    "preset '" + id + "' 的 parameters 不合法：" +
                        error.what(),
                    message);
    }
    message.clear();
    return PresetState::Ok;
}

}  // namespace

const char *to_string(PresetState state) noexcept {
    switch (state) {
        case PresetState::Ok: return "ok";
        case PresetState::InvalidArgument: return "invalid argument";
        case PresetState::IoError: return "I/O error";
        case PresetState::JsonSyntax: return "JSON syntax error";
        case PresetState::InvalidFormat: return "invalid format";
        case PresetState::UnknownPreset: return "unknown preset";
    }
    return "unknown";
}

PresetState load_preset(const std::string &id, LLM &out,
                        std::string &message) {
    return load_from_text(id, kEmbeddedPresets, out, message);
}

PresetState load_preset(const std::string &id, const char *path, LLM &out,
                        std::string &message) {
    if (path == nullptr || path[0] == '\0') {
        return fail(PresetState::InvalidArgument,
                    "presets 路徑要是非空字串", message);
    }
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        return fail(PresetState::IoError,
                    std::string(path) + " 讀不起來", message);
    }
    const std::string text{std::istreambuf_iterator<char>(input),
                           std::istreambuf_iterator<char>()};
    if (input.bad()) {
        return fail(PresetState::IoError,
                    std::string(path) + " 讀取失敗", message);
    }
    return load_from_text(id, text, out, message);
}

std::vector<std::string> preset_ids() {
    json presets;
    std::string message;
    if (validate(kEmbeddedPresets, presets, message) != PresetState::Ok) {
        return {};
    }
    std::vector<std::string> result;
    result.reserve(presets.size());
    for (auto it = presets.begin(); it != presets.end(); ++it) {
        result.push_back(it.key());
    }
    return result;
}

}  // namespace aos::llms
