#include <aos/slot.hpp>

#include <nlohmann/json.hpp>

#include <sys/file.h>
#include <fcntl.h>
#include <unistd.h>

#include <algorithm>
#include <array>
#include <cerrno>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <limits>
#include <optional>
#include <string>
#include <utility>
#include <vector>

namespace aos::llm {
namespace {

using Json = nlohmann::json;

void validate_cpu(std::string_view cpu) {
    if (cpu.empty()) throw std::runtime_error("CPU 名稱不安全");
    for (const char character : cpu) {
        const bool safe =
            (character >= 'A' && character <= 'Z') ||
            (character >= 'a' && character <= 'z') ||
            (character >= '0' && character <= '9') || character == '.' ||
            character == '_' || character == '-';
        if (!safe) throw std::runtime_error("CPU 名稱不安全");
    }
}

Json read_json_file(const std::filesystem::path &path) {
    if (!std::filesystem::exists(path)) return Json();

    std::ifstream input(path);
    if (!input) {
        throw std::runtime_error("無法讀取 JSON 設定: " + path.string());
    }
    try {
        return Json::parse(input);
    } catch (const Json::parse_error &error) {
        throw std::runtime_error("JSON 設定無法解析: " + path.string() +
                                 ": " + error.what());
    }
}

const Json *cpu_entry(const Json &root, std::string_view cpu) {
    if (!root.is_object()) return nullptr;
    const auto found = root.find(std::string(cpu));
    if (found == root.end() || !found->is_object()) return nullptr;
    return &*found;
}

template <typename Integer>
std::optional<Integer> json_integer(const Json &object, const char *name) {
    if (!object.is_object()) return std::nullopt;
    const auto found = object.find(name);
    if (found == object.end()) return std::nullopt;

    if (found->is_number_unsigned()) {
        const auto value = found->get<unsigned long long>();
        if (value > static_cast<unsigned long long>(
                        std::numeric_limits<Integer>::max())) {
            return std::nullopt;
        }
        return static_cast<Integer>(value);
    }
    if (found->is_number_integer()) {
        const auto value = found->get<long long>();
        if (value < static_cast<long long>(
                        std::numeric_limits<Integer>::min()) ||
            value > static_cast<long long>(
                        std::numeric_limits<Integer>::max())) {
            return std::nullopt;
        }
        return static_cast<Integer>(value);
    }
    return std::nullopt;
}

enum class LockResult { acquired, busy };

LockResult try_lock(int descriptor, const std::filesystem::path &path) {
    if (::flock(descriptor, LOCK_EX | LOCK_NB) == 0) {
        return LockResult::acquired;
    }
    if (errno == EWOULDBLOCK || errno == EAGAIN) return LockResult::busy;
    throw std::runtime_error("無法鎖定檔案: " + path.string());
}

void close_descriptor(int descriptor) noexcept {
    if (descriptor >= 0) (void)::close(descriptor);
}

class Ticket {
public:
    Ticket(std::filesystem::path path, int descriptor)
        : path_(std::move(path)), descriptor_(descriptor) {}

    ~Ticket() { cleanup(); }
    Ticket(const Ticket &) = delete;
    Ticket &operator=(const Ticket &) = delete;

    void remove() {
        if (!path_.empty() && ::unlink(path_.c_str()) != 0 && errno != ENOENT) {
            throw std::runtime_error("無法刪除等待票: " + path_.string());
        }
        path_.clear();
        close_descriptor(descriptor_);
        descriptor_ = -1;
    }

private:
    void cleanup() noexcept {
        if (!path_.empty()) (void)::unlink(path_.c_str());
        close_descriptor(descriptor_);
    }

    std::filesystem::path path_;
    int descriptor_ = -1;
};

std::string ticket_name(int priority) {
    constexpr long long minimum_priority = -1000000000LL;
    constexpr long long maximum_priority = 1000000000LL;
    const long long bounded =
        std::clamp(static_cast<long long>(priority), minimum_priority,
                   maximum_priority);
    const long long priority_key = 2000000000LL - bounded;
    const long long timestamp =
        std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::system_clock::now().time_since_epoch())
            .count();

    std::array<char, 64> buffer{};
    std::snprintf(buffer.data(), buffer.size(), "%010lld-%020lld-%lld",
                  priority_key, timestamp, static_cast<long long>(::getpid()));
    return buffer.data();
}

std::vector<std::string> ticket_names(
    const std::filesystem::path &wait_directory) {
    std::vector<std::string> names;
    for (const auto &entry :
         std::filesystem::directory_iterator(wait_directory)) {
        names.push_back(entry.path().filename().string());
    }
    std::sort(names.begin(), names.end());
    return names;
}

std::vector<std::string> live_tickets(
    const std::filesystem::path &wait_directory,
    const std::string &own_name, bool remove_dead) {
    std::vector<std::string> live;
    for (const std::string &name : ticket_names(wait_directory)) {
        if (name == own_name) {
            live.push_back(name);
            continue;
        }

        const std::filesystem::path path = wait_directory / name;
        const int descriptor = ::open(path.c_str(), O_RDWR | O_CLOEXEC);
        if (descriptor < 0) {
            if (errno == ENOENT) continue;
            throw std::runtime_error("無法開啟等待票: " + path.string());
        }

        try {
            if (try_lock(descriptor, path) == LockResult::busy) {
                live.push_back(name);
            } else if (remove_dead && ::unlink(path.c_str()) != 0 &&
                       errno != ENOENT) {
                throw std::runtime_error("無法刪除陳屍票: " +
                                         path.string());
            }
        } catch (...) {
            close_descriptor(descriptor);
            throw;
        }
        close_descriptor(descriptor);
    }
    return live;
}

int count_held(const std::filesystem::path &directory, int limit) {
    if (limit <= 0 || !std::filesystem::is_directory(directory)) return 0;

    int held = 0;
    for (int index = 0; index < limit; ++index) {
        const std::filesystem::path path =
            directory / (std::to_string(index) + ".lock");
        const int descriptor = ::open(path.c_str(), O_RDWR | O_CLOEXEC);
        if (descriptor < 0) {
            if (errno == ENOENT) continue;
            throw std::runtime_error("無法開啟槽檔: " + path.string());
        }
        try {
            if (try_lock(descriptor, path) == LockResult::busy) ++held;
        } catch (...) {
            close_descriptor(descriptor);
            throw;
        }
        close_descriptor(descriptor);
    }
    return held;
}

int count_waiting(const std::filesystem::path &wait_directory) {
    if (!std::filesystem::is_directory(wait_directory)) return 0;
    return static_cast<int>(live_tickets(wait_directory, {}, false).size());
}

}  // namespace

WaitingLlm::WaitingLlm(const std::string &message)
    : std::runtime_error(message) {}

std::filesystem::path aos_home() {
    if (const char *value = std::getenv("AOS_HOME");
        value != nullptr && value[0] != '\0') {
        return std::filesystem::absolute(value).lexically_normal();
    }
    const char *home = std::getenv("HOME");
    if (home == nullptr || home[0] == '\0') {
        throw std::runtime_error("找不到 AOS_HOME 或 HOME");
    }
    return (std::filesystem::absolute(home) / ".aos").lexically_normal();
}

std::filesystem::path resolve_world(const std::filesystem::path &folder) {
    if (!folder.empty()) {
        return std::filesystem::absolute(folder).lexically_normal();
    }
    if (const char *value = std::getenv("AOS_FOLDER");
        value != nullptr && value[0] != '\0') {
        return std::filesystem::absolute(value).lexically_normal();
    }

    const std::filesystem::path current = std::filesystem::current_path();
    for (std::filesystem::path candidate = current;;) {
        if (std::filesystem::is_directory(candidate / ".aos")) {
            return candidate;
        }
        const std::filesystem::path parent = candidate.parent_path();
        if (parent == candidate) break;
        candidate = parent;
    }
    return current;
}

CpuLimit read_limit(std::string_view cpu,
                    const std::filesystem::path &folder) {
    validate_cpu(cpu);
    const Json user = read_json_file(aos_home() / "cpus.json");
    const Json world =
        read_json_file(resolve_world(folder) / ".aos" / "llm.json");
    const Json *user_cpu = cpu_entry(user, cpu);
    const Json *world_cpu = cpu_entry(world, cpu);

    CpuLimit result;
    if (user_cpu != nullptr) {
        result.max_inflight = json_integer<int>(*user_cpu, "max_inflight");
        if (const auto wait = json_integer<long>(*user_cpu, "wait_ms")) {
            result.wait_ms = *wait;
        }
    }
    if (world_cpu != nullptr) {
        if (result.max_inflight) {
            if (const auto world_max =
                    json_integer<int>(*world_cpu, "max_inflight")) {
                result.max_inflight = std::min(*result.max_inflight,
                                               *world_max);
            }
        }
        if (const auto wait = json_integer<long>(*world_cpu, "wait_ms")) {
            result.wait_ms = *wait;
        }
    }
    return result;
}

Slot::Slot(int descriptor, int index) noexcept
    : descriptor_(descriptor), index_(index) {}

Slot::~Slot() { release(); }

Slot::Slot(Slot &&other) noexcept
    : descriptor_(std::exchange(other.descriptor_, -1)),
      index_(std::exchange(other.index_, -1)) {}

Slot &Slot::operator=(Slot &&other) noexcept {
    if (this != &other) {
        release();
        descriptor_ = std::exchange(other.descriptor_, -1);
        index_ = std::exchange(other.index_, -1);
    }
    return *this;
}

bool Slot::held() const noexcept { return descriptor_ >= 0; }

int Slot::index() const noexcept { return index_; }

void Slot::release() noexcept {
    close_descriptor(descriptor_);
    descriptor_ = -1;
    index_ = -1;
}

Slot acquire(std::string_view cpu, int priority,
             const std::filesystem::path &folder) {
    const CpuLimit limit = read_limit(cpu, folder);
    if (!limit.max_inflight) return Slot{};
    if (*limit.max_inflight <= 0) throw WaitingLlm("waiting-llm");

    const std::filesystem::path cpu_directory =
        aos_home() / "slots" / std::string(cpu);
    const std::filesystem::path wait_directory = cpu_directory / "wait";
    std::filesystem::create_directories(wait_directory);

    const std::string own_name = ticket_name(priority);
    const std::filesystem::path own_path = wait_directory / own_name;
    const int ticket_descriptor =
        ::open(own_path.c_str(), O_CREAT | O_RDWR | O_CLOEXEC, 0666);
    if (ticket_descriptor < 0) {
        throw std::runtime_error("無法建立等待票: " + own_path.string());
    }
    Ticket ticket(own_path, ticket_descriptor);
    if (try_lock(ticket_descriptor, own_path) == LockResult::busy) {
        throw std::runtime_error("等待票名稱衝突: " + own_path.string());
    }

    const auto start = std::chrono::steady_clock::now();
    while (true) {
        const std::vector<std::string> live =
            live_tickets(wait_directory, own_name, true);
        const auto position = std::find(live.begin(), live.end(), own_name);
        if (position == live.end()) {
            throw std::runtime_error("等待票遺失: " + own_path.string());
        }
        const auto rank = std::distance(live.begin(), position);
        if (rank < static_cast<decltype(rank)>(*limit.max_inflight)) {
            for (int index = 0; index < *limit.max_inflight; ++index) {
                const std::filesystem::path slot_path =
                    cpu_directory / (std::to_string(index) + ".lock");
                const int descriptor = ::open(
                    slot_path.c_str(), O_CREAT | O_RDWR | O_CLOEXEC, 0666);
                if (descriptor < 0) {
                    throw std::runtime_error("無法開啟槽檔: " +
                                             slot_path.string());
                }
                try {
                    if (try_lock(descriptor, slot_path) ==
                        LockResult::acquired) {
                        ticket.remove();
                        return Slot(descriptor, index);
                    }
                } catch (...) {
                    close_descriptor(descriptor);
                    throw;
                }
                close_descriptor(descriptor);
            }
        }

        const long elapsed_ms =
            std::chrono::duration_cast<std::chrono::milliseconds>(
                std::chrono::steady_clock::now() - start)
                .count();
        if (elapsed_ms >= limit.wait_ms) throw WaitingLlm("waiting-llm");
        (void)::usleep(20000);
    }
}

std::vector<SlotStatus> slot_status(const std::filesystem::path &folder) {
    const Json user = read_json_file(aos_home() / "cpus.json");
    if (!user.is_object()) return {};

    std::vector<std::string> cpus;
    cpus.reserve(user.size());
    for (const auto &[name, value] : user.items()) {
        (void)value;
        cpus.push_back(name);
    }
    std::sort(cpus.begin(), cpus.end());

    std::vector<SlotStatus> statuses;
    for (const std::string &cpu : cpus) {
        const CpuLimit limit = read_limit(cpu, folder);
        if (!limit.max_inflight) continue;

        const std::filesystem::path directory =
            aos_home() / "slots" / cpu;
        statuses.push_back({cpu, *limit.max_inflight,
                            count_held(directory, *limit.max_inflight),
                            count_waiting(directory / "wait"), limit.wait_ms});
    }
    return statuses;
}

}  // namespace aos::llm
