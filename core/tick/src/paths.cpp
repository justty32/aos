#include <aos/tick.hpp>

#include <filesystem>
#include <system_error>

namespace aos::tick {

Paths paths_of(const loop::Layout &layout) {
    const std::filesystem::path heartbeat =
        std::filesystem::path(layout.aos) / "heartbeat";
    return {
        .heartbeat = heartbeat.string(),
        .routines_file = (heartbeat / "routines.json").string(),
        .schedule_file = (heartbeat / "schedule.json").string(),
        .log_file = (heartbeat / "log.md").string(),
        .config_file = (heartbeat / "config.json").string(),
    };
}

std::optional<std::string> single_agent(const loop::Layout &layout) {
    std::error_code code;
    if (!std::filesystem::is_directory(layout.agents_dir, code) || code) {
        return std::nullopt;
    }

    std::optional<std::string> found;
    std::filesystem::directory_iterator entry(layout.agents_dir, code);
    if (code) return std::nullopt;
    const std::filesystem::directory_iterator end;
    while (entry != end) {
        const std::string name = entry->path().filename().string();
        if (!name.empty() && name.front() != '.') {
            std::error_code status_code;
            if (entry->is_directory(status_code) && !status_code) {
                if (found.has_value()) return std::nullopt;
                found = name;
            }
        }
        entry.increment(code);
        if (code) return std::nullopt;
    }
    return found;
}

}  // namespace aos::tick
