#pragma once

// handoff 層內部標頭：不對外，只給 handoff*.cpp 看。
// 這裡是批 header sidecar（SPEC §C-8 四欄位）與批 id（§D-6）的編碼／解碼／摘要，
// 全部是純字串運算：不碰檔案系統、不做交接決策。
// header 的四個欄位都是受控常量或 hex 字串，與 instruction schema 無關，所以刻意
// 不經過格式層（格式層是唯一懂 inst schema 的層，header 不是 inst）。

#include <cstdint>
#include <string>

namespace aos::detail {

// header sidecar 的兩個位置：<名字>-head.json 與發布用的 <名字>-head.json.temp。
struct HeaderPaths {
    std::string base;
    std::string temp;
};

// base 不以 .json 結尾就回 false、paths 不動（與 derive_paths 同一套約定）。
bool derive_header_paths(const std::string &base, HeaderPaths &paths);

// 批 id（§D-6）：64-bit FNV-1a，輸入是排序後每份投遞的「檔名 '\0' 內容 '\0'」串接，
// 輸出 16 位小寫 hex。摘要吃的是投遞**檔名**而不是完整路徑——世界整包可搬（§E-1），
// id 不該跟著搬家變。同一組投遞（同名同內容、恰好整組）算出同一個 id，這就是去重的
// 依據，所以不另存投遞名冊（manifest 是 v2 的事）。
class BatchDigest {
public:
    void add(const std::string &name, const std::string &content);
    std::string id() const;

private:
    std::uint64_t state_ = 0xcbf29ce484222325ULL;  // FNV-1a 64-bit offset basis
};

// 五欄位 header 文件（§C-8）：version／id／origin／result／swept，尾端一個 LF。
// swept 是去重的閘門：發布時寫 false，投遞全數刪除且目錄落盤之後改寫成 true。
std::string encode_header(const std::string &id, bool swept);

// 從 header 讀出去重要用的兩個欄位。其餘三欄由 loop 於 M2 認領。
struct HeaderFields {
    std::string id;
    bool swept = false;  // 缺欄（舊世界的 header）＝ false，見 §C-8
};

// 只採**頂層**的 id 與 swept：巢狀物件、陣列元素、字串值裡長得像 `"id"` 的位元組
// 一律不算數（#4——§C-8 的 result 欄在 M2 會被填成物件，裡面很可能有自己的 id）。
// 最小的頂層物件掃描器，不進 JSON 函式庫：期待 `{`，然後反覆「字串 key → `:` →
// 值 → `,` 或 `}`」；字串值正確跳過跳脫序列，物件／陣列用深度計數跳過。
//
// 讀不懂就回 false ＝「視同沒有 header」：不是合法的頂層物件、沒有頂層 id、
// id 不是字串、值裡有跳脫序列（我們自己寫出去的不含跳脫）都算讀不懂。這個失效
// 方向是刻意的——往「多跑一次」倒，不往「吃掉投遞」倒。
bool decode_header(const std::string &document, HeaderFields &fields);

}  // namespace aos::detail
