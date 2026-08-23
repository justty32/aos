#include <aos/llms.hpp>

#include "llms_internal.hpp"

#include <algorithm>
#include <stdexcept>

namespace aos::llms {

json params_value(const Params &params) {
    json extra;
    try {
        extra = json::parse(params.extra_json);
    } catch (const json::parse_error &error) {
        throw std::invalid_argument("Params.extra_json 不是合法 JSON：" +
                                    std::string(error.what()));
    }
    if (!extra.is_object()) {
        throw std::invalid_argument("Params.extra_json 要是 JSON object");
    }
    json result = json::object();
    if (params.temperature) result["temperature"] = *params.temperature;
    if (params.top_p) result["top_p"] = *params.top_p;
    if (params.max_tokens) result["max_tokens"] = *params.max_tokens;
    if (params.seed) result["seed"] = *params.seed;
    if (params.stop_json) {
        json stop;
        try {
            stop = json::parse(*params.stop_json);
        } catch (const json::parse_error &error) {
            throw std::invalid_argument("Params.stop_json 不是合法 JSON：" +
                                        std::string(error.what()));
        }
        const bool string_list = stop.is_array() &&
            std::ranges::all_of(stop, [](const json &item) {
                return item.is_string();
            });
        if (!stop.is_string() && !string_list) {
            throw std::invalid_argument(
                "Params.stop_json 要是字串或字串 array");
        }
        result["stop"] = std::move(stop);
    }
    if (params.presence_penalty) {
        result["presence_penalty"] = *params.presence_penalty;
    }
    if (params.frequency_penalty) {
        result["frequency_penalty"] = *params.frequency_penalty;
    }
    /* Python 版的 extra 是直接展開；三個引擎欄位由 Bot 在最後再固定。 */
    for (auto it = extra.begin(); it != extra.end(); ++it) {
        result[it.key()] = it.value();
    }
    return result;
}

std::string Params::to_json() const { return params_value(*this).dump(); }

}  // namespace aos::llms
