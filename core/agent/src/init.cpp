#include "internal.hpp"

#include <nlohmann/json.hpp>

#include <atomic>
#include <chrono>
#include <stdexcept>
#include <unistd.h>

namespace aos::agent {

void initialize(const std::filesystem::path &folder, std::string_view name,
                std::string_view persona) {
    const detail::Paths paths = detail::paths_for(folder, name);
    if (!std::filesystem::is_directory(paths.folder)) {
        throw std::runtime_error("folder 不存在或不是資料夾: " +
                                 paths.folder.string());
    }
    std::filesystem::create_directories(paths.inbox);
    std::filesystem::create_directories(paths.say);
    detail::atomic_write(paths.persona, persona);
    detail::write_history(paths, {});
    detail::write_status(paths, "idle", "等待訊息", 0);
    detail::atomic_write(paths.log, "");
    detail::write_tools(paths, detail::default_tools());
    detail::write_pending(paths, {});
    if (!std::filesystem::exists(paths.aos / "turn")) {
        detail::atomic_write(paths.aos / "turn", "1\n");
    }
    if (!std::filesystem::exists(paths.aos / "state.json")) {
        const nlohmann::json status =
            nlohmann::json::parse(detail::read_text(paths.status));
        const nlohmann::json state = {
            {"turn", 0},
            {"phase", "idle"},
            {"running", nlohmann::json::array()},
            {"agents", {{std::string(name), status}}}};
        detail::atomic_write(paths.aos / "state.json", state.dump(2) + "\n");
    }
    detail::deliver_self(paths, name, 0);
}

void say(const std::filesystem::path &folder, std::string_view name,
         std::string_view text) {
    const detail::Paths paths = detail::paths_for(folder, name);
    if (!std::filesystem::is_directory(paths.say)) {
        throw std::runtime_error("agent 尚未初始化: " + std::string(name));
    }
    static std::atomic<std::uint64_t> sequence{0};
    const auto stamp = std::chrono::duration_cast<std::chrono::nanoseconds>(
                           std::chrono::system_clock::now().time_since_epoch())
                           .count();
    const std::string filename = std::to_string(stamp) + "-" +
                                 std::to_string(getpid()) + "-" +
                                 std::to_string(sequence++) + ".md";
    detail::atomic_write(paths.say / filename, text);
}

}  // namespace aos::agent
