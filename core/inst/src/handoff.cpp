#define _POSIX_C_SOURCE 200809L

// handoff 層的三個公開動作：投遞聚合（含空投遞消化與原子發佈）、取件、釋放。
// 路徑推導與低階檔案存取在 handoff_fs.hpp／.cpp。
// 只依賴 inst＋format：不印訊息、不執行 instruction。

#include <aos/inst.hpp>

#include "handoff_fs.hpp"

#include <algorithm>
#include <cerrno>
#include <cstdio>
#include <string>
#include <utility>
#include <vector>

#include <dirent.h>
#include <sys/stat.h>
#include <unistd.h>

namespace aos {
namespace {

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

void remove_accepted_deliveries(const std::vector<std::string> &accepted,
                                HandoffResult &result) {
    for (const std::string &path : accepted) {
        if (unlink(path.c_str()) != 0) {
            add_issue(result, HandoffIssueKind::DeliveryRemoveFailed, path,
                      InstState::Ok, errno);
        }
    }
}

}  // namespace

HandoffState aggregate_instructions(const std::string &instruction_path,
                                    HandoffResult &result) {
    result = HandoffResult{};
    detail::HandoffPaths paths;
    if (!detail::derive_paths(instruction_path, paths)) {
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
        if (detail::is_delivery_name(name)) names.push_back(std::move(name));
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
        const std::string path = detail::join_path(paths.inbox, name);
        std::string document;
        int error = 0;
        if (!detail::read_file(path, document, error)) {
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
    if (combined.empty()) {
        // Otherwise empty deliveries remain in the inbox and are reread forever.
        remove_accepted_deliveries(accepted, result);
        return HandoffState::Ok;
    }

    std::string output;
    if (write_all(combined, output, nullptr) != InstState::Ok) {
        result.path = paths.temp;
        result.error = EINVAL;
        return HandoffState::PublishWriteFailed;
    }
    int error = 0;
    if (!detail::write_file(paths.temp, output, error)) {
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

    remove_accepted_deliveries(accepted, result);
    return HandoffState::Ok;
}

HandoffState claim_instruction(const std::string &instruction_path,
                               std::string &document,
                               HandoffResult &result) {
    result = HandoffResult{};
    document.clear();
    detail::HandoffPaths paths;
    if (!detail::derive_paths(instruction_path, paths)) {
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
    if (!detail::read_file(paths.base, document, error)) {
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
    detail::HandoffPaths paths;
    if (!detail::derive_paths(instruction_path, paths)) {
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
