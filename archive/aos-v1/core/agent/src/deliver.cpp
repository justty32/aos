#include "internal.hpp"

#include <nlohmann/json.hpp>

namespace aos::agent::detail {

void deliver(const Paths &paths, std::string_view id,
             const std::vector<std::string> &argv, std::string_view cwd,
             std::uint64_t timeout_ms) {
    const nlohmann::json instruction = {
        {"id", id}, {"argv", argv}, {"cwd", cwd}, {"timeout_ms", timeout_ms}};
    atomic_write(paths.inbox / (std::string(id) + ".json"),
                 instruction.dump(2) + "\n");
}

}  // namespace aos::agent::detail
