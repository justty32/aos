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

}  // namespace aos::agent::detail
