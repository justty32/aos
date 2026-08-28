#define _POSIX_C_SOURCE 200809L

// handoff 層的取件與釋放，以及兩個 to_string。
// 彙整在 handoff_aggregate.cpp、投遞在 handoff_deliver.cpp；路徑推導與低階檔案
// 存取在 handoff_fs.hpp／.cpp。
// 只依賴 inst＋format：不印訊息、不執行 instruction。

#include <aos/inst.hpp>

#include "handoff_fs.hpp"
#include "handoff_issue.hpp"

#include <cerrno>
#include <cstdio>
#include <string>

#include <sys/stat.h>
#include <unistd.h>

namespace aos {
namespace {

using detail::sync_directory;

}  // namespace

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
        if (error == ENOENT) {
            // 兩層對「存在」的定義必須對齊（#25）：aggregate 的第 ⓪ 步用 lstat
            // （不跟隨 symlink），這裡用 open（跟隨）。一個斷掉的 symlink 會讓
            // aggregate 判定「已有一批等著取」而不發布、claim 卻回 NoInstruction
            // ——夾出一個規格沒定義的第三態「存在但永遠取不走」，世界無聲卡死。
            // lstat 成功＝base 確實存在，只是讀不到：回 InstructionReadFailed，
            // 讓 CLI 回 1 並把原因噴出來。
            struct stat link_status {};
            if (lstat(paths.base.c_str(), &link_status) != 0) {
                return HandoffState::NoInstruction;
            }
            result.path = paths.base;
            result.error = ENOENT;
            return HandoffState::InstructionReadFailed;
        }
        result.path = paths.base;
        result.error = error;
        return HandoffState::InstructionReadFailed;
    }
    if (rename(paths.base.c_str(), paths.runi.c_str()) != 0) {
        result.path = paths.base;
        result.error = errno;
        return HandoffState::RenameFailed;
    }
    // §D-5 的耐久性同樣拘束取件：`.runi` 存在 ⟺ 有一回合沒跑完（§D-7），這個
    // 等價關係要成立，這一次 rename 就必須落盤——否則斷電後 `.runi` 回退成
    // `inst.json`，副作用已經發生的那一批會被整批重跑一次（#2）。
    sync_directory(detail::parent_directory(paths.base), result);
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
    // 釋放同受 §D-5 拘束（#5）。這一步過去只是「剛好」被 CLI 的 advance_turn
    // 順帶 fsync 到——§B-3 說 turn 在 M2 要搬到 loop 層，搬走那個巧合就沒了，
    // 而 `.runi` 復活代表每次 aos exec 都回 3、世界永久卡死。自己補上，不留巧合。
    sync_directory(detail::parent_directory(paths.runi), result);
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
    case HandoffIssueKind::DeliveryNotRegular: return "DeliveryNotRegular";
    case HandoffIssueKind::DeliveryNameIgnored: return "DeliveryNameIgnored";
    }
    return "Unknown";
}

}  // namespace aos
