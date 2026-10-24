// follow.hpp：【follow】順著指標往下走，遇到指示詞要不要穿過去（--follow）；追 $ref 鏈記下走過哪些檔的哪些位置。
//
//   kind.cpp    認指示詞（寬容規則同 aos-directive：寫法不合＝不是指示詞、原封不動）、拆 $ref 的每一份
//   locate.cpp  locate：從 `檔#/指標` 往下走到底，回停在哪份檔的哪個位置、走過的每一站
//
// 為什麼不直接叫 aos-directive：它的公開介面只回「解好的值」（resolve）或「換一層的值＋起點」（resolve_shallow），
// 不回「這個值在哪份檔的哪個位置」——改檔要的是位置。所以這裡照它的規則（相對路徑從這一層的檔所在的資料夾算、
// 捷徑解開、讀檔跳 #!、指標取原文、繞圈＝同一個檔＋指標又出現、$ref 陣列同名後蓋前）自己走一遍；
// 值本身（get --resolve）還是交給 aos-directive 解。兩邊對不上的地方寫在 README「跟 aos-directive 的分工」。
#pragma once

#include "doc/doc.hpp"

#include <optional>
#include <utility>

namespace aos::json {

enum class Kind { Plain, Ref, Env, FormBad };   // FormBad＝帶 $ref／$env 但寫法不合（aos 會原封不動留著）

Kind kind_of(const Json& v);

// $ref 的每一份（檔, 指標原文）；kind_of(v) 要是 Ref。
std::vector<std::pair<std::string, std::string>> ref_parts(const Json& v);

// 走到哪了：哪份檔（real）、檔裡的哪個位置、那個值；base＝這一層相對 $ref 的起點
// （最外層＝給的檔所在的資料夾，沒解開捷徑，同 aos-loop 讀設定檔；被 $ref 進來的＝那份檔解開捷徑後的資料夾，同 aos-directive）。
struct Cursor {
    std::string file;
    std::string base;
    std::vector<std::string> toks;
    Json* node = nullptr;
};

// 正在走的 $ref 鏈（檔 real, 指標）：同一個又出現＝繞圈。
using Chain = std::vector<std::pair<std::string, std::string>>;

// 讀 $ref 的一份：從 base 算路徑、讀、照指標取原文。讀不到、不是 JSON、指不到、繞圈＝DirectiveBad（同 aos-directive）。
Cursor fetch(Docs& docs, const std::string& base, const std::string& path, const std::string& ptr, Chain& chain);

// 一路穿過單份的 $ref，直到不是 $ref（$ref 陣列＝TargetBad）。
Cursor settle(Docs& docs, Cursor c, Chain& chain);

struct Mode {
    bool follow = false;        // 路上遇到 $ref 就穿過去（改被參照的檔）
    bool follow_final = false;  // 走到的那個值本身是 $ref 也穿過去（set／append／merge --follow）
    bool strict = false;        // 寫：沒 --follow 時路上經過指示詞＝FollowMissing（往指示詞物件裡加 key，aos 不會看）
};

struct Located {
    Cursor at;                       // 停在哪
    std::vector<std::string> rest;   // 沒走完的指標（第一格就不在）；空＝走到了
    std::vector<Cursor> hops;        // 走過的每一站（每穿過一個 $ref 記一站，最後一站＝at）
    bool merged = false;             // 最後穿過的是 $ref 陣列（at 是合起來的其中一份：最後一份）
};

Located locate(Docs& docs, const Spec& spec, Mode mode);

}  // namespace aos::json
