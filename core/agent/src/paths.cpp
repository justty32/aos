#include "internal.hpp"

#include <stdexcept>

namespace aos::agent {

std::filesystem::path absolute_folder(const std::filesystem::path &folder) {
    if (folder.empty()) throw std::invalid_argument("folder 不可為空");
    return std::filesystem::absolute(folder).lexically_normal();
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
