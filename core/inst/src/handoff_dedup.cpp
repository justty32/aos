#define _POSIX_C_SOURCE 200809L

// handoff 層：SPEC §D-6「批 id 與去重」的檔案系統面。介面與理由見 handoff_dedup.hpp。
// 只依賴 inst＋format：不印訊息、不執行 instruction。

#include "handoff_dedup.hpp"

#include "handoff_fs.hpp"
#include "handoff_issue.hpp"

#include <algorithm>
#include <cerrno>
#include <cstddef>
#include <cstdio>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include <dirent.h>
#include <unistd.h>

namespace aos::detail {

bool current_header(const std::string &path, HeaderFields &fields,
                    HandoffResult &result) {
    std::string document;
    int error = 0;
    if (!read_file(path, document, error)) {
        if (error != ENOENT) {
            add_issue(result, HandoffIssueKind::HeaderInvalid, path,
                      InstState::Ok, error);
        }
        return false;
    }
    if (!decode_header(document, fields)) {
        add_issue(result, HandoffIssueKind::HeaderInvalid, path, InstState::Ok,
                  0);
        return false;
    }
    return true;
}

bool find_rollforward_anchor(const std::string &directory,
                             const std::string &stem, const std::string &output,
                             std::string &anchor) {
    DirGuard guard;
    guard.handle = opendir(directory.c_str());
    if (guard.handle == nullptr) return false;

    const std::string prefix = stem + "-";
    const std::string header_prefix = stem + "-head-";
    constexpr std::string_view suffix = ".json.temp";
    std::vector<std::string> candidates;
    while (dirent *entry = readdir(guard.handle)) {
        std::string name = entry->d_name;
        if (name.size() <= prefix.size() + suffix.size()) continue;
        if (name.compare(0, prefix.size(), prefix) != 0) continue;
        if (name.compare(0, header_prefix.size(), header_prefix) == 0) continue;
        if (name.compare(name.size() - suffix.size(), suffix.size(), suffix) !=
            0) {
            continue;
        }
        candidates.push_back(std::move(name));
    }
    std::sort(candidates.begin(), candidates.end());

    for (const std::string &name : candidates) {
        const std::string path = join_path(directory, name);
        std::string committed;
        int error = 0;
        if (read_file(path, committed, error) && committed == output) {
            anchor = path;
            return true;
        }
    }
    return false;
}

void mark_header_swept(const HeaderPaths &header, const std::string &id,
                       const std::string &directory, HandoffResult &result) {
    const std::string temp = unique_temp_path(header.base);
    int error = 0;
    if (!write_file(temp, encode_header(id, true), error)) {
        add_issue(result, HandoffIssueKind::HeaderWriteFailed, temp,
                  InstState::Ok, error);
        unlink(temp.c_str());
        return;
    }
    if (rename(temp.c_str(), header.base.c_str()) != 0) {
        add_issue(result, HandoffIssueKind::HeaderWriteFailed, header.base,
                  InstState::Ok, errno);
        unlink(temp.c_str());
        return;
    }
    sync_directory(directory, result);
}

}  // namespace aos::detail
