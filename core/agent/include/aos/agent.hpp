#pragma once

#include <aos/export.h>
#include <aos/tool.hpp>

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

struct ToolCall {
    std::string tool;
    std::string shape;              // "list" | "string" | "none"
    std::vector<std::string> args;  // shape=="list" 時有效
    std::string args_text;          // shape=="string" 時有效
};

struct ToolCallError {
    std::string type;
    std::string message;
    std::string tool;
};

struct ToolCallResult {
    bool saw_json = false;
    std::optional<ToolCall> call;
    std::optional<ToolCallError> error;
};

struct PendingCall {
    std::string id;
    std::string tool;
    std::string args_json;  // args 的 JSON 文字
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

struct Engine {
    std::string kind = "lmstudio";
    std::string provider;
    std::string model;
    std::string session_id;
    int priority = 0;
};

struct PiRun {
    int exit_code = 0;
    std::string reply;
    std::vector<std::string> tool_calls;
    std::string stderr_text;
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
                            "你是一個可靠、好奇且言簡意賅的助手。",
                        const Engine &engine = {});

AOS_API Engine read_engine(const std::filesystem::path &folder,
                           std::string_view name);

AOS_API PiRun parse_pi_stream(std::string_view jsonl);

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

/* 世界層登記表 ∩ agent 白名單。 */
AOS_API std::vector<aos::tool::Spec> read_tools(
    const std::filesystem::path &folder, std::string_view name);

AOS_API std::vector<std::string> expand_argv(const aos::tool::Spec &spec,
                                             const ToolCall &call);

AOS_API ToolCallResult extract_tool_call(
    std::string_view reply, const std::vector<aos::tool::Spec> &tools);

AOS_API int step(const std::filesystem::path &folder, std::string_view name,
                 Completion completion = {}, std::string *error = nullptr);

}  // namespace aos::agent
