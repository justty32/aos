#include <aos/agent.hpp>

#include <nlohmann/json.hpp>

#include <algorithm>
#include <cstdio>
#include <exception>
#include <filesystem>
#include <optional>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace {

int usage(const char *program) {
    std::fprintf(stderr,
                 "usage: %s ls [--json]\n"
                 "       %s read [<id>] [--all] [--keep]\n",
                 program, program);
    return 2;
}

std::string display_from(std::string_view from) {
    if (from.empty()) return "-";
    if (std::filesystem::path(from).lexically_normal() ==
        aos::agent::user_folder()) {
        return "~";
    }
    return std::string(from);
}

std::string first_line(std::string_view text) {
    const std::size_t end = text.find_first_of("\r\n");
    return std::string(text.substr(0, end));
}

std::size_t utf8_width(unsigned char lead) {
    if ((lead & 0x80U) == 0) return 1;
    if ((lead & 0xE0U) == 0xC0U) return 2;
    if ((lead & 0xF0U) == 0xE0U) return 3;
    if ((lead & 0xF8U) == 0xF0U) return 4;
    return 1;
}

std::string truncate_utf8(std::string text, std::size_t limit) {
    std::size_t offset = 0;
    std::size_t characters = 0;
    while (offset < text.size() && characters < limit) {
        const std::size_t width = utf8_width(
            static_cast<unsigned char>(text[offset]));
        offset += std::min(width, text.size() - offset);
        ++characters;
    }
    if (offset == text.size()) return text;
    text.resize(offset);
    text += "…";
    return text;
}

std::pair<std::filesystem::path, std::string> current_inbox() {
    const std::filesystem::path folder = aos::agent::resolve_folder();
    if (aos::agent::is_user_folder(folder)) return {folder, {}};
    return {folder, aos::agent::resolve_name(folder)};
}

int list_inbox(int argc, char *argv[], const char *program) {
    const bool json = argc == 3 && std::string_view(argv[2]) == "--json";
    if (argc != 2 && !json) return usage(program);
    const auto [folder, name] = current_inbox();
    const std::vector<aos::agent::InboxItem> items =
        aos::agent::read_inbox(folder, name);
    if (json) {
        nlohmann::ordered_json output = nlohmann::ordered_json::array();
        for (const aos::agent::InboxItem &item : items) {
            output.push_back({{"id", item.id},
                              {"from", item.from},
                              {"when", item.when},
                              {"text", item.text}});
        }
        std::printf("%s\n", output.dump(2).c_str());
        return 0;
    }
    if (items.empty()) {
        std::fputs("（信箱是空的）\n", stdout);
        return 0;
    }
    std::size_t id_width = 2;
    std::size_t from_width = 4;
    std::size_t when_width = 4;
    for (const aos::agent::InboxItem &item : items) {
        id_width = std::max(id_width, item.id.size());
        from_width = std::max(from_width, display_from(item.from).size());
        when_width = std::max(when_width, item.when.size());
    }
    std::printf("%-*s %-*s %-*s %s\n", static_cast<int>(id_width), "ID",
                static_cast<int>(from_width), "FROM",
                static_cast<int>(when_width), "WHEN", "訊息");
    for (const aos::agent::InboxItem &item : items) {
        const std::string from = display_from(item.from);
        const std::string preview = truncate_utf8(first_line(item.text), 40);
        std::printf("%-*s %-*s %-*s %s\n", static_cast<int>(id_width),
                    item.id.c_str(), static_cast<int>(from_width), from.c_str(),
                    static_cast<int>(when_width), item.when.c_str(),
                    preview.c_str());
    }
    return 0;
}

std::vector<aos::agent::InboxItem> select_items(
    const std::vector<aos::agent::InboxItem> &items,
    const std::optional<std::string> &id, bool all) {
    if (all) return items;
    if (!id) return items.empty() ? std::vector<aos::agent::InboxItem>{}
                                  : std::vector{items.front()};
    for (const aos::agent::InboxItem &item : items) {
        if (item.id == *id) return {item};
    }
    std::vector<aos::agent::InboxItem> matches;
    for (const aos::agent::InboxItem &item : items) {
        if (item.id.starts_with(*id)) matches.push_back(item);
    }
    return matches.size() == 1 ? matches
                               : std::vector<aos::agent::InboxItem>{};
}

void print_item(const aos::agent::InboxItem &item, bool first) {
    if (!first) std::fputc('\n', stdout);
    const std::string from = item.from.empty() ? "-" : item.from;
    std::printf("--- %s  from %s  %s\n", item.id.c_str(), from.c_str(),
                item.when.c_str());
    if (!item.text.empty()) {
        std::fwrite(item.text.data(), 1, item.text.size(), stdout);
    }
    if (item.text.empty() || item.text.back() != '\n') std::fputc('\n', stdout);
}

int read_messages(int argc, char *argv[], const char *program) {
    bool all = false;
    bool keep = false;
    std::optional<std::string> id;
    for (int index = 2; index < argc; ++index) {
        const std::string_view argument = argv[index];
        if (argument == "--all" && !all) all = true;
        else if (argument == "--keep" && !keep) keep = true;
        else if (!argument.starts_with("--") && !id) id = argument;
        else return usage(program);
    }
    if (all && id) return usage(program);

    const auto [folder, name] = current_inbox();
    const std::vector<aos::agent::InboxItem> inbox =
        aos::agent::read_inbox(folder, name);
    if (inbox.empty()) {
        std::fputs("（沒有未讀訊息）\n", stdout);
        return 0;
    }
    const std::vector<aos::agent::InboxItem> selected =
        select_items(inbox, id, all);
    if (selected.empty()) {
        std::fprintf(stderr,
                     "aos inbox: 沒有這封訊息 %s（用 aos inbox ls 看有哪些）\n",
                     id ? id->c_str() : "");
        return 1;
    }

    for (std::size_t index = 0; index < selected.size(); ++index) {
        print_item(selected[index], index == 0);
    }
    std::fflush(stdout);
    if (keep) return 0;

    std::size_t marked = 0;
    bool failed = false;
    for (const aos::agent::InboxItem &item : selected) {
        std::string error;
        if (aos::agent::mark_inbox_read(item, error)) {
            ++marked;
        } else {
            failed = true;
            std::fprintf(stderr, "aos inbox: %s 無法標為已讀：%s\n",
                         item.id.c_str(), error.c_str());
        }
    }
    if (marked != 0) {
        std::fprintf(stderr,
                     "（已標為已讀，agent 不會再回覆這 %zu 封；要保留請用 "
                     "--keep）\n",
                     marked);
    }
    return failed ? 1 : 0;
}

int dispatch(int argc, char *argv[]) {
    const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
                              ? argv[0]
                              : "aos inbox";
    if (argc < 2 || argv == nullptr || argv[1] == nullptr) {
        return usage(program);
    }
    const std::string_view command = argv[1];
    if (command == "ls") return list_inbox(argc, argv, program);
    if (command == "read") return read_messages(argc, argv, program);
    return usage(program);
}

}  // namespace

extern "C" int aos_inbox_cli_main(int argc, char *argv[]) {
    try {
        return dispatch(argc, argv);
    } catch (const std::exception &error) {
        std::fprintf(stderr, "aos inbox: %s\n", error.what());
        return 1;
    }
}
