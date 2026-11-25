// util/files.hpp: path helpers, whole-file read and FILE#/POINTER splitting (trimmed copy of proto8 aos-util aos/util/files.hpp).
//
//   abspath / dirname / join   路徑（照 Python 的 os.path.abspath、dirname、join）
//   is_dir                     是不是資料夾（proto8 在 aos-util 的 dirs.cpp）
//   read_file                  讀整個檔
//   split_hash                 入口路徑的 JSON 尋址：`檔#/指標` 拆成路徑與指標兩半
// proto9: atomic writes, read_json, read_window, keep_bad, make_dir, names_in, move, remove_tree are not brought in.
#pragma once

#include "util/io.hpp"

#include <optional>
#include <string>

namespace aos {

// 絕對路徑，順便整理掉 `.`、`..`、重複的 `/`（Python 的 os.path.abspath）。
std::string abspath(const std::string& path);

// 上一層資料夾（Python 的 os.path.dirname）。
std::string dirname(const std::string& path);

// b 是絕對路徑就用 b，不然接在 a 後面（Python 的 os.path.join）。
std::string join(const std::string& a, const std::string& b);

bool is_dir(const std::string& path);

// 讀整個檔。讀不了回 nullopt，errno_out＝原因（ENOENT＝不存在）。
std::optional<std::string> read_file(const std::string& path, int& errno_out);

// `檔#/指標` 拆成兩半（ideas 10-19 § 19：入口路徑的 JSON 尋址，指標照 RFC 6901 JSON pointer）。
// 第一個 `#` 就切（不支援檔名含 `#`）；沒有 `#`＝pointer 空。有 `#` 但後面不是 `/` 開頭（`檔#`、`檔#key`）
// 丟 Error{CfgBad}（呼叫者要自己的代號就接住換掉）。
struct Spec {
    std::string path;
    std::string pointer;
};
Spec split_hash(const std::string& spec);

}  // namespace aos
