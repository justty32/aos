#include "internal.hpp"

#include "cli_common.hpp"

#include <aos/tool.hpp>
#include <nlohmann/json.hpp>

#include <algorithm>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <system_error>
#include <vector>

namespace aos::tool::detail {
namespace {

using Json = nlohmann::json;

std::string read_file(const std::filesystem::path &path) {
    std::ifstream input(path, std::ios::binary);
    if (!input) throw std::runtime_error("無法讀取 " + path.string());
    return {std::istreambuf_iterator<char>(input),
            std::istreambuf_iterator<char>()};
}

std::uint64_t count_messages(const std::filesystem::path &directory) {
    if (!std::filesystem::is_directory(directory)) return 0;
    std::uint64_t count = 0;
    for (const auto &entry : std::filesystem::directory_iterator(directory)) {
        if (entry.is_regular_file() && entry.path().extension() == ".md") {
            ++count;
        }
    }
    return count;
}

std::string one_line(std::string text) {
    std::replace(text.begin(), text.end(), '\n', ' ');
    std::replace(text.begin(), text.end(), '\r', ' ');
    return text;
}

std::string truncate_characters(std::string text, std::size_t limit) {
    std::size_t characters = 0;
    std::size_t end = 0;
    while (end < text.size() && characters < limit) {
        ++end;
        while (end < text.size() &&
               (static_cast<unsigned char>(text[end]) & 0xc0U) == 0x80U) {
            ++end;
        }
        ++characters;
    }
    if (end == text.size()) return text;
    text.resize(end);
    text += "…";
    return text;
}

std::optional<std::string>
only_agent(const std::filesystem::path &aos,
           const std::optional<std::string> &requested) {
    const std::filesystem::path agents = aos / "agents";
    if (requested) {
        if (std::filesystem::is_directory(agents / *requested)) {
            return requested;
        }
        return std::nullopt;
    }
    if (!std::filesystem::is_directory(agents)) return std::nullopt;
    std::optional<std::string> found;
    for (const auto &entry : std::filesystem::directory_iterator(agents)) {
        if (!entry.is_directory()) continue;
        if (found) return std::nullopt;
        found = entry.path().filename().string();
    }
    return found;
}

ContactStatusRow world_row(std::string name,
                           const std::filesystem::path &folder,
                           const std::optional<std::string> &requested) {
    ContactStatusRow row;
    row.name = std::move(name);
    try {
        const std::filesystem::path aos = folder / ".aos";
        if (!std::filesystem::is_directory(aos)) {
            row.status = "（找不到 .aos）";
            return row;
        }
        const std::optional<std::string> agent = only_agent(aos, requested);
        if (!agent) {
            row.status = "（沒有 agent）";
            return row;
        }
        row.agent = *agent;
        const std::filesystem::path status_path =
            aos / "agents" / *agent / "status.json";
        Json status;
        try {
            status = Json::parse(read_file(status_path));
            if (!status.is_object() || !status.contains("status") ||
                !status["status"].is_string() || !status.contains("turn") ||
                !status["turn"].is_number_unsigned()) {
                throw std::runtime_error("status 欄位格式錯誤");
            }
        } catch (const std::exception &) {
            row.agent.clear();
            row.status = "（status.json 讀不到）";
            return row;
        }
        row.status = status["status"].get<std::string>();
        row.turn = status["turn"].get<std::uint64_t>();
        row.unread = count_messages(aos / "agents" / *agent / "say");
        if (*row.unread > 0 && row.status == "idle") row.status = "pending";
        if (status.contains("last_error") && status["last_error"].is_string()) {
            row.last_error = truncate_characters(
                one_line(status["last_error"].get<std::string>()), 40);
        }
        return row;
    } catch (const std::exception &) {
        row.agent.clear();
        row.status = "（status.json 讀不到）";
        row.turn.reset();
        row.unread.reset();
        row.last_error.clear();
        return row;
    }
}

std::vector<Contact> contacts_with_user(const std::filesystem::path &root) {
    std::vector<Contact> contacts = read_contacts(root);
    const bool has_user =
        std::any_of(contacts.begin(), contacts.end(),
                    [](const Contact &contact) { return contact.name == "~"; });
    if (!has_user) {
        Contact user = user_contact();
        if (!user.folder.empty()) contacts.insert(contacts.begin(), user);
    }
    return contacts;
}

std::string optional_number(const std::optional<std::uint64_t> &value,
                            std::string_view missing) {
    return value ? std::to_string(*value) : std::string(missing);
}

Json row_json(const ContactStatusRow &row) {
    return {{"name", row.name},
            {"agent", row.agent},
            {"status", row.status},
            {"turn", row.turn ? Json(*row.turn) : Json(nullptr)},
            {"unread", row.unread ? Json(*row.unread) : Json(nullptr)},
            {"last_error", row.last_error}};
}

}  // namespace

std::vector<ContactStatusRow>
contact_status_rows(const std::filesystem::path &given_root) {
    const std::filesystem::path root = resolve_folder(given_root);
    std::vector<ContactStatusRow> rows;
    rows.push_back(world_row(".", root, std::nullopt));
    for (const Contact &contact : contacts_with_user(root)) {
        const std::filesystem::path folder =
            (root / contact.folder).lexically_normal();
        if (contact.name == "~") {
            ContactStatusRow user;
            user.name = "~";
            user.agent = "-";
            user.status = "-";
            user.unread = count_messages(folder / ".aos" / "say");
            rows.push_back(std::move(user));
            continue;
        }
        const std::optional<std::string> requested =
            contact.agent.empty() ? std::nullopt
                                  : std::optional<std::string>(contact.agent);
        rows.push_back(world_row(contact.name, folder, requested));
    }
    return rows;
}

int contact_status_command(const char *program,
                           const std::vector<std::string> &words) {
    std::filesystem::path root;
    bool json = false;
    for (std::size_t index = 1; index < words.size(); ++index) {
        if (words[index] == "--json") {
            json = true;
        } else if (words[index] == "--folder-root" &&
                   index + 1 < words.size()) {
            root = words[++index];
        } else {
            std::fprintf(stderr,
                         "usage: %s status [--folder-root F] [--json]\n",
                         program);
            return 2;
        }
    }

    const std::vector<ContactStatusRow> rows = contact_status_rows(root);
    if (json) {
        Json output = Json::array();
        for (const ContactStatusRow &row : rows)
            output.push_back(row_json(row));
        std::printf("%s\n", output.dump(2).c_str());
        return 0;
    }

    std::vector<std::vector<std::string>> table;
    for (const ContactStatusRow &row : rows) {
        const bool user = row.name == "~";
        table.push_back({row.name, row.agent, row.status,
                         optional_number(row.turn, user ? "-" : ""),
                         optional_number(row.unread, ""), row.last_error});
    }
    cli::print_table(
        {"NAME", "AGENT", "STATUS", "TURN", "UNREAD", "LAST_ERROR"}, table);
    return 0;
}

}  // namespace aos::tool::detail
