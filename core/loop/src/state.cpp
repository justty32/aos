#include <aos/loop.hpp>

#include "fs.hpp"
#include "state.hpp"

#include <algorithm>
#include <cstdint>
#include <string>
#include <utility>
#include <vector>

#include <dirent.h>

namespace aos::loop {

std::map<std::string, std::string> mirror_agents(const Layout &layout) {
    std::map<std::string, std::string> agents;
    DIR *directory = ::opendir(layout.agents_dir.c_str());
    if (directory == nullptr) return agents;

    while (dirent *entry = ::readdir(directory)) {
        const std::string name = entry->d_name;
        if (name == "." || name == "..") continue;
        std::string text;
        std::string ignored;
        const std::string path =
            fs::join(fs::join(layout.agents_dir, name), "status.json");
        if (fs::read_file(path, text, ignored)) agents.emplace(name, text);
    }
    ::closedir(directory);
    return agents;
}

bool write_state(const Layout &layout, const wire::State &state,
                 std::string &error) {
    return fs::write_atomic(layout.state_file, wire::to_json_text(state), error);
}

namespace detail {

std::vector<wire::RunningEntry> running_entries(
    const std::vector<wire::Inst> &insts,
    const std::vector<exec::Running> &running) {
    std::vector<wire::RunningEntry> entries;
    const std::size_t count = std::min(insts.size(), running.size());
    entries.reserve(count);
    for (std::size_t index = 0; index < count; ++index) {
        wire::RunningEntry entry;
        entry.id = insts[index].id;
        entry.argv0 = insts[index].argv.empty() ? "" : insts[index].argv[0];
        entry.pid = static_cast<std::int64_t>(running[index].pid);
        entry.started_at = running[index].started_at;
        entry.status = "running";
        entries.push_back(std::move(entry));
    }
    return entries;
}

void mark_done(std::vector<wire::RunningEntry> &entries,
               const std::vector<exec::Result> &results) {
    const std::size_t count = std::min(entries.size(), results.size());
    for (std::size_t index = 0; index < count; ++index) {
        entries[index].status = "done";
        if (results[index].error.empty() && results[index].signal == 0) {
            entries[index].exit = results[index].exit;
        } else {
            entries[index].exit.reset();
        }
    }
}

}  // namespace detail
}  // namespace aos::loop
