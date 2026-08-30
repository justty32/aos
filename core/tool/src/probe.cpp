#include <aos/tool.hpp>

#include <aos/exec.hpp>
#include <nlohmann/json.hpp>

#include <algorithm>
#include <cctype>
#include <exception>
#include <string>

namespace aos::tool {
namespace {

using Json = nlohmann::json;

bool allowed(std::string_view value,
             std::initializer_list<std::string_view> choices) {
    for (std::string_view choice : choices) {
        if (value == choice) return true;
    }
    return false;
}

std::string trim(std::string_view text) {
    std::size_t begin = 0;
    while (begin < text.size() &&
           std::isspace(static_cast<unsigned char>(text[begin]))) {
        ++begin;
    }
    std::size_t end = text.size();
    while (end > begin &&
           std::isspace(static_cast<unsigned char>(text[end - 1]))) {
        --end;
    }
    return std::string(text.substr(begin, end - begin));
}

std::string truncate_bytes(std::string value, std::size_t limit) {
    if (value.size() <= limit) return value;
    std::size_t end = limit;
    while (end > 0 &&
           (static_cast<unsigned char>(value[end]) & 0xc0U) == 0x80U) {
        --end;
    }
    value.resize(end);
    return value;
}

std::string first_nonempty_line(std::string_view output) {
    std::size_t begin = 0;
    while (begin <= output.size()) {
        const std::size_t newline = output.find('\n', begin);
        const std::size_t end =
            newline == std::string_view::npos ? output.size() : newline;
        std::string line = trim(output.substr(begin, end - begin));
        if (!line.empty()) return truncate_bytes(std::move(line), 200);
        if (newline == std::string_view::npos) break;
        begin = newline + 1;
    }
    return {};
}

void read_optional_fields(const Json &root, Spec &spec) {
    if (root.contains("args") && root["args"].is_string()) {
        const std::string value = root["args"].get<std::string>();
        if (allowed(value, {"list", "string", "none"})) spec.args = value;
    }
    if (root.contains("stdin") && root["stdin"].is_string()) {
        const std::string value = root["stdin"].get<std::string>();
        if (allowed(value, {"none", "text"})) spec.stdin_mode = value;
    }
    if (root.contains("timeout_ms") &&
        root["timeout_ms"].is_number_unsigned()) {
        spec.timeout_ms = root["timeout_ms"].get<std::uint64_t>();
    }
    if (root.contains("cwd") && root["cwd"].is_string()) {
        spec.cwd = root["cwd"].get<std::string>();
    }
    for (const char *key : {"lifecycle", "state", "guarantee",
                            "interruptible", "predictability", "stage"}) {
        if (!root.contains(key) || !root[key].is_string()) continue;
        std::string value = root[key].get<std::string>();
        if (std::string_view(key) == "lifecycle") spec.lifecycle = std::move(value);
        else if (std::string_view(key) == "state") spec.state = std::move(value);
        else if (std::string_view(key) == "guarantee") spec.guarantee = std::move(value);
        else if (std::string_view(key) == "interruptible") spec.interruptible = std::move(value);
        else if (std::string_view(key) == "predictability") spec.predictability = std::move(value);
        else spec.stage = std::move(value);
    }
    if (root.contains("network") && root["network"].is_boolean()) {
        spec.network = root["network"].get<bool>();
        spec.network_declared = true;
    }
    if (root.contains("env_allow") && root["env_allow"].is_array()) {
        std::vector<std::string> values;
        bool valid = true;
        for (const Json &item : root["env_allow"]) {
            if (!item.is_string()) {
                valid = false;
                break;
            }
            values.push_back(item.get<std::string>());
        }
        if (valid) spec.env_allow = std::move(values);
    }
}

}  // namespace

Probe probe_metainfo(const std::vector<std::string> &argv,
                     std::string_view flag) {
    Probe probe;
    try {
        if (argv.empty()) {
            probe.detail = "沒有可執行的 argv";
            return probe;
        }
        aos::exec::Spawn spawn;
        spawn.argv = argv;
        spawn.argv.emplace_back(flag);
        spawn.timeout_ms = 3000;
        std::vector<aos::exec::Running> running =
            aos::exec::start_all({spawn});
        std::vector<aos::exec::Result> results =
            aos::exec::wait_all(running);
        if (results.empty()) {
            probe.detail = "探測行程沒有回傳結果";
            return probe;
        }
        const aos::exec::Result &result = results.front();
        if (!result.error.empty()) {
            probe.detail = "探測行程失敗：" + result.error;
            return probe;
        }
        if (result.signal != 0) {
            probe.detail = "探測行程被 signal " +
                           std::to_string(result.signal) + " 結束";
            return probe;
        }
        if (result.exit != 0) {
            probe.detail = "探測行程退出碼是 " + std::to_string(result.exit);
            return probe;
        }

        try {
            const Json root = Json::parse(result.stdout_text);
            if (root.is_object() && root.contains("description") &&
                root["description"].is_string() &&
                !root["description"].get_ref<const std::string &>().empty()) {
                probe.ok = true;
                probe.source = "metainfo";
                probe.description = root["description"].get<std::string>();
                probe.spec.description = probe.description;
                read_optional_fields(root, probe.spec);
                return probe;
            }
        } catch (const Json::exception &) {
        }

        probe.description = first_nonempty_line(result.stdout_text);
        if (!probe.description.empty()) {
            probe.ok = true;
            probe.source = "header";
            return probe;
        }
        probe.detail = "探測行程沒有輸出可用的表述";
        return probe;
    } catch (const std::exception &error) {
        probe.detail = std::string("探測失敗：") + error.what();
        return probe;
    } catch (...) {
        probe.detail = "探測發生未知錯誤";
        return probe;
    }
}

}  // namespace aos::tool
