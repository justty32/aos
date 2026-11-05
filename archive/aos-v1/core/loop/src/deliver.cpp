#include <aos/loop.hpp>

#include "fs.hpp"

#include <atomic>
#include <chrono>
#include <string>

#include <unistd.h>

namespace aos::loop {

bool deliver(const Layout &layout, const wire::Inst &inst,
             std::string &error) {
    if (!ensure_layout(layout, error)) return false;
    const std::string path = fs::join(layout.inbox, inst.id + ".json");
    return fs::write_atomic(path, wire::to_json_text(inst), error);
}

wire::Inst inst_from_argv(const std::vector<std::string> &argv) {
    wire::Inst inst;
    inst.id = make_delivery_id();
    inst.argv = argv;
    return inst;
}

std::string make_delivery_id() {
    static std::atomic<std::uint64_t> sequence = 0;
    const auto now = std::chrono::time_point_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now());
    const auto epoch_ms = now.time_since_epoch().count();
    return "d-" + std::to_string(epoch_ms) + "-" +
           std::to_string(static_cast<long long>(::getpid())) + "-" +
           std::to_string(sequence.fetch_add(1));
}

}  // namespace aos::loop
