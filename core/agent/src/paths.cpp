#include "internal.hpp"

#include <aos/loop.hpp>

#include <stdexcept>
#include <vector>

namespace aos::agent {

std::filesystem::path absolute_folder(const std::filesystem::path &folder) {
    if (folder.empty()) throw std::invalid_argument("folder 不可為空");
    return std::filesystem::absolute(folder).lexically_normal();
}

std::filesystem::path resolve_folder(const std::filesystem::path &given) {
    if (!given.empty()) return absolute_folder(given);
    return absolute_folder(aos::loop::current_folder());
}

std::string resolve_name(const std::filesystem::path &folder,
                         std::string_view given) {
    if (!given.empty()) {
        detail::validate_name(given);
        return std::string(given);
    }

    const std::filesystem::path agents =
        absolute_folder(folder) / ".aos" / "agents";
    std::vector<std::string> names;
    if (std::filesystem::is_directory(agents)) {
        for (const auto &entry : std::filesystem::directory_iterator(agents)) {
            if (entry.is_directory()) {
                names.push_back(entry.path().filename().string());
            }
        }
    }
    if (names.empty()) {
        throw std::runtime_error("這個資料夾還沒有 agent；請先跑 aos agent init");
    }
    if (names.size() != 1) {
        throw std::runtime_error("這個資料夾有不只一隻 agent");
    }
    return names.front();
}

namespace detail {

void validate_name(std::string_view name) {
    if (name.empty() || name == "." || name == ".." ||
        name.find('/') != std::string_view::npos ||
        name.find('\\') != std::string_view::npos) {
        throw std::invalid_argument("agent 名稱不可為空或包含路徑分隔符");
    }
}

Paths paths_for(const std::filesystem::path &folder, std::string_view name) {
    validate_name(name);
    Paths paths;
    paths.folder = absolute_folder(folder);
    paths.aos = paths.folder / ".aos";
    paths.inbox = paths.aos / "inbox";
    paths.every = paths.aos / "every";
    paths.agent = paths.aos / "agents" / std::string(name);
    paths.persona = paths.agent / "persona.md";
    paths.history = paths.agent / "history.json";
    paths.status = paths.agent / "status.json";
    paths.say = paths.agent / "say";
    paths.log = paths.agent / "log.md";
    paths.tools = paths.agent / "tools.json";
    paths.pending = paths.agent / "pending.json";
    return paths;
}

}  // namespace detail
}  // namespace aos::agent
