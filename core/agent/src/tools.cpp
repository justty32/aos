#include "internal.hpp"

#include <nlohmann/json.hpp>

#include <algorithm>
#include <cctype>
#include <sstream>
#include <stdexcept>

namespace aos::agent {
namespace {

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

}  // namespace

namespace detail {

std::vector<Tool> default_tools() {
    return {{"sh", "用 sh -lc 執行一行 shell 指令。args 就是整行指令。",
             {"sh", "-lc", "{args}"}},
            {"ls", "列出資料夾內容。args 是選項與路徑，例如 -la 或 .",
             {"ls", "{args}"}},
            {"cat", "印出一個檔案的內容。args 是檔案路徑。",
             {"cat", "{args}"}}};
}

std::string system_prompt(const Paths &paths, std::string_view name,
                          std::uint64_t turn,
                          const std::vector<Tool> &tools) {
    std::ostringstream prompt;
    prompt << "你是一個名叫 " << name
           << " 的 agent，活在一個以回合推進的資料夾世界裡。現在是第 "
           << turn << " 回合。\n\n人格：\n"
           << read_text(paths.persona)
           << "\n\n你可以使用工具。要用工具時，在回覆的最後獨立一行輸出這樣的 JSON（只有一個，不要多寫）：\n"
              "{\"tool\":\"工具名\",\"args\":\"參數字串\"}\n"
              "工具的結果會在之後的回合以 tool 訊息回給你。不需要用工具時就正常回話，不要輸出那行 JSON。\n\n"
              "可用工具：\n";
    for (const Tool &tool : tools) {
        prompt << "- " << tool.name << ": " << tool.description << '\n';
    }
    return prompt.str();
}

}  // namespace detail

std::vector<Tool> read_tools(const std::filesystem::path &folder,
                             std::string_view name) {
    const detail::Paths paths = detail::paths_for(folder, name);
    try {
        const nlohmann::json root =
            nlohmann::json::parse(detail::read_text(paths.tools));
        if (!root.contains("tools") || !root["tools"].is_array()) {
            throw std::runtime_error("tools.json 缺少 tools 陣列");
        }
        std::vector<Tool> tools;
        for (const auto &item : root["tools"]) {
            if (!item.is_object() || !item.contains("name") ||
                !item["name"].is_string() || !item.contains("description") ||
                !item["description"].is_string() || !item.contains("argv") ||
                !item["argv"].is_array()) {
                throw std::runtime_error("tools.json 的工具格式錯誤");
            }
            Tool tool{item["name"].get<std::string>(),
                      item["description"].get<std::string>(), {}};
            for (const auto &argument : item["argv"]) {
                if (!argument.is_string()) {
                    throw std::runtime_error("tools.json 的 argv 必須全是字串");
                }
                tool.argv.push_back(argument.get<std::string>());
            }
            tools.push_back(std::move(tool));
        }
        return tools;
    } catch (const nlohmann::json::exception &error) {
        throw std::runtime_error(std::string("tools.json 無法解析: ") +
                                 error.what());
    }
}

std::vector<std::string> expand_argv(
    const std::vector<std::string> &argument_template,
    std::string_view args) {
    std::vector<std::string> expanded = argument_template;
    for (std::string &argument : expanded) {
        std::size_t position = 0;
        while ((position = argument.find("{args}", position)) !=
               std::string::npos) {
            argument.replace(position, 6, args);
            position += args.size();
        }
    }
    return expanded;
}

std::optional<ToolCall> extract_tool_call(std::string_view reply,
                                          const std::vector<Tool> &tools,
                                          std::string *unknown_tool) {
    if (unknown_tool != nullptr) unknown_tool->clear();
    std::vector<std::string_view> lines;
    while (true) {
        const std::size_t newline = reply.find('\n');
        lines.push_back(reply.substr(0, newline));
        if (newline == std::string_view::npos) break;
        reply.remove_prefix(newline + 1);
    }
    for (auto line = lines.rbegin(); line != lines.rend(); ++line) {
        const std::string_view candidate = trim(*line);
        if (candidate.size() < 2 || candidate.front() != '{' ||
            candidate.back() != '}') {
            continue;
        }
        try {
            const nlohmann::json value = nlohmann::json::parse(candidate);
            if (!value.is_object() || !value.contains("tool")) continue;
            if (!value["tool"].is_string() || !value.contains("args") ||
                !value["args"].is_string()) {
                return std::nullopt;
            }
            ToolCall call{value["tool"].get<std::string>(),
                          value["args"].get<std::string>()};
            const auto known = std::find_if(
                tools.begin(), tools.end(), [&](const Tool &tool) {
                    return tool.name == call.tool;
                });
            if (known == tools.end()) {
                if (unknown_tool != nullptr) *unknown_tool = call.tool;
                return std::nullopt;
            }
            return call;
        } catch (const nlohmann::json::exception &) {
            continue;
        }
    }
    return std::nullopt;
}

}  // namespace aos::agent
