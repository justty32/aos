#include <aos/agent.hpp>

#include "internal.hpp"

#include <algorithm>
#include <charconv>
#include <chrono>
#include <ctime>
#include <limits>
#include <system_error>

namespace aos::agent {
namespace {

std::string format_utc(std::time_t value) {
    std::tm utc{};
    if (gmtime_r(&value, &utc) == nullptr) return {};
    char buffer[sizeof("2026-08-30T12:12:45Z")];
    if (std::strftime(buffer, sizeof(buffer), "%Y-%m-%dT%H:%M:%SZ", &utc) ==
        0) {
        return {};
    }
    return buffer;
}

std::string filename_time(std::string_view id) {
    const std::size_t dash = id.find('-');
    if (dash == std::string_view::npos || dash == 0) return {};
    std::uint64_t nanoseconds = 0;
    const auto [end, error] =
        std::from_chars(id.data(), id.data() + dash, nanoseconds);
    if (error != std::errc{} || end != id.data() + dash) return {};
    const std::uint64_t seconds = nanoseconds / 1'000'000'000ULL;
    if (seconds >
        static_cast<std::uint64_t>(std::numeric_limits<std::time_t>::max())) {
        return {};
    }
    return format_utc(static_cast<std::time_t>(seconds));
}

std::string mtime_utc(const std::filesystem::path &path) {
    const auto file_time = std::filesystem::last_write_time(path);
    const auto system_time =
        std::chrono::time_point_cast<std::chrono::system_clock::duration>(
            file_time - std::filesystem::file_time_type::clock::now() +
            std::chrono::system_clock::now());
    return format_utc(std::chrono::system_clock::to_time_t(system_time));
}

void parse_message(std::string raw, InboxItem &item) {
    if (!raw.starts_with("from: ")) {
        item.text = std::move(raw);
        return;
    }
    const std::size_t line_end = raw.find('\n');
    if (line_end == std::string::npos) {
        item.text = std::move(raw);
        return;
    }
    std::size_t value_end = line_end;
    if (value_end != 0 && raw[value_end - 1] == '\r') --value_end;
    std::size_t body = line_end + 1;
    if (body < raw.size() && raw[body] == '\r') ++body;
    if (body >= raw.size() || raw[body] != '\n') {
        item.text = std::move(raw);
        return;
    }
    item.from = raw.substr(6, value_end - 6);
    item.text = raw.substr(body + 1);
}

bool is_missing(const std::error_code &error) {
    return error == std::errc::no_such_file_or_directory;
}

}  // namespace

std::filesystem::path inbox_dir(const std::filesystem::path &folder,
                                std::string_view name) {
    if (name.empty()) return absolute_folder(folder) / ".aos" / "say";
    return detail::paths_for(folder, name).say;
}

std::vector<InboxItem> read_inbox(const std::filesystem::path &folder,
                                  std::string_view name) {
    const std::filesystem::path directory = inbox_dir(folder, name);
    std::error_code error;
    if (!std::filesystem::exists(directory, error)) {
        if (error && !is_missing(error)) {
            throw std::filesystem::filesystem_error("無法檢查信箱", directory,
                                                    error);
        }
        return {};
    }
    if (!std::filesystem::is_directory(directory, error)) {
        if (error) {
            throw std::filesystem::filesystem_error("無法檢查信箱", directory,
                                                    error);
        }
        return {};
    }

    std::vector<std::filesystem::path> files;
    std::filesystem::directory_iterator entry(directory, error);
    const std::filesystem::directory_iterator end;
    while (!error && entry != end) {
        std::error_code type_error;
        if (entry->is_regular_file(type_error) && !type_error &&
            entry->path().extension() == ".md") {
            files.push_back(entry->path());
        }
        entry.increment(error);
    }
    if (error) {
        throw std::filesystem::filesystem_error("無法列出信箱", directory,
                                                error);
    }
    std::sort(files.begin(), files.end(),
              [](const auto &left, const auto &right) {
                  return left.filename().string() < right.filename().string();
              });

    std::vector<InboxItem> items;
    items.reserve(files.size());
    for (const std::filesystem::path &file : files) {
        InboxItem item;
        item.path = file;
        item.id = file.stem().string();
        item.when = filename_time(item.id);
        if (item.when.empty()) item.when = mtime_utc(file);
        parse_message(detail::read_text(file), item);
        items.push_back(std::move(item));
    }
    return items;
}

bool mark_inbox_read(const InboxItem &item, std::string &error) {
    error.clear();
    const std::filesystem::path destination =
        item.path.parent_path().parent_path() / "read" /
        item.path.filename();
    std::error_code filesystem_error;
    std::filesystem::create_directories(destination.parent_path(),
                                        filesystem_error);
    if (filesystem_error) {
        error = "無法建立已讀資料夾：" + filesystem_error.message();
        return false;
    }

    std::filesystem::rename(item.path, destination, filesystem_error);
    if (!filesystem_error) return true;
    if (filesystem_error != std::errc::cross_device_link) {
        error = "無法搬移訊息：" + filesystem_error.message();
        return false;
    }

    filesystem_error.clear();
    std::filesystem::copy_file(item.path, destination,
                               std::filesystem::copy_options::none,
                               filesystem_error);
    if (filesystem_error) {
        error = "無法跨檔案系統複製訊息：" + filesystem_error.message();
        return false;
    }
    std::filesystem::remove(item.path, filesystem_error);
    if (!filesystem_error) return true;

    std::error_code cleanup_error;
    std::filesystem::remove(destination, cleanup_error);
    error = "複製後無法移除未讀訊息：" + filesystem_error.message();
    return false;
}

}  // namespace aos::agent
