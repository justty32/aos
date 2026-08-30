#pragma once

#include <aos/agent.hpp>

#include <filesystem>
#include <string>
#include <string_view>
#include <vector>

namespace aos::agent::detail {

struct Paths {
    std::filesystem::path folder;
    std::filesystem::path aos;
    std::filesystem::path inbox;
    std::filesystem::path every;
    std::filesystem::path agent;
    std::filesystem::path persona;
    std::filesystem::path history;
    std::filesystem::path status;
    std::filesystem::path say;
    std::filesystem::path log;
    std::filesystem::path tools;
    std::filesystem::path pending;
};

Paths paths_for(const std::filesystem::path &folder, std::string_view name);
void validate_name(std::string_view name);

std::string read_text(const std::filesystem::path &path);
void atomic_write(const std::filesystem::path &path, std::string_view text);
void append_log(const Paths &paths, std::uint64_t turn,
                std::string_view role, std::string_view content);
void append_note(const Paths &paths, std::string_view text);

void write_history(const Paths &paths, const std::vector<Message> &messages);
void write_status(const Paths &paths, std::string_view status,
                  std::string_view detail, std::uint64_t turn);
void write_pending(const Paths &paths, const Pending &pending);
void write_tools(const Paths &paths, const std::vector<Tool> &tools);

std::vector<Tool> default_tools();
std::string system_prompt(const Paths &paths, std::string_view name,
                          std::uint64_t turn,
                          const std::vector<Tool> &tools);

void deliver(const Paths &paths, std::string_view id,
             const std::vector<std::string> &argv,
             bool tool_instruction = false);

}  // namespace aos::agent::detail
