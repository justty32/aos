#include "internal.hpp"

#include <nlohmann/json.hpp>

namespace aos::agent::detail {

void deliver(const Paths &paths, std::string_view id,
             const std::vector<std::string> &argv, bool tool_instruction) {
    nlohmann::json instruction = {{"id", id}, {"argv", argv}};
    if (tool_instruction) {
        instruction["cwd"] = ".";
        instruction["timeout_ms"] = 30000;
    }
    atomic_write(paths.inbox / (std::string(id) + ".json"),
                 instruction.dump(2) + "\n");
}

void deliver_self(const Paths &paths, std::string_view name,
                  std::uint64_t turn) {
    const std::string id =
        "agent-" + std::string(name) + "-" + std::to_string(turn);
    deliver(paths, id,
            {"aos", "agent", "step", paths.folder.string(),
             std::string(name)});
}

}  // namespace aos::agent::detail
