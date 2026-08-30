#include "internal.hpp"

#include <aos/tool.hpp>
#include <nlohmann/json.hpp>

#include <atomic>
#include <chrono>
#include <cstdlib>
#include <stdexcept>
#include <string>
#include <system_error>
#include <unistd.h>

namespace aos::agent {
namespace {

bool executable_file(const std::filesystem::path &path) {
    std::error_code code;
    return std::filesystem::is_regular_file(path, code) &&
           ::access(path.c_str(), X_OK) == 0;
}

/* every/agent-<name>.json 要寫哪個 aos。
 *
 * L1-01：裸的 "aos" 會讓「用絕對路徑呼叫剛編好的 aos」那種人每回合 exec 失敗
 * （exit 127、stderr 空白），整個世界靜默空轉。所以 init 當下就把**這一個**
 * 正在跑的 aos 的絕對路徑寫死進去。
 * 找不到（例如從函式庫直接呼叫 initialize()）才退回裸的 "aos"。 */
std::string aos_program_path() {
    if (const char *configured = std::getenv("AOS_BIN")) {
        const std::filesystem::path path = configured;
        if (executable_file(path)) return std::filesystem::absolute(path).string();
    }
    std::error_code code;
    const std::filesystem::path self =
        std::filesystem::read_symlink("/proc/self/exe", code);
    if (!code && self.filename() == "aos" && executable_file(self)) {
        return self.string();
    }
    if (const char *search = std::getenv("PATH")) {
        std::string_view rest(search);
        while (!rest.empty()) {
            const std::size_t separator = rest.find(':');
            const std::string_view entry = rest.substr(0, separator);
            if (!entry.empty()) {
                const std::filesystem::path candidate =
                    std::filesystem::path(std::string(entry)) / "aos";
                if (executable_file(candidate)) {
                    return std::filesystem::absolute(candidate).string();
                }
            }
            if (separator == std::string_view::npos) break;
            rest.remove_prefix(separator + 1);
        }
    }
    return "aos";
}

}  // namespace

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
    detail::atomic_write(paths.log_journal(), "");
    aos::tool::install_defaults(paths.folder);
    aos::tool::install_say_tool(paths.folder);
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
        {"argv", {aos_program_path(), "agent", "step"}}};
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
