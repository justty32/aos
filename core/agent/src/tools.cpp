#include "internal.hpp"

#include <nlohmann/json.hpp>

#include <algorithm>
#include <cctype>
#include <sstream>
#include <stdexcept>
#include <unordered_set>

namespace aos::agent {
namespace {

using Json = nlohmann::json;

std::string_view trim(std::string_view text) {
    while (!text.empty() &&
           std::isspace(static_cast<unsigned char>(text.front()))) {
        text.remove_prefix(1);
    }
    while (!text.empty() &&
           std::isspace(static_cast<unsigned char>(text.back()))) {
        text.remove_suffix(1);
    }
    return text;
}

std::vector<std::string_view> lines_of(std::string_view text) {
    std::vector<std::string_view> lines;
    while (true) {
        const std::size_t newline = text.find('\n');
        lines.push_back(text.substr(0, newline));
        if (newline == std::string_view::npos) break;
        text.remove_prefix(newline + 1);
    }
    return lines;
}

std::vector<std::string> whitelist_names(const Json &root,
                                         const std::filesystem::path &path) {
    const Json *items = nullptr;
    if (root.is_array()) {
        items = &root;
    } else if (root.is_object() && root.contains("tools") &&
               root["tools"].is_array()) {
        items = &root["tools"];
    } else {
        throw std::runtime_error(path.string() +
                                 " 必須是字串陣列或含 tools 陣列的物件");
    }

    std::vector<std::string> names;
    for (const Json &item : *items) {
        if (item.is_string()) {
            names.push_back(item.get<std::string>());
        } else if (item.is_object() && item.contains("name") &&
                   item["name"].is_string()) {
            names.push_back(item["name"].get<std::string>());
        } else {
            throw std::runtime_error(path.string() +
                                     " 的工具白名單項目格式錯誤");
        }
    }
    return names;
}

ToolCallResult invalid_args(std::string_view name, std::string message) {
    ToolCallResult result;
    result.saw_json = true;
    result.error =
        ToolCallError{"invalid_args", std::move(message), std::string(name)};
    return result;
}

std::string prompt_field(std::string text) {
    std::replace(text.begin(), text.end(), '\n', ' ');
    std::replace(text.begin(), text.end(), '\r', ' ');
    return text;
}

}  // namespace

namespace detail {

std::string system_prompt(const Paths &paths, std::string_view name,
                          std::uint64_t turn,
                          const std::vector<aos::tool::Spec> &tools) {
    std::ostringstream prompt;
    prompt << "你是一個名叫 " << name
           << " 的 agent，活在一個以回合推進的資料夾世界裡。現在是第 " << turn
           << " 回合。\n\n人格：\n"
           << read_text(paths.persona);
    if (tools.empty()) return prompt.str();

    prompt
        << "\n\n你可以使用工具。要用工具時，在回覆的最後獨立一行輸出這樣的 "
           "JSON（只有一個，不要多寫）：\n"
           "{\"tool\":\"工具名\",\"args\":[\"參數1\",\"參數2\"]}\n"
           "args 的形狀由每個工具的登記決定：args: list 要給 JSON "
           "字串陣列；args: string 要給一個字串；args: none 就不要寫 args "
           "這個欄位。\n"
           "工具的結果會在之後的回合以一則 tool 訊息回給你，內容是固定形狀的 "
           "JSON。\n"
           "不需要用工具時就正常回話，不要輸出那行 JSON。\n\n"
           "可用工具：\n";
    for (const aos::tool::Spec &tool : tools) {
        prompt << "- " << tool.name << " — " << prompt_field(tool.description)
               << " (args: " << tool.args << ", stdin: " << tool.stdin_mode;
        if (!tool.predictability.empty()) {
            prompt << ", 可預期性: " << prompt_field(tool.predictability);
        }
        prompt << ")\n";
    }
    return prompt.str();
}

}  // namespace detail

std::vector<aos::tool::Spec> read_tools(const std::filesystem::path &folder,
                                        std::string_view name) {
    const detail::Paths paths = detail::paths_for(folder, name);
    std::vector<aos::tool::Spec> registry =
        aos::tool::read_registry(paths.folder);
    if (!std::filesystem::exists(paths.tools)) return registry;

    try {
        const Json root = Json::parse(detail::read_text(paths.tools));
        const std::vector<std::string> names =
            whitelist_names(root, paths.tools);
        const std::unordered_set<std::string> allowed(names.begin(),
                                                      names.end());
        registry.erase(std::remove_if(registry.begin(), registry.end(),
                                      [&](const aos::tool::Spec &spec) {
                                          return !allowed.contains(spec.name);
                                      }),
                       registry.end());
        return registry;
    } catch (const Json::exception &error) {
        throw std::runtime_error(paths.tools.string() +
                                 " JSON 無法解析: " + error.what());
    }
}

std::vector<std::string> expand_argv(const aos::tool::Spec &spec,
                                     const ToolCall &call) {
    std::vector<std::string> expanded = spec.argv;
    if (call.shape == "none") return expanded;
    if (call.shape == "list") {
        expanded.insert(expanded.end(), call.args.begin(), call.args.end());
        return expanded;
    }
    if (call.shape != "string") {
        throw std::invalid_argument("未知的工具 args 形狀: " + call.shape);
    }

    bool replaced = false;
    for (std::string &argument : expanded) {
        std::size_t position = 0;
        while ((position = argument.find("{args}", position)) !=
               std::string::npos) {
            argument.replace(position, 6, call.args_text);
            position += call.args_text.size();
            replaced = true;
        }
    }
    if (!replaced) expanded.push_back(call.args_text);
    return expanded;
}

ToolCallResult extract_tool_call(std::string_view reply,
                                 const std::vector<aos::tool::Spec> &tools) {
    const std::vector<std::string_view> lines = lines_of(reply);
    for (auto line = lines.rbegin(); line != lines.rend(); ++line) {
        const std::string_view candidate = trim(*line);
        if (candidate.size() < 2 || candidate.front() != '{' ||
            candidate.back() != '}') {
            continue;
        }
        try {
            const Json value = Json::parse(candidate);
            if (!value.is_object() || !value.contains("tool") ||
                !value["tool"].is_string()) {
                continue;
            }

            ToolCallResult result;
            result.saw_json = true;
            const std::string tool_name = value["tool"].get<std::string>();
            const auto spec = std::find_if(tools.begin(), tools.end(),
                                           [&](const aos::tool::Spec &tool) {
                                               return tool.name == tool_name;
                                           });
            if (spec == tools.end()) {
                result.error = ToolCallError{
                    "unknown_tool", "沒有登記工具 " + tool_name, tool_name};
                return result;
            }

            ToolCall call;
            call.tool = tool_name;
            call.shape = spec->args;
            if (spec->args == "list") {
                if (!value.contains("args") || !value["args"].is_array()) {
                    return invalid_args(tool_name,
                                        "工具 " + tool_name +
                                            " 的 args 必須是字串陣列");
                }
                for (const Json &argument : value["args"]) {
                    if (!argument.is_string()) {
                        return invalid_args(tool_name,
                                            "工具 " + tool_name +
                                                " 的 args 必須是字串陣列");
                    }
                    call.args.push_back(argument.get<std::string>());
                }
            } else if (spec->args == "string") {
                if (!value.contains("args") || !value["args"].is_string()) {
                    return invalid_args(tool_name, "工具 " + tool_name +
                                                       " 的 args 必須是字串");
                }
                call.args_text = value["args"].get<std::string>();
            } else if (spec->args == "none") {
                const bool valid =
                    !value.contains("args") || value["args"].is_null() ||
                    (value["args"].is_array() && value["args"].empty()) ||
                    (value["args"].is_string() &&
                     value["args"].get_ref<const std::string &>().empty());
                if (!valid) {
                    return invalid_args(tool_name,
                                        "工具 " + tool_name + " 不收 args");
                }
            }
            result.call = std::move(call);
            return result;
        } catch (const Json::exception &) {
            continue;
        }
    }
    return {};
}

}  // namespace aos::agent
