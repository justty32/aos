#include "llms_internal.hpp"

#include <map>
#include <mutex>
#include <set>
#include <string>
#include <utility>

namespace aos::llms {
namespace {

using Table = std::map<std::string, Caps>;
using Names = std::set<std::string>;
using CacheKey = std::pair<std::string, std::string>;

std::map<CacheKey, Table> cache;
std::map<CacheKey, Names> name_cache;
std::mutex cache_mutex;

void read_flag(const json &info, const char *field,
               std::optional<bool> &target) {
    const auto found = info.find(field);
    if (found != info.end() && found->is_boolean()) {
        target = found->get<bool>();
    }
}

Caps parse_caps(const json &info) {
    Caps result;
    if (!info.is_object()) return result;
    read_flag(info, "supports_function_calling", result.tools);
    read_flag(info, "supports_tool_choice", result.tool_choice);
    read_flag(info, "supports_parallel_function_calling",
              result.parallel_tools);
    read_flag(info, "supports_vision", result.vision);
    read_flag(info, "supports_reasoning", result.reasoning);
    read_flag(info, "supports_response_schema", result.json_schema);
    read_flag(info, "supports_prompt_caching", result.caching);
    return result;
}

void apply_override(Caps &target, const Caps &overrides) {
    if (overrides.tools) target.tools = overrides.tools;
    if (overrides.tool_choice) target.tool_choice = overrides.tool_choice;
    if (overrides.parallel_tools) {
        target.parallel_tools = overrides.parallel_tools;
    }
    if (overrides.vision) target.vision = overrides.vision;
    if (overrides.reasoning) target.reasoning = overrides.reasoning;
    if (overrides.json_schema) target.json_schema = overrides.json_schema;
    if (overrides.caching) target.caching = overrides.caching;
}

Table fetch(const LLM::Impl &llm) noexcept {
    try {
        HttpRequest request;
        request.method = "GET";
        request.url = llm.root_url + "/model/info";
        request.headers = {"Authorization: Bearer " + llm.key};
        request.timeout_ms = 5000;
        const HttpResponse response = llm.transport(request);
        if (!response.error.empty() || response.status < 200 ||
            response.status >= 300) {
            return {};
        }
        const json body = json::parse(response.body);
        const auto data = body.find("data");
        if (data == body.end() || !data->is_array()) return {};
        Table result;
        for (const json &entry : *data) {
            if (!entry.is_object()) continue;
            const auto name = entry.find("model_name");
            if (name == entry.end() || !name->is_string()) continue;
            const auto info = entry.find("model_info");
            result[name->get<std::string>()] =
                info == entry.end() ? Caps{} : parse_caps(*info);
        }
        return result;
    } catch (...) {
        return {};
    }
}

Table table(const LLM::Impl &llm) {
    std::lock_guard lock(cache_mutex);
    const CacheKey key{llm.root_url, llm.key};
    const auto found = cache.find(key);
    if (found != cache.end()) return found->second;
    Table result = fetch(llm);
    cache.emplace(key, result);
    return result;
}

/* `/model/info` 是 LiteLLM proxy 專屬的，能力也只有它答得出來。但「這個端點上
 * 有哪些模型」是每個 OpenAI 相容端點都答得出來的 —— 標準的 `/v1/models`。
 * 只查前者的話，直接打 LM Studio 之類的端點會得到一片空白。 */
Names fetch_names(const LLM::Impl &llm) noexcept {
    try {
        HttpRequest request;
        request.method = "GET";
        request.url = llm.base_url + "/models";
        request.headers = {"Authorization: Bearer " + llm.key};
        request.timeout_ms = 5000;
        const HttpResponse response = llm.transport(request);
        if (!response.error.empty() || response.status < 200 ||
            response.status >= 300) {
            return {};
        }
        const json body = json::parse(response.body);
        const auto data = body.find("data");
        if (data == body.end() || !data->is_array()) return {};
        Names result;
        for (const json &entry : *data) {
            if (!entry.is_object()) continue;
            const auto id = entry.find("id");
            if (id != entry.end() && id->is_string()) {
                result.insert(id->get<std::string>());
            }
        }
        return result;
    } catch (...) {
        return {};
    }
}

Names names(const LLM::Impl &llm) {
    std::lock_guard lock(cache_mutex);
    const CacheKey key{llm.base_url, llm.key};
    const auto found = name_cache.find(key);
    if (found != name_cache.end()) return found->second;
    Names result = fetch_names(llm);
    name_cache.emplace(key, result);
    return result;
}

}  // namespace

Caps cached_caps(const LLM::Impl &llm) {
    const Table remote = table(llm);
    Caps result;
    const auto found = remote.find(llm.model);
    if (found != remote.end()) result = found->second;
    apply_override(result, llm.caps_override);
    return result;
}

std::vector<ModelInfo> cached_models(const LLM::Impl &llm) {
    // 兩個來源聯集：`/model/info` 給名字加能力（只有 proxy 有），
    // `/v1/models` 給名字（每個 OpenAI 相容端點都有）。只出現在後者的模型，
    // 能力就是「不知道」——那是實話，不是查失敗。
    const Table remote = table(llm);
    Names all = names(llm);
    for (const auto &[name, caps] : remote) all.insert(name);

    std::vector<ModelInfo> result;
    result.reserve(all.size());
    for (const std::string &name : all) {
        const auto found = remote.find(name);
        ModelInfo model{.name = name,
                        .caps = found == remote.end() ? Caps{} : found->second};
        if (name == llm.model) apply_override(model.caps, llm.caps_override);
        result.push_back(std::move(model));
    }
    return result;
}

void clear_cached_caps() {
    std::lock_guard lock(cache_mutex);
    cache.clear();
    name_cache.clear();
}

}  // namespace aos::llms
