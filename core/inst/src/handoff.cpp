#define _POSIX_C_SOURCE 200809L

#include <aos/inst.hpp>

#include <algorithm>
#include <cerrno>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include <dirent.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

namespace aos {
namespace {

struct Paths {
    std::string base;
    std::string temp;
    std::string runi;
    std::string inbox;
};

bool derive_paths(const std::string &base, Paths &paths) {
    constexpr std::string_view suffix = ".json";
    if (base.size() <= suffix.size() ||
        base.compare(base.size() - suffix.size(), suffix.size(), suffix) != 0) {
        return false;
    }
    paths.base = base;
    paths.temp = base + ".temp";
    paths.runi = base + ".runi";
    paths.inbox = base.substr(0, base.size() - suffix.size()) + ".tempd";
    return true;
}

int open_retry(const char *path, int flags, mode_t mode = 0) {
    int fd;
    do {
        fd = open(path, flags, mode);
    } while (fd < 0 && errno == EINTR);
    return fd;
}

bool close_checked(int fd, int &error) {
    if (close(fd) == 0) return true;
    error = errno;
    return false;
}

bool read_file(const std::string &path, std::string &buffer, int &error) {
    const int fd = open_retry(path.c_str(), O_RDONLY | O_CLOEXEC);
    if (fd < 0) {
        error = errno;
        return false;
    }
    char chunk[64 * 1024];
    bool ok = true;
    for (;;) {
        ssize_t count;
        do {
            count = read(fd, chunk, sizeof(chunk));
        } while (count < 0 && errno == EINTR);
        if (count < 0) {
            error = errno;
            ok = false;
            break;
        }
        if (count == 0) break;
        buffer.append(chunk, static_cast<std::size_t>(count));
    }
    if (!close_checked(fd, error)) ok = false;
    return ok;
}

bool write_file(const std::string &path, const std::string &data, int &error) {
    const int fd = open_retry(path.c_str(),
                              O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0666);
    if (fd < 0) {
        error = errno;
        return false;
    }
    const char *cursor = data.data();
    std::size_t remaining = data.size();
    bool ok = true;
    while (remaining != 0) {
        ssize_t count;
        do {
            count = write(fd, cursor, remaining);
        } while (count < 0 && errno == EINTR);
        if (count <= 0) {
            error = count < 0 ? errno : EIO;
            ok = false;
            break;
        }
        cursor += count;
        remaining -= static_cast<std::size_t>(count);
    }
    if (!close_checked(fd, error)) ok = false;
    return ok;
}

bool is_delivery_name(const std::string &name) {
    const std::size_t extension = name.find('.');
    return extension != std::string::npos && extension != 0 &&
           name.substr(extension) == ".json";
}

std::string join_path(const std::string &directory, const std::string &name) {
    return directory + "/" + name;
}

void add_issue(HandoffResult &result, HandoffIssueKind kind,
               const std::string &path, InstState state, int error) {
    result.issues.push_back(HandoffIssue{kind, path, state, error});
}

void isolate_delivery(const std::string &path, HandoffResult &result) {
    if (rename(path.c_str(), (path + ".bad").c_str()) != 0) {
        add_issue(result, HandoffIssueKind::IsolationFailed, path,
                  InstState::Ok, errno);
    }
}

}  // namespace

HandoffState aggregate_instructions(const std::string &instruction_path,
                                    HandoffResult &result) {
    result = HandoffResult{};
    Paths paths;
    if (!derive_paths(instruction_path, paths)) {
        return HandoffState::InvalidArgument;
    }

    struct stat status {};
    if (lstat(paths.base.c_str(), &status) == 0) return HandoffState::Ok;
    if (errno != ENOENT) {
        result.path = paths.base;
        result.error = errno;
        return HandoffState::InstructionReadFailed;
    }

    DIR *directory = opendir(paths.inbox.c_str());
    if (directory == nullptr && errno == ENOENT) return HandoffState::Ok;
    if (directory == nullptr) {
        result.path = paths.inbox;
        result.error = errno;
        return HandoffState::InboxReadFailed;
    }

    std::vector<std::string> names;
    errno = 0;
    while (dirent *entry = readdir(directory)) {
        std::string name = entry->d_name;
        if (is_delivery_name(name)) names.push_back(std::move(name));
        errno = 0;
    }
    const int read_error = errno;
    const int close_error = closedir(directory) == 0 ? 0 : errno;
    if (read_error != 0 || close_error != 0) {
        result.path = paths.inbox;
        result.error = read_error != 0 ? read_error : close_error;
        return HandoffState::InboxReadFailed;
    }
    std::sort(names.begin(), names.end());

    std::vector<inst_t> combined;
    std::vector<std::string> accepted;
    for (const std::string &name : names) {
        const std::string path = join_path(paths.inbox, name);
        std::string document;
        int error = 0;
        if (!read_file(path, document, error)) {
            add_issue(result, HandoffIssueKind::DeliveryReadFailed, path,
                      InstState::Ok, error);
            isolate_delivery(path, result);
            continue;
        }

        std::vector<inst_t> delivery;
        std::size_t error_record = 0;
        const char empty = '\0';
        const char *data = document.empty() ? &empty : document.data();
        const InstState state =
            read_all(data, document.size(), delivery, &error_record);
        if (state != InstState::Ok) {
            add_issue(result, HandoffIssueKind::InvalidDelivery, path, state, 0);
            isolate_delivery(path, result);
            continue;
        }
        for (inst_t &instruction : delivery) {
            combined.push_back(std::move(instruction));
        }
        accepted.push_back(path);
    }
    if (combined.empty()) return HandoffState::Ok;

    std::string output;
    if (write_all(combined, output, nullptr) != InstState::Ok) {
        result.path = paths.temp;
        result.error = EINVAL;
        return HandoffState::PublishWriteFailed;
    }
    int error = 0;
    if (!write_file(paths.temp, output, error)) {
        unlink(paths.temp.c_str());
        result.path = paths.temp;
        result.error = error;
        return HandoffState::PublishWriteFailed;
    }
    if (rename(paths.temp.c_str(), paths.base.c_str()) != 0) {
        result.path = paths.temp;
        result.error = errno;
        return HandoffState::RenameFailed;
    }
    result.published = true;

    for (const std::string &path : accepted) {
        if (unlink(path.c_str()) != 0) {
            add_issue(result, HandoffIssueKind::DeliveryRemoveFailed, path,
                      InstState::Ok, errno);
        }
    }
    return HandoffState::Ok;
}

HandoffState claim_instruction(const std::string &instruction_path,
                               std::string &document,
                               HandoffResult &result) {
    result = HandoffResult{};
    document.clear();
    Paths paths;
    if (!derive_paths(instruction_path, paths)) {
        return HandoffState::InvalidArgument;
    }

    struct stat status {};
    if (lstat(paths.runi.c_str(), &status) == 0) {
        result.path = paths.runi;
        return HandoffState::Busy;
    }
    if (errno != ENOENT) {
        result.path = paths.runi;
        result.error = errno;
        return HandoffState::InstructionReadFailed;
    }

    int error = 0;
    if (!read_file(paths.base, document, error)) {
        if (error == ENOENT) return HandoffState::NoInstruction;
        result.path = paths.base;
        result.error = error;
        return HandoffState::InstructionReadFailed;
    }
    if (rename(paths.base.c_str(), paths.runi.c_str()) != 0) {
        result.path = paths.base;
        result.error = errno;
        return HandoffState::RenameFailed;
    }
    return HandoffState::Ok;
}

HandoffState release_instruction(const std::string &instruction_path,
                                 HandoffResult &result) {
    result = HandoffResult{};
    Paths paths;
    if (!derive_paths(instruction_path, paths)) {
        return HandoffState::InvalidArgument;
    }
    if (unlink(paths.runi.c_str()) != 0) {
        result.path = paths.runi;
        result.error = errno;
        return HandoffState::ReleaseFailed;
    }
    return HandoffState::Ok;
}

const char *to_string(HandoffState state) noexcept {
    switch (state) {
    case HandoffState::Ok: return "Ok";
    case HandoffState::InvalidArgument: return "InvalidArgument";
    case HandoffState::Busy: return "Busy";
    case HandoffState::NoInstruction: return "NoInstruction";
    case HandoffState::InboxReadFailed: return "InboxReadFailed";
    case HandoffState::InstructionReadFailed: return "InstructionReadFailed";
    case HandoffState::PublishWriteFailed: return "PublishWriteFailed";
    case HandoffState::RenameFailed: return "RenameFailed";
    case HandoffState::ReleaseFailed: return "ReleaseFailed";
    }
    return "Unknown";
}

const char *to_string(HandoffIssueKind kind) noexcept {
    switch (kind) {
    case HandoffIssueKind::InvalidDelivery: return "InvalidDelivery";
    case HandoffIssueKind::DeliveryReadFailed: return "DeliveryReadFailed";
    case HandoffIssueKind::IsolationFailed: return "IsolationFailed";
    case HandoffIssueKind::DeliveryRemoveFailed: return "DeliveryRemoveFailed";
    }
    return "Unknown";
}

}  // namespace aos
