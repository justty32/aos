#pragma once

// handoff 層內部標頭：不對外，只給 handoff*.cpp 看。
// 這裡只有「路徑推導」與「低階檔案存取」，不碰 HandoffResult、不做交接決策。
// handoff 只依賴 inst＋format，這個檔連 format 都不需要。

#include <string>

namespace aos::detail {

// 從 instruction 路徑（必須以 .json 結尾）推導出來的四個位置。
struct HandoffPaths {
    std::string base;   // 發佈好、等待取件的 instruction
    std::string temp;   // 原子發佈用的暫存檔（.temp）
    std::string runi;   // 取件後的執行中標記（.runi）
    std::string inbox;  // 投遞收件匣目錄（.tempd）
};

// base 不以 .json 結尾就回 false，paths 不動。
bool derive_paths(const std::string &base, HandoffPaths &paths);

// EINTR-safe 的整檔讀寫；失敗時把 errno 寫進 error。
bool read_file(const std::string &path, std::string &buffer, int &error);
bool write_file(const std::string &path, const std::string &data, int &error);

// 收件匣裡算數的投遞檔名：有副檔名、不以點開頭、且副檔名部分正好是 .json。
// （所以 foo.json.bad 之類的隔離檔會被忽略。）
bool is_delivery_name(const std::string &name);

std::string join_path(const std::string &directory, const std::string &name);

}  // namespace aos::detail
