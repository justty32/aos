// doc.hpp：【doc】一份 JSON 檔怎麼讀、怎麼照原樣寫回去，與 `檔#/指標` 的尋址。
//
//   splice.cpp   splice：寫回去時只重寫有變的那一塊，其他原文不動
//   file.cpp     load_file（記下 #! 行、縮排、結尾換行、權限）／save_file（原子寫入：先寫 `.名字.<pid>.tmp` 再改名，N-05）
//   pointer.cpp  parse_spec（`檔#/指標` 拆開）、指標的拆／接（RFC 6901）、往下一格 child、印給人看的位置 shown
#pragma once

#include "common/common.hpp"

#include <map>
#include <optional>
#include <string>
#include <vector>

#include <sys/types.h>

namespace aos::json {

// 一份 JSON 檔與寫回去要照的排版。
struct File {
    std::string given;           // 使用者給的路徑，整理成絕對路徑（沒解開捷徑）
    std::string real;            // 實際的檔（realpath，捷徑解開；不在＝given）。寫回去寫這個，捷徑本身不動
    bool exists = false;
    std::string shebang;         // 第一行是 #! 就整行留著（含換行），寫回去照放
    Json doc;
    std::string body;            // 讀進來時 #! 之後的原文（splice 照它只改變的那一塊）
    bool one_line = false;       // 原本整份寫在一行＝寫回去也一行（", "、": "，同 aos 的 dumps）
    int indent = 2;              // 多行時每層幾個 indent_char（看第一個有縮排的行）
    char indent_char = ' ';
    bool final_newline = true;   // 原本結尾有沒有換行
    mode_t mode = 0;             // 原本的權限（寫回去照設；新檔＝0666 扣 umask）
};

// 讀一份檔。allow_missing＝不在也行（回 exists＝false、doc＝null、排版用預設）。
// 不在 FileMissing；讀不了（含資料夾）、不是 JSON FileBad。
File load_file(const std::string& path, bool allow_missing);

// body 照 doc 重寫：先試 splice（比 before 只重寫有變的那一塊，其他原文不動），不行（或還沒有 body＝新檔）才照記下的排版整份重排。
std::string render_body(const File& f, const Json& before);

// 把 shebang＋body 寫回 real（呼叫者先用 render_body 更新 body）。原子：同資料夾先寫 `.名字.<pid>.tmp`、設權限、fsync、
// 再 rename 蓋過去。失敗 WriteFailed（暫存檔清掉）。
void save_file(const File& f);

// 只重寫有變的那一塊（splice.cpp 開頭有說明）；做不到回 nullopt。
std::optional<std::string> splice(const File& f, const Json& before, const Json& after);

// 讀過的檔都留在這（同一個檔只讀一次；改完一起寫）。key＝real。
struct Docs {
    std::map<std::string, File> files;
    File& open(const std::string& path, bool allow_missing);   // 讀（或拿已經讀過的）；path 可以是相對 cwd
};

// `檔#/指標`。
struct Spec {
    std::string file;
    std::vector<std::string> toks;   // 指標拆好、~0 ~1 已還原；空＝整份
};
Spec parse_spec(const std::string& s);   // # 後面不是 /＝SpecBad；檔名空＝SpecBad

std::vector<std::string> split_pointer(const std::string& ptr);   // "" → {}；"/a/b" → {"a","b"}
std::string pointer_of(const std::vector<std::string>& toks);       // 反過來（跳脫 ~ /）

// 往下一格：物件看 key、陣列看索引（不收前導 0、不收 "-"，同 aos-directive）。沒有＝nullptr。
Json* child(Json& node, const std::string& tok);
bool is_index(const std::string& tok, size_t size);

// 印給人看的位置：檔在 cwd 底下就印相對路徑、否則絕對路徑；有指標就接 #/…（跟 $ref 同一種寫法）。
std::string shown(const std::string& real, const std::vector<std::string>& toks);

}  // namespace aos::json
