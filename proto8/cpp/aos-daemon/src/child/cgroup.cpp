// cgroup.cpp：實作 cgroup v2 探測還原、每列份額及由下往上的整格清理。
#include "child/cgroup.hpp"
#include "aos/util/files.hpp"
#include <cerrno>
#include <chrono>
#include <cstring>
#include <filesystem>
#include <fcntl.h>
#include <sstream>
#include <thread>
#include <unistd.h>

namespace aos::daemon {
namespace {

std::string put(const std::string& path, const std::string& value) {
    int fd = open(path.c_str(), O_WRONLY | O_CLOEXEC);
    if (fd < 0) {
        return "cannot write " + value + " to " + path + ": " + std::strerror(errno);
    }
    ssize_t n;
    do {
        n = write(fd, value.data(), value.size());
    } while (n < 0 && errno == EINTR);
    int e = n < 0 ? errno : EIO;
    close(fd);
    return n == (ssize_t)value.size() ? "" : "cannot write " + value + " to " + path + ": " + std::strerror(e);
}

std::string make(const std::string& path, bool& created) {
    std::error_code ec;
    created = std::filesystem::create_directory(path, ec);
    return ec ? "cannot mkdir " + path + ": " + ec.message() : "";
}

std::string remove_tree(const std::filesystem::path& path) {
    std::error_code ec;
    for (std::filesystem::directory_iterator it(path, ec), end; !ec && it != end; it.increment(ec)) {
        if (it->is_directory(ec)) {
            std::string why = remove_tree(it->path());
            if (!why.empty()) {
                return why;
            }
        }
    }
    if (ec) {
        return "cannot list " + path.string() + ": " + ec.message();
    }
    if (rmdir(path.c_str()) != 0) {
        return "cannot rmdir " + path.string() + ": " + std::strerror(errno);
    }
    return "";
}

}  // namespace

long long cgroup_event(const std::string& path, const std::string& key) {
    int err = 0;
    auto text = aos::read_file(path, err);
    if (!text) {
        return -1;
    }
    std::istringstream in(*text);
    std::string k;
    long long n;
    while (in >> k >> n) {
        if (k == key) {
            return n;
        }
    }
    return -1;
}

bool cgroup_populated(const std::string& cell) {
    return cgroup_event(cell + "/cgroup.events", "populated") == 1;
}

std::string cgroup_kill(const std::string& cell) {
    return put(cell + "/cgroup.kill", "1");
}

std::string cgroup_empty_cell(const std::string& cell, bool remove) {
    long long populated = cgroup_event(cell + "/cgroup.events", "populated");
    if (populated < 0) {
        return "cannot read " + cell + "/cgroup.events";
    }
    if (populated == 1) {
        std::string why = cgroup_kill(cell);
        if (!why.empty()) {
            return why;
        }
        auto end = std::chrono::steady_clock::now() + std::chrono::seconds(1);
        do {
            std::this_thread::sleep_for(std::chrono::milliseconds(50));
            populated = cgroup_event(cell + "/cgroup.events", "populated");
        } while (populated == 1 && std::chrono::steady_clock::now() < end);
        if (populated != 0) {
            return "cgroup remains populated: " + cell;
        }
    }
    if (remove) {
        return remove_tree(cell);
    }
    std::error_code ec;
    for (std::filesystem::directory_iterator it(cell, ec), end; !ec && it != end; it.increment(ec)) {
        if (it->is_directory(ec)) {
            std::string why = remove_tree(it->path());
            if (!why.empty()) {
                return why;
            }
        }
    }
    return ec ? "cannot list " + cell + ": " + ec.message() : "";
}

bool cgroup_setup(std::string& base, std::string& reason) {
    base.clear();
    int err = 0;
    auto text = aos::read_file("/proc/self/cgroup", err);
    if (!text) {
        reason = "cannot read /proc/self/cgroup: " + std::string(std::strerror(err));
        return false;
    }
    std::istringstream lines(*text);
    std::string line;
    std::string root;
    while (std::getline(lines, line)) {
        if (line.starts_with("0::")) {
            std::string path = line.substr(3);
            while (!path.empty() && (path.back() == '\r' || path.back() == '\n' || path.back() == '/')) {
                path.pop_back();
            }
            root = "/sys/fs/cgroup" + path;
            break;
        }
    }
    if (root.empty()) {
        reason = "no cgroup v2 entry";
        return false;
    }
    auto controllers = aos::read_file(root + "/cgroup.controllers", err);
    if (!controllers) {
        reason = "cannot read " + root + "/cgroup.controllers: " + std::strerror(err);
        return false;
    }
    std::istringstream tokens(*controllers);
    bool memory = false, pids = false;
    while (tokens >> line) {
        memory = memory || line == "memory";
        pids = pids || line == "pids";
    }
    if (!memory || !pids) {
        reason = "controllers lack memory/pids";
        return false;
    }
    bool made_daemon = false, made_procs = false, moved = false, enabled = false;
    reason = make(root + "/daemon", made_daemon);
    if (reason.empty()) {
        reason = put(root + "/daemon/cgroup.procs", std::to_string(getpid()));
        moved = reason.empty();
    }
    if (reason.empty()) {
        reason = put(root + "/cgroup.subtree_control", "+memory +pids");
        enabled = reason.empty();
    }
    if (reason.empty()) {
        reason = make(root + "/procs", made_procs);
    }
    if (reason.empty()) {
        reason = put(root + "/procs/cgroup.subtree_control", "+memory +pids");
    }
    if (reason.empty()) {
        base = root;
        return true;
    }
    // 還原僅碰這次建的格；每一步都盡力做，不蓋過原始錯誤。
    if (made_procs) {
        rmdir((root + "/procs").c_str());
    }
    if (enabled) {
        put(root + "/cgroup.subtree_control", "-memory -pids");
    }
    if (moved) {
        put(root + "/cgroup.procs", std::to_string(getpid()));
    }
    if (made_daemon) {
        rmdir((root + "/daemon").c_str());
    }
    return false;
}

std::string cgroup_prepare(const std::string& base, const std::string& name, const Json& limits) {
    std::string cell = base + "/procs/" + name;
    auto fail = [&](const std::string& why) {
        if (!why.empty()) {
            throw Error{code::LimitBad, "cgroup " + cell + ": " + why};
        }
    };
    std::error_code ec;
    if (std::filesystem::exists(cell, ec)) {
        fail(cgroup_empty_cell(cell, true));
    }
    if (ec) {
        fail("cannot stat " + cell + ": " + ec.message());
    }
    bool created = false;
    fail(make(cell, created));
    bool mem = limits.is_object() && limits.contains("mem_total_mb");
    std::string max = mem ? std::to_string(limits["mem_total_mb"].get<unsigned long long>() << 20) : "max";
    fail(put(cell + "/memory.max", max));
    if (std::filesystem::exists(cell + "/memory.swap.max", ec)) {
        fail(put(cell + "/memory.swap.max", mem ? "0" : "max"));
    }
    fail(put(cell + "/pids.max", limits.is_object() && limits.contains("procs_total") ? aos::dumps(limits["procs_total"]) : "max"));
    return cell;
}

bool cgroup_has_pid(const std::string& cell, pid_t pid) {
    int err = 0;
    auto text = aos::read_file(cell + "/cgroup.procs", err);
    std::istringstream in(text.value_or(""));
    long long n;
    while (in >> n) {
        if (n == pid) {
            return true;
        }
    }
    return false;
}

}  // namespace aos::daemon
