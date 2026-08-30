#include "internal.hpp"

#include <aos/loop.hpp>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdlib>
#include <stdexcept>
#include <system_error>
#include <unistd.h>
#include <vector>

namespace aos::agent {
namespace {

std::filesystem::path user_aos_folder() {
    return user_folder() / ".aos";
}

std::string message_filename() {
    static std::atomic<std::uint64_t> sequence{0};
    const auto stamp = std::chrono::duration_cast<std::chrono::nanoseconds>(
                           std::chrono::system_clock::now().time_since_epoch())
                           .count();
    return std::to_string(stamp) + "-" + std::to_string(getpid()) + "-" +
           std::to_string(sequence++) + ".md";
}

}  // namespace

std::filesystem::path user_folder() {
    const char *home = std::getenv("HOME");
    if (home == nullptr || *home == '\0') {
        throw std::runtime_error("HOME 沒有設定");
    }
    return absolute_folder(home);
}

bool is_user_folder(const std::filesystem::path &folder) {
    return !folder.empty() && absolute_folder(folder) == user_folder();
}

std::filesystem::path say_from() {
    const char *folder = std::getenv("AOS_FOLDER");
    if (folder != nullptr && *folder != '\0') return absolute_folder(folder);

    std::error_code error;
    const std::filesystem::path cwd = std::filesystem::current_path(error);
    if (!error) {
        const std::string found = aos::loop::find_folder(cwd.string());
        if (!found.empty()) return absolute_folder(found);
    }
    return user_folder();
}

void ensure_user_layout() {
    const std::filesystem::path aos = user_aos_folder();
    std::filesystem::create_directories(aos / "say");
    const std::filesystem::path log = aos / "log.md";
    if (!std::filesystem::exists(log)) detail::atomic_write(log, "");
}

void say_to_user(std::string_view text, std::string_view from) {
    ensure_user_layout();
    detail::atomic_write(user_aos_folder() / "say" / message_filename(),
                         detail::message_body(from, text));
}

std::size_t drain_user_say() {
    ensure_user_layout();
    const std::filesystem::path aos = user_aos_folder();
    const std::filesystem::path say = aos / "say";
    std::vector<std::filesystem::path> messages;
    for (const auto &entry : std::filesystem::directory_iterator(say)) {
        if (entry.is_regular_file() && entry.path().extension() == ".md") {
            messages.push_back(entry.path());
        }
    }
    std::sort(messages.begin(), messages.end());
    if (messages.empty()) return 0;

    std::string log = read_user_log();
    for (const std::filesystem::path &message : messages) {
        log += detail::read_text(message);
        if (log.empty() || log.back() != '\n') log.push_back('\n');
        log.push_back('\n');
    }
    detail::atomic_write(aos / "log.md", log);
    for (const std::filesystem::path &message : messages) {
        std::filesystem::remove(message);
    }
    return messages.size();
}

std::string read_user_log() {
    const std::filesystem::path log = user_aos_folder() / "log.md";
    if (!std::filesystem::exists(log)) return {};
    return detail::read_text(log);
}

}  // namespace aos::agent
