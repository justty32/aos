#define _POSIX_C_SOURCE 200809L

// handoff 層的三個公開動作：投遞聚合（含空投遞消化與原子發佈）、取件、釋放。
// 路徑推導與低階檔案存取在 handoff_fs.hpp／.cpp。
// 只依賴 inst＋format：不印訊息、不執行 instruction。

#include <aos/inst.hpp>

#include "handoff_fs.hpp"
#include "handoff_header.hpp"

#include <algorithm>
#include <cerrno>
#include <cstddef>
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

std::string parent_directory(const std::string &path) {
    const std::size_t slash = path.find_last_of('/');
    if (slash == std::string::npos) return ".";
    if (slash == 0) return "/";
    return path.substr(0, slash);
}

// rename／unlink 之後把目錄項落盤（§D-5）。失敗只記 issue、不改變控制流：目錄項
// 本身已經換好了，少的是耐久性保證；為此讓整輪彙整失敗只會把世界卡住，更糟。
void sync_directory(const std::string &directory, HandoffResult &result) {
    int error = 0;
    if (!detail::fsync_dir(directory, error)) {
        add_issue(result, HandoffIssueKind::DirectorySyncFailed, directory,
                  InstState::Ok, error);
    }
}

void remove_accepted_deliveries(const std::vector<std::string> &accepted,
                                const std::string &inbox,
                                HandoffResult &result) {
    if (accepted.empty()) return;
    for (const std::string &path : accepted) {
        if (unlink(path.c_str()) != 0) {
            add_issue(result, HandoffIssueKind::DeliveryRemoveFailed, path,
                      InstState::Ok, errno);
        }
    }
    sync_directory(inbox, result);
}

// 現任 header 的批 id。沒有 header、讀不到或讀不懂都回 false（後兩者記 issue），
// 呼叫端一律當作「沒有可比對的 id」，照常發布。
bool current_header_id(const std::string &path, std::string &id,
                       HandoffResult &result) {
    std::string document;
    int error = 0;
    if (!detail::read_file(path, document, error)) {
        if (error != ENOENT) {
            add_issue(result, HandoffIssueKind::HeaderInvalid, path,
                      InstState::Ok, error);
        }
        return false;
    }
    if (!detail::decode_header_id(document, id)) {
        add_issue(result, HandoffIssueKind::HeaderInvalid, path, InstState::Ok,
                  0);
        return false;
    }
    return true;
}

// 批 .temp 裡是不是一份完整的批——roll forward 的前提。彙整從不發布空批次，
// 所以解析出空批次的 .temp 一定不是我們提交過的那一份。
bool temp_holds_complete_batch(const std::string &path) {
    std::string document;
    int error = 0;
    if (!detail::read_file(path, document, error)) return false;
    std::vector<inst_t> batch;
    const char empty = '\0';
    const char *data = document.empty() ? &empty : document.data();
    return read_all(data, document.size(), batch, nullptr) == InstState::Ok &&
           !batch.empty();
}

}  // namespace

HandoffState aggregate_instructions(const std::string &instruction_path,
                                    HandoffResult &result) {
    result = HandoffResult{};
    detail::HandoffPaths paths;
    detail::HeaderPaths header;
    if (!detail::derive_paths(instruction_path, paths) ||
        !detail::derive_header_paths(instruction_path, header)) {
        return HandoffState::InvalidArgument;
    }
    const std::string base_directory = parent_directory(paths.base);

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
    detail::BatchDigest digest;
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
        digest.add(name, document);
    }
    if (combined.empty()) {
        // Otherwise empty deliveries remain in the inbox and are reread forever.
        // 沒有東西發布，就不寫 header：header 描述的是「現任的批」。
        remove_accepted_deliveries(accepted, paths.inbox, result);
        return HandoffState::Ok;
    }

    // 去重兜底（§D-6）。header 的 id 跟本輪摘要相同＝這一組投遞上一輪已經跨過提交點
    // （header 的 rename），只是投遞沒被清掉——崩在刪投遞之前，或 unlink 全數失敗。
    const std::string id = digest.id();
    std::string published_id;
    if (current_header_id(header.base, published_id, result) &&
        published_id == id) {
        if (temp_holds_complete_batch(paths.temp)) {
            // 上次崩在兩個 rename 之間：批還完整躺在 .temp，往前補完（roll forward），
            // 這一批沒丟。
            if (rename(paths.temp.c_str(), paths.base.c_str()) != 0) {
                result.path = paths.temp;
                result.error = errno;
                return HandoffState::RenameFailed;
            }
            sync_directory(base_directory, result);
            result.published = true;
        }
        // 沒有 .temp：上一輪已經發布完，批也已經被取走（或正在跑）。只清投遞、
        // 不重發——這正是「同一批不會執行兩次」的兜底。
        remove_accepted_deliveries(accepted, paths.inbox, result);
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
    // 順序（§D-5）：批 .temp 已落盤，接著寫 header .temp、rename header，那一次
    // rename 就是**去重承諾的提交點**，之後才 rename 批。
    // 為什麼 header 要先：崩在兩個 rename 之間會留下「header 是新 id ＋ 批還在
    // .temp」——重開機認得出來，可以 roll forward。反過來（批先、header 後）崩掉
    // 只剩「批已發布、header 還是舊 id」，跟「這批根本沒發布過」長得一模一樣，
    // 重開機分不出來，就會重演雙重執行。
    // header 寫不成不是致命傷：這一批照發，只是這一輪沒有去重保證（退回本階段
    // 之前的行為），記 issue 讓上層看得見。
    if (!detail::write_file(header.temp, detail::encode_header(id), error)) {
        add_issue(result, HandoffIssueKind::HeaderWriteFailed, header.temp,
                  InstState::Ok, error);
        unlink(header.temp.c_str());
    } else if (rename(header.temp.c_str(), header.base.c_str()) != 0) {
        add_issue(result, HandoffIssueKind::HeaderWriteFailed, header.base,
                  InstState::Ok, errno);
        unlink(header.temp.c_str());
    } else {
        sync_directory(base_directory, result);
    }
    if (rename(paths.temp.c_str(), paths.base.c_str()) != 0) {
        result.path = paths.temp;
        result.error = errno;
        return HandoffState::RenameFailed;
    }
    sync_directory(base_directory, result);
    result.published = true;

    remove_accepted_deliveries(accepted, paths.inbox, result);
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
    case HandoffState::DeliveryInvalid: return "DeliveryInvalid";
    }
    return "Unknown";
}

const char *to_string(HandoffIssueKind kind) noexcept {
    switch (kind) {
    case HandoffIssueKind::InvalidDelivery: return "InvalidDelivery";
    case HandoffIssueKind::DeliveryReadFailed: return "DeliveryReadFailed";
    case HandoffIssueKind::IsolationFailed: return "IsolationFailed";
    case HandoffIssueKind::DeliveryRemoveFailed: return "DeliveryRemoveFailed";
    case HandoffIssueKind::HeaderWriteFailed: return "HeaderWriteFailed";
    case HandoffIssueKind::HeaderInvalid: return "HeaderInvalid";
    case HandoffIssueKind::DirectorySyncFailed: return "DirectorySyncFailed";
    }
    return "Unknown";
}

}  // namespace aos
