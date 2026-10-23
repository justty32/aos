// aos/files.hpp：【aos-util】檔案的小工具——路徑、讀檔、原子寫入。loop 的 ctl／state 窗、daemon 的 table 窗、回覆檔都用這組。
//
//   abspath / dirname / join   路徑（照 Python 的 os.path.abspath、dirname、join）
//   read_file / read_json      讀整個檔；read_json 讀不了或不是 JSON＝nullopt
//   write_json                 先寫暫存檔、再改名蓋過去（原子寫入，見 files.cpp 的說明）
//   split_hash / read_json_at  入口路徑的 JSON 尋址：`檔#/指標` 拆成兩半；讀檔（跳過第一行 #!）再照指標取值
// （讀 JSON 串流用 aos/io.hpp 的 read_stream。）
// 對應 Python aos_ctl_state.py 的 write_json。
#pragma once

#include "aos/io.hpp"

#include <optional>
#include <string>
#include <vector>

namespace aos {

// 絕對路徑，順便整理掉 `.`、`..`、重複的 `/`（Python 的 os.path.abspath）。
std::string abspath(const std::string& path);

// 上一層資料夾（Python 的 os.path.dirname）。
std::string dirname(const std::string& path);

// b 是絕對路徑就用 b，不然接在 a 後面（Python 的 os.path.join）。
std::string join(const std::string& a, const std::string& b);

// 讀整個檔。讀不了回 nullopt，errno_out＝原因（ENOENT＝不存在）。
std::optional<std::string> read_file(const std::string& path, int& errno_out);

// 讀一份 JSON 檔。讀不了、不是合法 JSON 都回 nullopt。
std::optional<Json> read_json(const std::string& path);

// 原子寫入：先寫同資料夾的 `.名字.tmp`、再改名蓋過去；所在的資料夾沒有就建。
// 成功回 nullopt；失敗回原因（白話），暫存檔清掉。排版同 Python json.dump(indent=2)。
std::optional<std::string> write_json(const std::string& path, const Json& doc);

// `檔#/指標` 拆成兩半（ideas 10-19 § 19：入口路徑的 JSON 尋址，指標照 RFC 6901 JSON pointer）。
// 第一個 `#` 就切（不支援檔名含 `#`）；沒有 `#`＝pointer 空。有 `#` 但後面不是 `/` 開頭（`檔#`、`檔#key`）
// 丟 Error{FieldType}（呼叫者要自己的代號就接住換掉）。
struct Spec {
    std::string path;
    std::string pointer;
};
Spec split_hash(const std::string& spec);

// 讀一份 JSON 檔，再照 pointer 取值（pointer 空＝整份）。第一行是 `#!`（shebang）就當空行跳過。
// 讀不到丟 Error{ReadFailed}、不是 JSON 丟 Error{JsonSyntax}、指標寫壞或指不到丟 Error{FieldType}。
Json read_json_at(const std::string& path, const std::string& pointer);

}  // namespace aos
