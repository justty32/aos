#include <aos/tool.hpp>

#include "cli_common.hpp"
#include "internal.hpp"

#include <algorithm>
#include <cstdio>
#include <exception>
#include <filesystem>
#include <string>
#include <string_view>
#include <vector>

namespace {

using aos::tool::Contact;

int usage(const char *program, FILE *stream = stderr, int result = 2) {
    std::fprintf(
        stream,
        "usage: %s add <name> <folder> [--agent A] [--note TEXT] "
        "[--folder-root F]\n"
        "       %s ls [--folder-root F] [--json]\n"
        "       %s rm <name> [--folder-root F]\n"
        "       %s status [--folder-root F] [--json]\n"
        "\n"
        "  add                    add or update a contact\n"
        "    --agent A            name of the agent on the other side\n"
        "    --note TEXT          attach a note\n"
        "    --folder-root F      world that owns the contact list\n"
        "  ls                     list contacts; accepts --folder-root F, --json\n"
        "  rm                     remove a contact; accepts --folder-root F\n"
        "  status                 show status, turn and unread count for self and each contact\n"
        "  -h, --help             show this usage\n",
        program, program, program, program);
    return result;
}

int add(const char *program, const std::vector<std::string> &words) {
    if (words.size() < 3) return usage(program);
    Contact contact{words[1], words[2], {}, {}};
    std::filesystem::path root;
    for (std::size_t index = 3; index < words.size();) {
        if (index + 1 >= words.size()) return usage(program);
        if (words[index] == "--agent") contact.agent = words[index + 1];
        else if (words[index] == "--note") contact.note = words[index + 1];
        else if (words[index] == "--folder-root") root = words[index + 1];
        else return usage(program);
        index += 2;
    }
    const bool existed = aos::tool::find_contact(root, contact.name).has_value();
    aos::tool::add_contact(root, contact);
    if (existed) {
        std::printf("updated contact %s\n", contact.name.c_str());
    } else {
        std::printf("added contact %s -> %s\n", contact.name.c_str(),
                    contact.folder.c_str());
    }
    return 0;
}

void print_json(const std::vector<Contact> &contacts) {
    std::puts("[");
    for (std::size_t index = 0; index < contacts.size(); ++index) {
        const Contact &contact = contacts[index];
        std::string item = "  {\n    \"name\": " +
                           aos::tool::cli::json_escape(contact.name) +
                           ",\n    \"folder\": " +
                           aos::tool::cli::json_escape(contact.folder);
        if (!contact.agent.empty()) {
            item += ",\n    \"agent\": " +
                    aos::tool::cli::json_escape(contact.agent);
        }
        if (!contact.note.empty()) {
            item += ",\n    \"note\": " +
                    aos::tool::cli::json_escape(contact.note);
        }
        item += "\n  }";
        if (index + 1 != contacts.size()) item += ',';
        std::puts(item.c_str());
    }
    std::puts("]");
}

int list(const char *program, const std::vector<std::string> &words) {
    std::filesystem::path root;
    bool json = false;
    for (std::size_t index = 1; index < words.size(); ++index) {
        if (words[index] == "--json") json = true;
        else if (words[index] == "--folder-root" && index + 1 < words.size()) {
            root = words[++index];
        } else {
            return usage(program);
        }
    }
    std::vector<Contact> contacts = aos::tool::read_contacts(root);
    const bool has_user = std::any_of(
        contacts.begin(), contacts.end(),
        [](const Contact &contact) { return contact.name == "~"; });
    if (!has_user) {
        Contact user = aos::tool::user_contact();
        if (!user.folder.empty()) contacts.insert(contacts.begin(), user);
    }
    if (json) {
        print_json(contacts);
        return 0;
    }
    if (contacts.empty()) {
        std::puts("(no contacts)");
        return 0;
    }
    std::vector<std::vector<std::string>> rows;
    for (const Contact &contact : contacts) {
        rows.push_back(
            {contact.name, contact.folder, contact.agent, contact.note});
    }
    aos::tool::cli::print_table({"NAME", "FOLDER", "AGENT", "NOTE"}, rows);
    return 0;
}

int remove(const char *program, const std::vector<std::string> &words) {
    if (words.size() < 2) return usage(program);
    const std::string name = words[1];
    std::filesystem::path root;
    std::size_t index = 2;
    while (index < words.size()) {
        if (words[index] != "--folder-root" || index + 1 >= words.size()) {
            return usage(program);
        }
        root = words[index + 1];
        index += 2;
    }
    if (!aos::tool::remove_contact(root, name)) {
        std::fprintf(stderr, "aos contact: no contact named %s\n", name.c_str());
        return 1;
    }
    std::printf("removed contact %s\n", name.c_str());
    return 0;
}

int dispatch(int argc, char *argv[]) {
    const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
                              ? argv[0]
                              : "aos contact";
    for (int index = 1; argv != nullptr && index < argc; ++index) {
        if (argv[index] != nullptr &&
            (std::string_view(argv[index]) == "--help" ||
             std::string_view(argv[index]) == "-h")) {
            return usage(program, stdout, 0);
        }
    }
    std::vector<std::string> words;
    for (int index = 1; index < argc; ++index) {
        if (argv == nullptr || argv[index] == nullptr) return usage(program);
        words.emplace_back(argv[index]);
    }
    if (words.empty()) return usage(program);
    if (words[0] == "add") return add(program, words);
    if (words[0] == "ls") return list(program, words);
    if (words[0] == "rm") return remove(program, words);
    if (words[0] == "status") {
        return aos::tool::detail::contact_status_command(program, words);
    }
    return usage(program);
}

}  // namespace

extern "C" int aos_contact_cli_main(int argc, char *argv[]) {
    try {
        return dispatch(argc, argv);
    } catch (const std::exception &error) {
        const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
                                  ? argv[0]
                                  : "aos contact";
        std::fprintf(stderr, "%s: %s\n", program, error.what());
        return 1;
    }
}
