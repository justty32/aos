#pragma once

#include <aos/export.h>

#include <cstdint>
#include <filesystem>
#include <functional>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace aos::agent {

struct Message {
    std::string role;
    std::string content;
};

struct Tool {
    std::string name;
    std::string description;
    std::vector<std::string> argv;
};

struct ToolCall {
    std::string tool;
    std::string args;
};

struct PendingCall {
    std::string id;
    std::string tool;
    std::string args;
};

struct Pending {
    std::uint64_t turn = 0;
    std::vector<PendingCall> calls;
};

struct Status {
    std::string status;
    std::string detail;
    std::string updated_at;
    std::uint64_t turn = 0;
};

using Completion =
    std::function<std::string(const std::vector<Message> &messages)>;

AOS_API std::filesystem::path absolute_folder(
    const std::filesystem::path &folder);

/* given 非空就用它；否則解析目前的資料夾世界。 */
AOS_API std::filesystem::path resolve_folder(
    const std::filesystem::path &given = {});

/* given 非空就用它；否則回傳 folder 裡唯一的 agent 名稱。 */
AOS_API std::string resolve_name(const std::filesystem::path &folder,
                                 std::string_view given = {});

AOS_API void initialize(const std::filesystem::path &folder,
                        std::string_view name,
                        std::string_view persona =
                            "你是一個可靠、好奇且言簡意賅的助手。");

AOS_API void say(const std::filesystem::path &folder, std::string_view name,
                 std::string_view text);

AOS_API std::string read_log(const std::filesystem::path &folder,
                             std::string_view name);

AOS_API Status read_status(const std::filesystem::path &folder,
                           std::string_view name);

AOS_API std::string read_status_file(const std::filesystem::path &folder,
                                     std::string_view name);

AOS_API std::vector<Message> read_history(
    const std::filesystem::path &folder, std::string_view name);

AOS_API Pending read_pending(const std::filesystem::path &folder,
                             std::string_view name);

AOS_API std::vector<Tool> read_tools(const std::filesystem::path &folder,
                                     std::string_view name);

AOS_API std::vector<std::string> expand_argv(
    const std::vector<std::string> &argument_template,
    std::string_view args);

AOS_API std::optional<ToolCall> extract_tool_call(
    std::string_view reply, const std::vector<Tool> &tools,
    std::string *unknown_tool = nullptr);

AOS_API int step(const std::filesystem::path &folder, std::string_view name,
                 Completion completion = {}, std::string *error = nullptr);

}  // namespace aos::agent
