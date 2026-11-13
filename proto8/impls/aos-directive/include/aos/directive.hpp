// aos/directive.hpp：指示詞（語法糖：把設定拆成小檔、讀環境變數）（N-45，10-20 改版）。
// resolve_keys：先解析單層，再完整解析呼叫者指定、自己讀的欄位，保留各欄位的相對路徑起點。
//
// 解 JSON 時找出所有帶 $ref 或 $env 的物件，整個物件換成它指到的值；物件裡其餘東西不管（10-20 ideas D12）。
// $ref 的路徑（11-13 晚使用者「他應該是以#作爲json內部尋址的標示」，thinking 2026-11/13/ref-path-rules；index 路徑同一套、
// Python 那份是 lib/aos_refpath.py，兩邊跑同一張 lib/tests/ref_path_cases.json）：# 左邊一律檔案系統、右邊一律 json 內部。
//   {"$ref": "x.json"}、"./x.json"、"../x.json"、"sub/x.json"   檔案系統，從寫著它的那份檔所在的資料夾算（RefBase::dir）；整份內容（第一行 #! 跳過），換進來的值接著解
//   {"$ref": "#/a/b"}               本檔根起算（RFC 6901，~1＝/、~0＝~；.. 不特別、是 key 名）；本檔＝RefBase::file
//   {"$ref": "#./b"}、"#../c"       從所在物件起算／所在物件的上一層（../.. 可連用，超出根＝DirectiveBad）；#.／#./＝所在物件、#..／#../＝上一層整個。
//                                   所在物件＝這個 {"$ref": …} 那一格的上一層（{"a": {"b": {"$ref": "#./x"}}} 的 #./x＝/a/x）；整份檔就是指示詞＝沒有所在物件＝DirectiveBad
//   {"$ref": "#"}、"#/"             本檔整份；"y.json#"、"y.json#/"＝y.json 整份；"y.json#/k"＝y.json 的 /k
//   "y.json#./…"、"y.json#../…"、"#aaa"、"y.json#aaa"、空字串   DirectiveBad
//   {"$ref": ["a.json", "b.json#/c"]}  陣列（10-23 使用者）：幾份照順序合成一份——都是物件＝合 key（同名後面的蓋前面的，淺層）、
//                                   都是陣列＝接起來、種類混在一起＝DirectiveBad；每個元素寫法同上（陣列不算一層）；空陣列、有一個元素不是字串＝寫法不合（原封不動）
//   {"$env": "NAME"}                環境變數的值
// 同一物件兩個都寫只看 $ref。換出來的值是字串時：有 "$path" 就照字串接上去（10-21 傍晚起，原 os.path.join），再在前面加 "$prefix"（D9、D10）；
// 不是字串就靜默不作用（D11）。修飾詞都帶 $：沒帶 $ 的 "path" 寫了是普通 key、不作用。
//
// 錯分兩類（D13～D15）：
//   丟 aos::Error{DirectiveBad}：路徑寫法不合（上表）、環境變數沒設、$ref 的檔讀不到（含不是 JSON、資料夾）、指標指不到、繞圈（同一個檔＋指標）。
//   原封不動、不報錯：不認得的 $xxx 與其餘 key 不管；$path、$prefix 不是字串＝當沒寫；$ref 不是字串或非空的字串陣列、$env 不是非空字串；
//   只有 #… 卻不知道寫著它的是哪份檔、#./／#../ 卻不知道這一格在檔裡哪裡（RefBase::placed 為 false）。
//
// 被 $ref 進來的檔裡的 $ref，從那個檔（解開捷徑後）所在的資料夾算、所在物件照它在那份檔裡的位置。
// 指標取的是檔的原文（不穿過裡面的 $ref），取到的值再接著解。
#pragma once

#include "aos/util/error.hpp"
#include "aos/util/io.hpp"

#include <filesystem>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

namespace aos {

namespace code {
inline constexpr const char* DirectiveBad = "DirectiveBad"; // 指示詞解不開：變數沒設、讀不到、指不到、繞圈
}  // namespace code

// 相對 $ref 的起點：dir＝檔案系統相對路徑從哪個資料夾算；file＝寫著這些 $ref 的那份檔（`#…` 指它），空＝不知道（stdin、行程內給的 JSON）；
// at＝正在解的這個值在 file 裡的位置（RFC 6901 token，跳脫後的樣子；空＝根），placed＝知不知道 at（11-13 #./、#../ 要用）。
// 給了 file 就當它是那份檔的根（placed、at 空）；只給一段子樹的呼叫者要自己填 at。只給資料夾（字串、路徑）＝file 空、不知道位置。
// 轉成字串＝dir（呼叫者拿起點去接路徑時用）。in(key)／in(i)＝往下一格（往下走時一路帶著位置）。
struct RefBase {
    std::string dir;
    std::string file;
    std::vector<std::string> at;
    bool placed = false;
    RefBase() = default;
    RefBase(std::string d, std::string f = "") : dir(std::move(d)), file(std::move(f)), placed(!file.empty()) {}
    RefBase(std::string d, std::string f, std::vector<std::string> a) : dir(std::move(d)), file(std::move(f)), at(std::move(a)), placed(true) {}
    RefBase(const char* d) : dir(d) {}
    RefBase(const std::filesystem::path& d) : dir(d.string()) {}
    operator const std::string&() const { return dir; }
    RefBase in(const std::string& key) const;
    RefBase in(size_t i) const;
};

// 「字串→位置」：$ref 裡寫的一個字串 → 哪份檔（接上起點、整理過；還沒解開捷徑）的哪個指標（RFC 6901，空＝整份）。只看字面、不讀檔。
// base.at＝這個 {"$ref": …} 在檔裡的位置（所在物件＝它的上一層）。寫法不合＝丟 DirectiveBad；算不出來（不知道檔／位置）＝nullopt。
// aos-directive 自己與 aos-json 的 --follow、ref --move 都用這一支；Python（lib/aos_refpath.py，$ref 與 index 共用）跑同一張表。
struct RefSpot {
    std::string file;
    std::string pointer;
};
std::optional<RefSpot> ref_spot(const std::string& spec, const RefBase& base);

// RFC 6901 指標字串（"" 或 "/a/b"）↔ token（跳脫後的樣子）；key → token（~ 寫 ~0、/ 寫 ~1）。
std::vector<std::string> pointer_tokens(const std::string& ptr);
std::string token_of(const std::string& key);

// 解掉 doc 裡所有指示詞，回新的值（原本那份不動）。base＝doc 裡相對 $ref 的起點（與寫著它的那份檔）。
Json resolve(const Json& doc, const RefBase& base);

// 只換這一格（10-23 晚：aos 讀的 JSON 都解指示詞，但每支程式只解自己讀的那幾格，C-52）：v 本身是指示詞就換成它指到的值，
// 換來的又是指示詞就再換；**不往物件、陣列裡面走**（裡面的指示詞原封不動，留給讀那幾格的人）。
// 回換好的值，與「它裡面相對 $ref 的起點」：換過 $ref＝最後那份檔（解開捷徑後）所在的資料夾與那份檔；沒換、或換的是 $env＝base。
// 呼叫者往下讀某一格時，拿這個起點對那一格再呼叫 resolve_shallow 或 resolve。錯同 resolve（DirectiveBad）。
// $ref 陣列合出來的值，每個 key（物件）／元素（陣列）各自來自不同的檔：起點記在 key_dirs／item_dirs，用 dir_of 取。
struct Resolved {
    Json value;
    RefBase base_dir;                                    // value 的起點（資料夾＋那份檔＋value 在那份檔裡的位置）
    std::unordered_map<std::string, RefBase> key_dirs;   // 合物件時：key → 它來自的那份檔的起點（位置已接上 key）
    std::vector<RefBase> item_dirs;                      // 接陣列時：第 i 個元素 → 它來自的那份檔的起點（位置已接上原本的索引）
    RefBase dir_of(const std::string& key) const;   // value 那個 key 的起點（位置已接上那個 key）
    RefBase dir_of(size_t i) const;                 // value 第 i 個元素的起點（位置已接上那個索引）
};
Resolved resolve_shallow(const Json& v, const RefBase& base);

// 整份先換一層，再完整解開指定的 key；保留每個 key 原本的相對路徑起點。
Resolved resolve_keys(const Json& doc, const RefBase& base, const std::vector<std::string>& keys);

}  // namespace aos
