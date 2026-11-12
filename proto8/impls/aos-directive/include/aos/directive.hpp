// aos/directive.hpp：指示詞（語法糖：把設定拆成小檔、讀環境變數）（N-45，10-20 改版）。
// resolve_keys：先解析單層，再完整解析呼叫者指定、自己讀的欄位，保留各欄位的相對路徑起點。
//
// 解 JSON 時找出所有帶 $ref 或 $env 的物件，整個物件換成它指到的值；物件裡其餘東西不管（10-20 ideas D12）：
//   {"$ref": "檔"}                  那份 JSON 檔的整份內容（第一行 #! 跳過），換進來的值接著解
//   {"$ref": "檔#/a/b"}             檔內那個位置（JSON pointer，RFC 6901）；位置只認 #/（10-23 使用者「把$at刪掉，就都只認#/。」）
//   {"$ref": "#/a/b"}               寫著這個 $ref 的那份檔自己裡的 /a/b（11-12 使用者「ref應該支援#/開頭吧」）；
//                                   那份檔＝RefBase::file（被 $ref 進來的檔裡＝那份檔自己）；不知道是哪份檔（file 空）＝原封不動留著
//   {"$ref": ["a.json", "b.json#/c"]}  陣列（10-23 使用者）：幾份照順序合成一份——都是物件＝合 key（同名後面的蓋前面的，淺層）、
//                                   都是陣列＝接起來、種類混在一起＝DirectiveBad；每個元素寫法同上；
//                                   只有一份＝它本身；空陣列、有一個元素不是合格的字串＝寫法不合（整個物件原封不動）
//   {"$env": "NAME"}                環境變數的值
// 同一物件兩個都寫只看 $ref。換出來的值是字串時：有 "$path" 就照字串接上去（10-21 傍晚起，原 os.path.join），再在前面加 "$prefix"（D9、D10）；
// 不是字串就靜默不作用（D11）。修飾詞都帶 $：舊的 "path" 已改名 $path，沒帶 $ 的寫了是普通 key、不作用；$at（10-23 刪）寫了是不認得的 $xxx、不管。
//
// 錯分兩類（D13～D15）：
//   真的解不開＝丟 aos::Error{DirectiveBad}：環境變數沒設、$ref 的檔讀不到（含不是 JSON）、指標指不到、繞圈（同一個檔＋指標）。
//   寫法（格式）寬容、不報錯：不認得的 $xxx（含 $fmt）與其餘 key 不管；$path、$prefix 不是字串＝當沒寫；
//   $ref／$env 的值不是非空字串（$ref 也可以是非空的字串陣列）、
//   $ref 的 # 後面不是 /、只有 #/… 卻不知道寫著它的是哪份檔＝換不了，整個物件原封不動留著。
//
// 相對檔名：doc 本身裡的 $ref 從 base 的 dir 算；被 $ref 進來的檔裡的 $ref，從那個檔（解開捷徑後）所在的資料夾算。
// 檔名部分可以寫 ./、../（接到起點後整理，11-12 確認）；# 後面是 JSON pointer、沒有 ..。
// 指標取的是檔的原文（不穿過裡面的 $ref），取到的值再接著解。
#pragma once

#include "aos/util/error.hpp"
#include "aos/util/io.hpp"

#include <filesystem>
#include <string>
#include <unordered_map>
#include <vector>

namespace aos {

namespace code {
inline constexpr const char* DirectiveBad = "DirectiveBad"; // 指示詞解不開：變數沒設、讀不到、指不到、繞圈
}  // namespace code

// 相對 $ref 的起點（11-12）：dir＝相對檔名從哪個資料夾算；file＝寫著這些 $ref 的那份檔（`#/…` 開頭的 $ref 取它的原文），
// 空＝不知道（stdin、行程內給的 JSON），`#/…` 開頭的 $ref 原封不動留著。只給資料夾（字串、路徑）＝file 空。
// 轉成字串＝dir（呼叫者拿起點去接路徑時用）。
struct RefBase {
    std::string dir;
    std::string file;
    RefBase() = default;
    RefBase(std::string d, std::string f = "") : dir(std::move(d)), file(std::move(f)) {}
    RefBase(const char* d) : dir(d) {}
    RefBase(const std::filesystem::path& d) : dir(d.string()) {}
    operator const std::string&() const { return dir; }
};

// 解掉 doc 裡所有指示詞，回新的值（原本那份不動）。base＝doc 裡相對 $ref 的起點（與寫著它的那份檔）。
Json resolve(const Json& doc, const RefBase& base);

// 只換這一格（10-23 晚：aos 讀的 JSON 都解指示詞，但每支程式只解自己讀的那幾格，C-52）：v 本身是指示詞就換成它指到的值，
// 換來的又是指示詞就再換；**不往物件、陣列裡面走**（裡面的指示詞原封不動，留給讀那幾格的人）。
// 回換好的值，與「它裡面相對 $ref 的起點」：換過 $ref＝最後那份檔（解開捷徑後）所在的資料夾與那份檔；沒換、或換的是 $env＝base。
// 呼叫者往下讀某一格時，拿這個起點對那一格再呼叫 resolve_shallow 或 resolve。錯同 resolve（DirectiveBad）。
// $ref 陣列合出來的值，每個 key（物件）／元素（陣列）各自來自不同的檔：起點記在 key_dirs／item_dirs，用 dir_of 取。
struct Resolved {
    Json value;
    RefBase base_dir;                                    // value 裡相對 $ref 的起點（資料夾＋那份檔）
    std::unordered_map<std::string, RefBase> key_dirs;   // 合物件時：key → 它來自的那份檔的起點
    std::vector<RefBase> item_dirs;                      // 接陣列時：第 i 個元素 → 它來自的那份檔的起點
    const RefBase& dir_of(const std::string& key) const;   // value 那個 key 裡相對 $ref 的起點
    const RefBase& dir_of(size_t i) const;                 // value 第 i 個元素裡相對 $ref 的起點
};
Resolved resolve_shallow(const Json& v, const RefBase& base);

// 整份先換一層，再完整解開指定的 key；保留每個 key 原本的相對路徑起點。
Resolved resolve_keys(const Json& doc, const RefBase& base, const std::vector<std::string>& keys);

}  // namespace aos
