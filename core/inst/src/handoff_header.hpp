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

// 四欄位 header 文件（§C-8）：version／id／origin／result，尾端一個 LF。
std::string encode_header(const std::string &id);

// 只抽出 id 欄（去重要用的就這一欄；其餘三欄由 loop 於 M2 認領）。
// 定點解析、不進 JSON 函式庫：認得的就是自己寫出去的那個版面。找不到或格式不認得
// 就回 false，呼叫端一律視同「沒有 header」。
bool decode_header_id(const std::string &document, std::string &id);

}  // namespace aos::detail
