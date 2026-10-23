// aos/directive.hpp：指示詞（語法糖：把設定拆成小檔、讀環境變數）。照 proto8/bin/aos_inst.py 的 resolve（N-45，10-20 改版）。
//
// 解 JSON 時找出所有帶 $ref 或 $env 的物件，整個物件換成它指到的值；物件裡其餘東西不管（10-20 ideas D12）：
//   {"$ref": "檔"}                  那份 JSON 檔的整份內容（第一行 #! 跳過），換進來的值接著解
//   {"$ref": "檔#/a/b"}             檔內那個位置（JSON pointer，RFC 6901）
//   {"$ref": "檔", "$at": "/a/b"}   同上；兩個都寫＝$at 接在 #/ 後面（D1、D7）
//   {"$env": "NAME"}                環境變數的值
// 同一物件兩個都寫只看 $ref。換出來的值是字串時：有 "$path" 就照 os.path.join 接，再在前面加 "$prefix"（D9、D10）；
// 不是字串就靜默不作用（D11）。修飾詞都帶 $：舊的 "path" 已改名 $path、10-23 起修飾 $ref 的位置叫 $at，沒帶 $ 的寫了是普通 key、不作用。
//
// 錯分兩類（D13～D15）：
//   真的解不開＝丟 aos::Error{DirectiveBad}：環境變數沒設、$ref 的檔讀不到（含不是 JSON）、指標指不到、繞圈（同一個檔＋指標）。
//   寫法（格式）寬容、不報錯：不認得的 $xxx（含 $fmt）與其餘 key 不管；$path、$prefix 不是字串＝當沒寫；
//   $at 不是字串、或不是空字串也不是 / 開頭＝當沒寫；$ref／$env 的值不是非空字串、$ref 的 # 後面不是 /、
//   只有 #/… 沒寫檔名＝換不了，整個物件原封不動留著。
//
// 相對檔名：doc 本身裡的 $ref 從 base_dir 算；被 $ref 進來的檔裡的 $ref，從那個檔（解開捷徑後）所在的資料夾算。
// 指標取的是檔的原文（不穿過裡面的 $ref），取到的值再接著解。
#pragma once

#include "aos/error.hpp"
#include "aos/io.hpp"

#include <filesystem>
#include <string>

namespace aos {

namespace code {
inline constexpr const char* DirectiveBad = "DirectiveBad"; // 指示詞解不開：變數沒設、讀不到、指不到、繞圈
}  // namespace code

// 解掉 doc 裡所有指示詞，回新的值（原本那份不動）。base_dir＝doc 裡相對 $ref 的基準。
// where 只為了相容舊呼叫（不再用到）。
Json resolve(const Json& doc, const std::filesystem::path& base_dir, const std::string& where = "<stdin>");

}  // namespace aos
