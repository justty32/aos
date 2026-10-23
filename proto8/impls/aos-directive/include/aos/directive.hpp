// aos/directive.hpp：指示詞（語法糖：把設定拆成小檔、讀環境變數）（N-45，10-20 改版）。
//
// 解 JSON 時找出所有帶 $ref 或 $env 的物件，整個物件換成它指到的值；物件裡其餘東西不管（10-20 ideas D12）：
//   {"$ref": "檔"}                  那份 JSON 檔的整份內容（第一行 #! 跳過），換進來的值接著解
//   {"$ref": "檔#/a/b"}             檔內那個位置（JSON pointer，RFC 6901）
//   {"$ref": "檔", "$at": "/a/b"}   同上；兩個都寫＝$at 接在 #/ 後面（D1、D7）
//   {"$ref": ["a.json", "b.json#/c"]}  陣列（10-23 使用者）：幾份照順序合成一份——都是物件＝合 key（同名後面的蓋前面的，淺層）、
//                                   都是陣列＝接起來、種類混在一起＝DirectiveBad；每個元素寫法同上，$at 接在每一份的指標後面；
//                                   只有一份＝它本身；空陣列、有一個元素不是合格的字串＝寫法不合（整個物件原封不動）
//   {"$env": "NAME"}                環境變數的值
// 同一物件兩個都寫只看 $ref。換出來的值是字串時：有 "$path" 就照字串接上去（10-21 傍晚起，原 os.path.join），再在前面加 "$prefix"（D9、D10）；
// 不是字串就靜默不作用（D11）。修飾詞都帶 $：舊的 "path" 已改名 $path、10-23 起修飾 $ref 的位置叫 $at，沒帶 $ 的寫了是普通 key、不作用。
//
// 錯分兩類（D13～D15）：
//   真的解不開＝丟 aos::Error{DirectiveBad}：環境變數沒設、$ref 的檔讀不到（含不是 JSON）、指標指不到、繞圈（同一個檔＋指標）。
//   寫法（格式）寬容、不報錯：不認得的 $xxx（含 $fmt）與其餘 key 不管；$path、$prefix 不是字串＝當沒寫；
//   $at 不是字串、或不是空字串也不是 / 開頭＝當沒寫；$ref／$env 的值不是非空字串（$ref 也可以是非空的字串陣列）、
//   $ref 的 # 後面不是 /、只有 #/… 沒寫檔名＝換不了，整個物件原封不動留著。
//
// 相對檔名：doc 本身裡的 $ref 從 base_dir 算；被 $ref 進來的檔裡的 $ref，從那個檔（解開捷徑後）所在的資料夾算。
// 指標取的是檔的原文（不穿過裡面的 $ref），取到的值再接著解。
#pragma once

#include "aos/error.hpp"
#include "aos/io.hpp"

#include <filesystem>
#include <string>
#include <unordered_map>
#include <vector>

namespace aos {

namespace code {
inline constexpr const char* DirectiveBad = "DirectiveBad"; // 指示詞解不開：變數沒設、讀不到、指不到、繞圈
}  // namespace code

// 解掉 doc 裡所有指示詞，回新的值（原本那份不動）。base_dir＝doc 裡相對 $ref 的基準。
// where 只為了相容舊呼叫（不再用到）。
Json resolve(const Json& doc, const std::filesystem::path& base_dir, const std::string& where = "<stdin>");

// 只換這一格（10-23 晚：aos 讀的 JSON 都解指示詞，但每支程式只解自己讀的那幾格，C-52）：v 本身是指示詞就換成它指到的值，
// 換來的又是指示詞就再換；**不往物件、陣列裡面走**（裡面的指示詞原封不動，留給讀那幾格的人）。
// 回換好的值，與「它裡面相對 $ref 的起點」：換過 $ref＝最後那份檔（解開捷徑後）所在的資料夾；沒換、或換的是 $env＝base_dir。
// 呼叫者往下讀某一格時，拿這個起點對那一格再呼叫 resolve_shallow 或 resolve。錯同 resolve（DirectiveBad）。
// $ref 陣列合出來的值，每個 key（物件）／元素（陣列）各自來自不同的檔：起點記在 key_dirs／item_dirs，用 dir_of 取。
struct Resolved {
    Json value;
    std::string base_dir;
    std::unordered_map<std::string, std::string> key_dirs;   // 合物件時：key → 它來自的那份檔的起點
    std::vector<std::string> item_dirs;                      // 接陣列時：第 i 個元素 → 它來自的那份檔的起點
    const std::string& dir_of(const std::string& key) const;   // value 那個 key 裡相對 $ref 的起點
    const std::string& dir_of(size_t i) const;                 // value 第 i 個元素裡相對 $ref 的起點
};
Resolved resolve_shallow(const Json& v, const std::filesystem::path& base_dir);

}  // namespace aos
