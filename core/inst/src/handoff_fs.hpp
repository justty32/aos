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
// write_file 在 close 前 fsync(fd)：內容落盤後才算寫成功，fsync 失敗視同寫入失敗。
bool read_file(const std::string &path, std::string &buffer, int &error);
bool write_file(const std::string &path, const std::string &data, int &error);

// EINTR-safe：open(path, O_DIRECTORY) → fsync → close。用來在 rename 之後把目錄項
// 的變更落盤（rename 落盤與否，看的是目錄的 fsync，不是檔案本身的）。
bool fsync_dir(const std::string &path, int &error);

// 排他發布：把 from rename 成 to，to 已存在時失敗、不覆蓋（error 為 EEXIST）。
// 優先走 renameat2(RENAME_NOREPLACE)；檔案系統不支援時（EINVAL/ENOSYS/ENOTSUP）
// 退階為 link(from, to) + unlink(from)——link 沿用同一套「已存在就失敗」語意，
// 退階路徑的 unlink 失敗一律視為整體失敗（呼應 write_file 對 close 失敗的處理：
// 收尾步驟失敗，就不算數），供呼叫者判斷是否需要重試或改用新名字。
// aggregate 既有的覆蓋語意 rename 不用這個 helper，維持原樣。
bool publish_exclusive(const std::string &from, const std::string &to, int &error);

// 投遞唯一名（裁-1 格式）："<pid>-<seq>"，不含副檔名、不含點；seq 是行程內單調遞增
// 的計數（static atomic），只保證同一行程內不重複——pid 重用造成的跨行程撞名由
// publish_exclusive 兜底（EEXIST 時呼叫者換名重試）。
std::string next_delivery_name();

// 收件匣裡算數的投遞檔名：有副檔名、不以點開頭、且副檔名部分正好是 .json。
// （所以 foo.json.bad 之類的隔離檔會被忽略。）
bool is_delivery_name(const std::string &name);

std::string join_path(const std::string &directory, const std::string &name);

}  // namespace aos::detail
