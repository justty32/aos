#include <aos/tool.hpp>

#include "internal.hpp"

#include <nlohmann/json.hpp>

#include <algorithm>
#include <cstdlib>
#include <stdexcept>

namespace aos::tool {
namespace {

using Json = nlohmann::json;

std::string required_string(const Json &item, const char *key,
                            const std::filesystem::path &path) {
    if (!item.contains(key) || !item[key].is_string() ||
        item[key].get_ref<const std::string &>().empty()) {
        throw std::runtime_error(path.string() + ": " + key +
                                 " 必須是非空字串");
    }
    return item[key].get<std::string>();
}

std::string optional_string(const Json &item, const char *key,
                            const std::filesystem::path &path) {
    if (!item.contains(key)) return {};
    if (!item[key].is_string()) {
        throw std::runtime_error(path.string() + ": " + key + " 必須是字串");
    }
    return item[key].get<std::string>();
}

void validate_contact(const Contact &contact) {
    if (contact.name.empty()) throw std::runtime_error("聯絡人 name 不可為空");
    if (contact.folder.empty()) throw std::runtime_error("聯絡人 folder 不可為空");
}

}  // namespace

Contact user_contact() {
    const char *home = std::getenv("HOME");
    if (home == nullptr || *home == '\0') {
        return {"~", "", "", "使用者（頂層信箱）"};
    }
    const std::filesystem::path folder =
        std::filesystem::absolute(home).lexically_normal();
    return {"~", folder.string(), "", "使用者（頂層信箱）"};
}

std::vector<Contact> read_contacts(const std::filesystem::path &folder) {
    const std::filesystem::path path = contacts_path(folder);
    if (!std::filesystem::exists(path)) return {};
    Json root;
    try {
        root = Json::parse(detail::read_text(path));
    } catch (const Json::exception &error) {
        throw std::runtime_error(path.string() + ": JSON 無法解析: " +
                                 error.what());
    }
    if (!root.is_array()) {
        throw std::runtime_error(path.string() + ": 頂層必須是 JSON 陣列");
    }
    std::vector<Contact> contacts;
    for (const Json &item : root) {
        if (!item.is_object()) {
            throw std::runtime_error(path.string() + ": 聯絡人必須是 object");
        }
        contacts.push_back({required_string(item, "name", path),
                            required_string(item, "folder", path),
                            optional_string(item, "agent", path),
                            optional_string(item, "note", path)});
    }
    return contacts;
}

void write_contacts(const std::filesystem::path &folder,
                    const std::vector<Contact> &contacts) {
    Json root = Json::array();
    for (const Contact &contact : contacts) {
        validate_contact(contact);
        Json item = {{"name", contact.name}, {"folder", contact.folder}};
        if (!contact.agent.empty()) item["agent"] = contact.agent;
        if (!contact.note.empty()) item["note"] = contact.note;
        root.push_back(std::move(item));
    }
    detail::atomic_write(contacts_path(folder), root.dump(2) + "\n");
}

void add_contact(const std::filesystem::path &folder, const Contact &contact) {
    validate_contact(contact);
    std::vector<Contact> contacts = read_contacts(folder);
    const auto found = std::find_if(
        contacts.begin(), contacts.end(), [&](const Contact &item) {
            return item.name == contact.name;
        });
    if (found == contacts.end()) contacts.push_back(contact);
    else *found = contact;
    write_contacts(folder, contacts);
}

bool remove_contact(const std::filesystem::path &folder,
                    std::string_view name) {
    std::vector<Contact> contacts = read_contacts(folder);
    const auto found = std::find_if(
        contacts.begin(), contacts.end(), [&](const Contact &item) {
            return item.name == name;
        });
    if (found == contacts.end()) return false;
    contacts.erase(found);
    write_contacts(folder, contacts);
    return true;
}

std::optional<Contact> find_contact(const std::filesystem::path &folder,
                                    std::string_view name) {
    const std::vector<Contact> contacts = read_contacts(folder);
    const auto found = std::find_if(
        contacts.begin(), contacts.end(), [&](const Contact &item) {
            return item.name == name;
        });
    if (found == contacts.end()) {
        if (name != "~") return std::nullopt;
        Contact contact = user_contact();
        if (contact.folder.empty()) return std::nullopt;
        return contact;
    }
    return *found;
}

}  // namespace aos::tool
