#pragma once

#include <cstdint>
#include <filesystem>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace aos::tool::detail {

std::string read_text(const std::filesystem::path &path);
void atomic_write(const std::filesystem::path &path, std::string_view text);

struct ContactStatusRow {
    std::string name;
    std::string agent;
    std::string status;
    std::optional<std::uint64_t> turn;
    std::optional<std::uint64_t> unread;
    std::string last_error;
};

std::vector<ContactStatusRow>
contact_status_rows(const std::filesystem::path &root);
int contact_status_command(const char *program,
                           const std::vector<std::string> &words);

}  // namespace aos::tool::detail
