#include "internal.hpp"

#include <nlohmann/json.hpp>

#include <chrono>
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

void append_log(const Paths &paths, std::uint64_t turn,
                std::string_view role, std::string_view content) {
    std::string log;
    if (std::filesystem::exists(paths.log)) log = read_text(paths.log);
    log += "## turn " + std::to_string(turn) + " " + std::string(role) + "\n";
    log.append(content);
    if (log.empty() || log.back() != '\n') log.push_back('\n');
    log.push_back('\n');
    atomic_write(paths.log, log);
}

void append_note(const Paths &paths, std::string_view text) {
    std::string log;
    if (std::filesystem::exists(paths.log)) log = read_text(paths.log);
    log.append(text);
    if (log.empty() || log.back() != '\n') log.push_back('\n');
    atomic_write(paths.log, log);
}

void write_history(const Paths &paths, const std::vector<Message> &messages) {
    Json root = {{"messages", Json::array()}};
    for (const Message &message : messages) {
        root["messages"].push_back(
            {{"role", message.role}, {"content", message.content}});
    }
    atomic_write(paths.history, root.dump(2) + "\n");
}

void write_status(const Paths &paths, std::string_view status,
                  std::string_view detail, std::uint64_t turn) {
    const Json root = {{"status", status},
                       {"detail", detail},
                       {"updated_at", now_iso8601()},
                       {"turn", turn}};
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
    return {require_string(root, "status", paths.status),
            require_string(root, "detail", paths.status),
            require_string(root, "updated_at", paths.status),
            root["turn"].get<std::uint64_t>()};
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
    return detail::read_text(detail::paths_for(folder, name).log);
}

}  // namespace aos::agent
