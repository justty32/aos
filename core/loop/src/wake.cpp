#include <aos/loop.hpp>

#include "fs.hpp"

#include <algorithm>
#include <chrono>
#include <csignal>
#include <filesystem>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

#include <time.h>

namespace aos::loop::detail {

/* run 的 handler 與等待函式共用；handler 只能把它設成 1。 */
AOS_API volatile sig_atomic_t stop_requested = 0;

}  // namespace aos::loop::detail

namespace aos::loop {
namespace {

struct DirectoryStamp {
    std::uint64_t count = 0;
    std::int64_t max_mtime_ns = 0;
};

DirectoryStamp stamp(const std::filesystem::path &directory,
                     std::string_view extension) {
    DirectoryStamp result;
    std::error_code error;
    std::filesystem::directory_iterator entries(directory, error);
    const std::filesystem::directory_iterator end;
    while (!error && entries != end) {
        const auto path = entries->path();
        if (entries->is_regular_file(error) && !error &&
            path.extension() == extension) {
            ++result.count;
            const auto modified = entries->last_write_time(error);
            if (!error) {
                const auto nanoseconds =
                    std::chrono::duration_cast<std::chrono::nanoseconds>(
                        modified.time_since_epoch())
                        .count();
                if (result.count == 1 ||
                    nanoseconds > result.max_mtime_ns) {
                    result.max_mtime_ns = nanoseconds;
                }
            }
        }
        entries.increment(error);
    }
    return result;
}

struct DeliveryStamp {
    std::string text;
    std::uint64_t count = 0;
};

DeliveryStamp make_stamp(const Layout &layout) {
    std::ostringstream out;
    const DirectoryStamp inbox = stamp(layout.inbox, ".json");
    out << "inbox:" << inbox.count << ':' << inbox.max_mtime_ns;
    std::uint64_t count = inbox.count;

    std::vector<std::filesystem::path> agents;
    std::error_code error;
    std::filesystem::directory_iterator entries(layout.agents_dir, error);
    const std::filesystem::directory_iterator end;
    while (!error && entries != end) {
        if (entries->is_directory(error) && !error) {
            agents.push_back(entries->path());
        }
        entries.increment(error);
    }
    std::sort(agents.begin(), agents.end());
    for (const auto &agent : agents) {
        const DirectoryStamp say = stamp(agent / "say", ".md");
        out << ";agent:" << agent.filename().string() << ':' << say.count
            << ':' << say.max_mtime_ns;
        count += say.count;
    }
    return {out.str(), count};
}

bool sleep_for(std::uint64_t milliseconds) {
    timespec delay{};
    delay.tv_sec = static_cast<time_t>(milliseconds / 1000);
    delay.tv_nsec = static_cast<long>((milliseconds % 1000) * 1000000);
    return ::nanosleep(&delay, nullptr) == 0;
}

}  // namespace

std::string delivery_signature(const Layout &layout) {
    return make_stamp(layout).text;
}

bool wait_for_delivery(const Layout &layout, std::uint64_t timeout_ms,
                       std::uint64_t poll_ms) {
    const DeliveryStamp initial = make_stamp(layout);
    if (initial.count != 0) return true;
    if (timeout_ms == 0 || detail::stop_requested != 0) return false;
    if (poll_ms == 0) poll_ms = 1;

    const auto deadline = std::chrono::steady_clock::now() +
                          std::chrono::milliseconds(timeout_ms);
    while (true) {
        if (detail::stop_requested != 0) return false;
        const auto now = std::chrono::steady_clock::now();
        if (now >= deadline) return false;
        const auto remaining = std::chrono::duration_cast<std::chrono::milliseconds>(
                                   deadline - now)
                                   .count();
        if (!sleep_for(std::min<std::uint64_t>(
                poll_ms, static_cast<std::uint64_t>(
                             std::max<std::int64_t>(1, remaining))))) {
            return false;
        }
        if (detail::stop_requested != 0) return false;
        if (make_stamp(layout).text != initial.text) return true;
    }
}

}  // namespace aos::loop
