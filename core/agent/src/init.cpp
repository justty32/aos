#include "internal.hpp"

#include <aos/tool.hpp>
#include <nlohmann/json.hpp>

#include <atomic>
#include <chrono>
#include <stdexcept>
#include <unistd.h>

namespace aos::agent {

void initialize(const std::filesystem::path &folder, std::string_view name,
                std::string_view persona, const Engine &requested_engine) {
    const detail::Paths paths = detail::paths_for(folder, name);
    if (!std::filesystem::is_directory(paths.folder)) {
        throw std::runtime_error("folder 不存在或不是資料夾: " +
                                 paths.folder.string());
    }
    const std::filesystem::path agents = paths.aos / "agents";
    if (std::filesystem::is_directory(agents)) {
        for (const auto &entry : std::filesystem::directory_iterator(agents)) {
            if (entry.is_directory()) {
                throw std::runtime_error(
                    paths.folder.string() + " 已經住著 agent " +
                    entry.path().filename().string() +
                    "；一個資料夾只住一隻");
            }
        }
    }
    std::filesystem::create_directories(paths.inbox);
    std::filesystem::create_directories(paths.every);
    std::filesystem::create_directories(paths.say);
    Engine engine = requested_engine;
    if (engine.kind.empty()) engine.kind = "lmstudio";
    if (engine.kind == "pi") {
        if (engine.provider.empty()) engine.provider = "deepseek";
        if (engine.model.empty()) engine.model = "deepseek-v4-flash";
        if (engine.session_id.empty()) engine.session_id = detail::new_uuid();
    }
    detail::write_engine(paths, engine);
    detail::atomic_write(paths.persona, persona);
    detail::write_history(paths, {});
    detail::write_status(paths, "idle", "等待訊息", 0);
    detail::atomic_write(paths.log, "");
    aos::tool::install_defaults(paths.folder);
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
    const nlohmann::json instruction = {
        {"argv", {"aos", "agent", "step"}}};
    detail::atomic_write(paths.every / ("agent-" + std::string(name) + ".json"),
                         instruction.dump(2) + "\n");
}

void say(const std::filesystem::path &folder, std::string_view name,
         std::string_view text, std::string_view from) {
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
    detail::atomic_write(paths.say / filename,
                         detail::message_body(from, text));
}

}  // namespace aos::agent
