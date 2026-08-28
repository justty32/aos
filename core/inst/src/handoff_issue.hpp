#pragma once

// handoff 層內部標頭：不對外，只給 handoff*.cpp 看。
// 這裡是三個 handoff .cpp 共用的兩個小動作——記一筆 issue、rename／unlink 之後
// 把目錄項落盤。它們同時要碰 HandoffResult（公開型別）與 detail::fsync_dir
// （handoff_fs 的內部標頭），所以放不進 handoff_fs.hpp——那個檔刻意不認識
// HandoffResult，也不做交接決策。

#include <aos/inst.hpp>

#include "handoff_fs.hpp"

#include <string>

namespace aos::detail {

inline void add_issue(HandoffResult &result, HandoffIssueKind kind,
                      const std::string &path, InstState state, int error) {
    result.issues.push_back(HandoffIssue{kind, path, state, error});
}

// rename／unlink 之後把目錄項落盤（§D-5）。失敗只記 issue、**不改變控制流**：
// 目錄項本身已經換好了，少的是耐久性保證；為此讓整輪失敗只會把世界卡住，更糟。
// 回傳「有沒有真的落盤」——彙整用它決定該不該把 header 標成 swept（§C-8）。
inline bool sync_directory(const std::string &directory, HandoffResult &result) {
    int error = 0;
    if (fsync_dir(directory, error)) return true;
    add_issue(result, HandoffIssueKind::DirectorySyncFailed, directory,
              InstState::Ok, error);
    return false;
}

}  // namespace aos::detail
