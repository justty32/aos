#include "internal.hpp"

#include <nlohmann/json.hpp>

#include <chrono>
#include <cstdio>
#include <fstream>
#include <iomanip>
#include <iterator>
#include <sstream>
#include <stdexcept>
#include <ctime>

namespace aos::agent {
namespace {

using Json = nlohmann::json;

Json parse_file(const std::filesystem::path &path) {
    try {
        return Json::parse(detail::read_text(path));
    } catch (const Json::exception &error) {
        throw std::runtime_error(path.string() + " JSON 無法解析: " +
                                 error.what());
    }
}

std::string require_string(const Json &item, const char *key,
                           const std::filesystem::path &path) {
    if (!item.contains(key) || !item[key].is_string()) {
        throw std::runtime_error(path.string() + " 缺少字串欄位 " + key);
    }
    return item[key].get<std::string>();
}

std::string now_iso8601() {
    const auto now = std::chrono::system_clock::now();
    const std::time_t value = std::chrono::system_clock::to_time_t(now);
    std::tm utc{};
    gmtime_r(&value, &utc);
    std::ostringstream out;
    out << std::put_time(&utc, "%Y-%m-%dT%H:%M:%SZ");
    return out.str();
}

std::string render_log_journal(std::string_view journal,
                               const std::filesystem::path &path) {
    std::istringstream input{std::string(journal)};
    std::string rendered;
    std::string line;
    std::size_t line_number = 0;
    while (std::getline(input, line)) {
        ++line_number;
        if (line.empty()) {
            throw std::runtime_error(path.string() + " 第 " +
                                     std::to_string(line_number) +
                                     " 行不是 JSON 物件");
        }

        Json entry;
        try {
            entry = Json::parse(line);
        } catch (const Json::exception &error) {
            throw std::runtime_error(path.string() + " 第 " +
                                     std::to_string(line_number) +
                                     " 行 JSON 無法解析: " + error.what());
        }
        if (!entry.is_object() || !entry.contains("turn") ||
            !entry["turn"].is_number_unsigned()) {
            throw std::runtime_error(path.string() + " 第 " +
                                     std::to_string(line_number) +
                                     " 行缺少 turn");
        }
        const std::string role = require_string(entry, "role", path);
        const std::string content = require_string(entry, "content", path);
        if (role == "note") {
            rendered += content;
            if (rendered.empty() || rendered.back() != '\n') {
                rendered.push_back('\n');
            }
            continue;
        }
        if (role != "user" && role != "assistant" && role != "tool") {
            throw std::runtime_error(path.string() + " 第 " +
                                     std::to_string(line_number) +
                                     " 行的 role 無效");
        }
        rendered += "## turn " +
                    std::to_string(entry["turn"].get<std::uint64_t>()) +
                    " " + role + "\n";
        rendered += content;
        if (rendered.empty() || rendered.back() != '\n') {
            rendered.push_back('\n');
        }
        rendered.push_back('\n');
    }
    return rendered;
}

void append_journal_entry(const aos::agent::detail::Paths &paths,
                          std::uint64_t turn, std::string_view role,
                          std::string_view content) {
    const std::filesystem::path journal_path = paths.log_journal();
    std::string journal;
    if (std::filesystem::exists(journal_path)) {
        journal = aos::agent::detail::read_text(journal_path);
    }
    const Json entry = {{"turn", turn},
                        {"role", std::string(role)},
                        {"content", std::string(content)}};
    journal += entry.dump() + "\n";
    aos::agent::detail::atomic_write(journal_path, journal);
    aos::agent::detail::atomic_write(
        paths.log, render_log_journal(journal, journal_path));
}

}  // namespace

namespace detail {

std::string read_text(const std::filesystem::path &path) {
    std::ifstream input(path, std::ios::binary);
    if (!input) throw std::runtime_error("無法讀取 " + path.string());
    return {std::istreambuf_iterator<char>(input),
            std::istreambuf_iterator<char>()};
}

void atomic_write(const std::filesystem::path &path, std::string_view text) {
    std::filesystem::create_directories(path.parent_path());
    const std::filesystem::path temporary = path.string() + ".tmp";
    {
        std::ofstream output(temporary, std::ios::binary | std::ios::trunc);
        if (!output) throw std::runtime_error("無法寫入 " + temporary.string());
        output.write(text.data(), static_cast<std::streamsize>(text.size()));
        output.close();
        if (!output) throw std::runtime_error("寫入失敗 " + temporary.string());
    }
    std::filesystem::rename(temporary, path);
}

std::string message_body(std::string_view from, std::string_view text) {
    if (from.empty()) return std::string(text);
    std::string body = "from: ";
    body.append(from);
    body += "\n\n";
    body.append(text);
    return body;
}

void append_log(const Paths &paths, std::uint64_t turn,
                std::string_view role, std::string_view content) {
    append_journal_entry(paths, turn, role, content);
}

void append_note(const Paths &paths, std::uint64_t turn,
                 std::string_view text) {
    append_journal_entry(paths, turn, "note", text);
}

void write_history(const Paths &paths, const std::vector<Message> &messages) {
    Json root = {{"messages", Json::array()}};
    for (const Message &message : messages) {
        root["messages"].push_back(
            {{"role", message.role}, {"content", message.content}});
    }
    atomic_write(paths.history, root.dump(2) + "\n");
}

std::uint64_t count_unread(const Paths &paths) {
    if (!std::filesystem::is_directory(paths.say)) return 0;

    std::uint64_t unread = 0;
    for (const auto &entry : std::filesystem::directory_iterator(paths.say)) {
        if (entry.is_regular_file() && entry.path().extension() == ".md") {
            ++unread;
        }
    }
    return unread;
}

void write_status(const Paths &paths, std::string_view status,
                  std::string_view detail, std::uint64_t turn,
                  std::string_view last_error) {
    Json root = {{"status", status},
                 {"detail", detail},
                 {"updated_at", now_iso8601()},
                 {"turn", turn},
                 {"unread", count_unread(paths)}};
    if (!last_error.empty()) root["last_error"] = last_error;
    atomic_write(paths.status, root.dump(2) + "\n");
}

void write_pending(const Paths &paths, const Pending &pending) {
    Json root = {{"turn", pending.turn}, {"calls", Json::array()}};
    for (const PendingCall &call : pending.calls) {
        Json args = nullptr;
        try {
            args = Json::parse(call.args_json);
        } catch (const Json::exception &) {
        }
        root["calls"].push_back(
            {{"id", call.id}, {"tool", call.tool}, {"args", std::move(args)}});
    }
    atomic_write(paths.pending, root.dump(2) + "\n");
}

}  // namespace detail

std::vector<Message> read_history(const std::filesystem::path &folder,
                                  std::string_view name) {
    const detail::Paths paths = detail::paths_for(folder, name);
    const Json root = parse_file(paths.history);
    if (!root.contains("messages") || !root["messages"].is_array()) {
        throw std::runtime_error(paths.history.string() +
                                 " 缺少 messages 陣列");
    }
    std::vector<Message> messages;
    for (const Json &item : root["messages"]) {
        if (!item.is_object()) throw std::runtime_error("history 訊息必須是物件");
        messages.push_back({require_string(item, "role", paths.history),
                            require_string(item, "content", paths.history)});
    }
    return messages;
}

Status read_status(const std::filesystem::path &folder,
                   std::string_view name) {
    const detail::Paths paths = detail::paths_for(folder, name);
    const Json root = parse_file(paths.status);
    if (!root.contains("turn") || !root["turn"].is_number_unsigned()) {
        throw std::runtime_error(paths.status.string() + " 缺少 turn");
    }
    Status status;
    status.status = require_string(root, "status", paths.status);
    status.detail = require_string(root, "detail", paths.status);
    status.updated_at = require_string(root, "updated_at", paths.status);
    status.turn = root["turn"].get<std::uint64_t>();
    if (root.contains("unread") && root["unread"].is_number_unsigned()) {
        status.unread = root["unread"].get<std::uint64_t>();
    }
    if (root.contains("last_error") && root["last_error"].is_string()) {
        status.last_error = root["last_error"].get<std::string>();
    }
    return status;
}

std::uint64_t count_unread(const std::filesystem::path &folder,
                           std::string_view name) {
    return detail::count_unread(detail::paths_for(folder, name));
}

std::string read_status_file(const std::filesystem::path &folder,
                             std::string_view name) {
    return detail::read_text(detail::paths_for(folder, name).status);
}

Pending read_pending(const std::filesystem::path &folder,
                     std::string_view name) {
    const detail::Paths paths = detail::paths_for(folder, name);
    const Json root = parse_file(paths.pending);
    if (!root.contains("turn") || !root["turn"].is_number_unsigned() ||
        !root.contains("calls") || !root["calls"].is_array()) {
        throw std::runtime_error(paths.pending.string() + " 格式錯誤");
    }
    Pending pending;
    pending.turn = root["turn"].get<std::uint64_t>();
    for (const Json &item : root["calls"]) {
        if (!item.is_object()) throw std::runtime_error("pending call 必須是物件");
        if (!item.contains("args")) {
            throw std::runtime_error(paths.pending.string() + " 缺少欄位 args");
        }
        pending.calls.push_back({require_string(item, "id", paths.pending),
                                 require_string(item, "tool", paths.pending),
                                 item["args"].dump()});
    }
    return pending;
}

std::string read_log(const std::filesystem::path &folder,
                     std::string_view name) {
    const detail::Paths paths = detail::paths_for(folder, name);
    if (!std::filesystem::exists(paths.log_journal())) {
        return detail::read_text(paths.log);
    }

    const std::string rendered =
        render_log_journal(detail::read_text(paths.log_journal()),
                           paths.log_journal());
    const bool log_exists = std::filesystem::exists(paths.log);
    const std::string current =
        log_exists ? detail::read_text(paths.log) : std::string{};
    if (!log_exists || current != rendered) {
        std::fprintf(stderr,
                     "aos: %s 與稽核紀錄不符（有人手動改過），已從 "
                     "log.jsonl 還原\n",
                     paths.log.string().c_str());
        detail::atomic_write(paths.log, rendered);
    }
    return rendered;
}

}  // namespace aos::agent
