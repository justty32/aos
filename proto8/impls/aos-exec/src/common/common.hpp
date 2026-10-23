// common.hpp：【common】aos-exec 好幾個元素都用到的：型別別名、entry_name()、找到的入口（Kind、Found）。
//
//   Json、Error   從 aos-util 拉進來的名字
//   code::*、Result   在公開標頭 aos/exec.hpp（程式裡一律寫 code::Xxx）
//   entry_name()  $AOS_ENTRY，沒設（或空的）＝"_entry"；只讀不設（每次都重讀：.env 可能剛改過它）
//   Kind、Found   一跳（hop）找到的入口：種類、值、實際的檔
#pragma once

#include "aos/exec.hpp"

#include <string>

namespace aos::exec {

using aos::Error;
using aos::Json;

std::string entry_name();

enum class Kind {
    Executable,   // 有 +x 的檔：exec（shebang 由 kernel 處理；沒 #! 由 execvp 改用 /bin/sh，ideas § 22）
    Argv,         // 非空 JSON 陣列：當 argv exec（元素可放 $env／$ref，開跑前才解，10-20 ideas D2、D8；
                  // execvp：照 PATH 找 argv[0]；帶 / 又 exec 不了＝前面插 aos-exec，D3）
    Inst,         // 有 argv 這個 key 的 JSON 物件：inst 單子，行程內跑
    Redirect,     // 字串：路徑轉向＝交給下一層、全新的一跳（10-21 .env）
};

// 一跳找到的東西。file＝實際那個檔（realpath，不帶 #/）；doc＝陣列、單子或轉向的路徑（指示詞還沒解）。
// 找完時已經 cd 到 file 所在的資料夾、六個 AOS_* 都設好了。
struct Found {
    Kind kind = Kind::Executable;
    std::string file;
    Json doc;
};

}  // namespace aos::exec
