#pragma once

// handoff 層內部標頭：不對外，只給 handoff*.cpp 看。
// 這裡只有「路徑推導」與「低階檔案存取」，不碰 HandoffResult、不做交接決策。
// handoff 只依賴 inst＋format，這個檔連 format 都不需要。

#include <string>

#include <dirent.h>

namespace aos::detail {

// opendir 與 closedir 之間有會配置記憶體的操作（std::string、push_back），而
// 呼叫端不是 noexcept：例外穿出去時要保證 DIR* 與它的 fd 不洩漏。成功路徑仍然
// 顯式 close() 並檢查回傳值，guard 只在還沒顯式關掉時才收尾。
struct DirGuard {
    DIR *handle = nullptr;

    DirGuard() = default;
    DirGuard(const DirGuard &) = delete;
    DirGuard &operator=(const DirGuard &) = delete;
    ~DirGuard() {
        if (handle != nullptr) closedir(handle);
    }

    int close() {
        DIR *const closing = handle;
        handle = nullptr;
        return closedir(closing);
    }
};

// 從 instruction 路徑（必須以 .json 結尾）推導出來的四個位置。
// 彙整**不再**產生 `<base>.temp`：批寫進每行程唯一的暫存（unique_temp_path），
// 然後直接排他 rename 成 base。共用的固定槽位會讓兩個彙整者互相覆蓋對方寫進去的
// 批，於是 A 可能發布 B 的批、卻只清掉 A 自己看到的那幾份投遞——剩下的在下一輪
// 被重新彙整＝重複執行。所以這個 struct 沒有 temp 欄。
struct HandoffPaths {
    std::string base;   // 發佈好、等待取件的 instruction
    std::string runi;   // 取件後的執行中標記（.runi）
    std::string inbox;  // 投遞收件匣目錄（.tempd）
};

// base 不以 .json 結尾就回 false，paths 不動。
bool derive_paths(const std::string &base, HandoffPaths &paths);

// EINTR-safe 的整檔讀寫；失敗時把 errno 寫進 error。
// write_file 在 close 前 fsync(fd)：內容落盤後才算寫成功，fsync 失敗視同寫入失敗。
// error 保留**先發生**的那個 errno：close 只有在前面都還沒出錯時才有資格寫 error
// （否則回報的會是收尾那個比較沒用的錯，把真正的原因蓋掉）。
bool read_file(const std::string &path, std::string &buffer, int &error);
bool write_file(const std::string &path, const std::string &data, int &error);

// 與 write_file 相同（含 fsync），但用 O_EXCL 建檔：檔名已經被佔走就失敗
// （error 為 EEXIST）、絕不覆蓋既有內容。deliver 建自己的 `.temp` 用它——投遞的
// 檔名是自己挑的，撞到就該換一個，不是蓋掉別人寫到一半的投遞。
bool write_file_exclusive(const std::string &path, const std::string &data,
                          int &error);

// EINTR-safe：open(path, O_DIRECTORY) → fsync → close。用來在 rename 之後把目錄項
// 的變更落盤（rename 落盤與否，看的是目錄的 fsync，不是檔案本身的）。
bool fsync_dir(const std::string &path, int &error);

// 排他發布：把 from rename 成 to，to 已存在時失敗、不覆蓋（error 為 EEXIST）。
// 優先走 renameat2(RENAME_NOREPLACE)；檔案系統不支援時（EINVAL/ENOSYS/ENOTSUP）
// 退階為 link(from, to) + unlink(from)，link 沿用同一套「已存在就失敗」語意。
//
// 退階路徑的 unlink 失敗**不算失敗**：那時 to 已經連好、內容完整，回報失敗會讓
// 呼叫者以為沒成功而重做（生產者重投＝真的多出一份，見 handoff_deliver.cpp 自己
// 寫下的原則）。這種情況回 true，並把 unlink 的 errno 放進 *leftover_error——那是
// 「已完成、但留下一份 from 的殘骸要人處理」的警告，nullptr 就丟掉。
//
// 彙整的批發布（`.temp` → base）與投遞的隔離（→ `.bad`）都走這個 helper：
// §D-5 要求批發布 MUST 排他（目的檔已存在＝別的彙整者先發布了），§D-8 要求
// 絕不覆蓋既有 `.bad`（覆寫等同刪除）。
bool publish_exclusive(const std::string &from, const std::string &to, int &error,
                       int *leftover_error = nullptr);

// 行程內唯一的權杖（裁-1 格式）："<pid>-<seq>"，不含副檔名、不含點；seq 是行程內
// 單調遞增的計數（static atomic），只保證同一行程內不重複——pid 重用造成的跨行程
// 撞名由 publish_exclusive 兜底（EEXIST 時呼叫者換名重試）。
std::string next_unique_token();

// 投遞唯一名（§D-2）。與 next_unique_token 同一個計數器、同一個形狀。
std::string next_delivery_name();

// 每行程唯一的暫存路徑：把權杖插在最後一個 .json 之前，再接 .temp。
//   .aos/inst.json      → .aos/inst-4711-0.json.temp
//   .aos/inst-head.json → .aos/inst-head-4711-0.json.temp
// 這個形狀**刻意**符合 §B-1 的 `<名字>.<副檔名>.<狀況>` 文法（名字變成
// `inst-4711-0`），不是把權杖接在狀況字後面。§D-5：唯一名保證兩個彙整者不會共寫
// 同一個檔，寫完再以一次 rename 進固定的 `.temp` 槽位（那個槽位是 roll-forward
// 的錨）。
std::string unique_temp_path(const std::string &base);

// 同一套規則，狀況字換成 .bad：x.json → x-4711-3.json.bad。既有 `.bad` 撞名時
// 給隔離用的第二個名字（§D-8：絕不覆蓋既有 `.bad`）。
std::string unique_bad_path(const std::string &path);

// path 的所在目錄；沒有斜線回 "."、只有開頭斜線回 "/"。rename／unlink 之後要
// fsync 的就是這個目錄。
std::string parent_directory(const std::string &path);

// 收件匣裡算數的投遞檔名：不以點開頭，且**第一個**點之後的整段正好是 `.json`。
// 也就是說 `a.b.json`、`a..json`、`.hidden.json` 都不收——收的集合刻意維持原樣
// （改判定會改變收哪些檔），但彙整會對「以 .json 結尾卻不合這個形狀」的名字記一筆
// DeliveryNameIgnored 出聲，不再靜默（#10）。`foo.json.bad`／`.temp`／`.runi`
// 之類的狀況檔同樣不收，那是對的。
bool is_delivery_name(const std::string &name);

std::string join_path(const std::string &directory, const std::string &name);

}  // namespace aos::detail
