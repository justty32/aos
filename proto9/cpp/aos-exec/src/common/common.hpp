// common.hpp：【common】aos-exec 好幾個元素都用到的：錯誤代號、型別別名、entry_name()、找到的入口（Kind、Found）。
//
//   Json、Error   從 util 拉進來的名字
//   code::*       aos-exec 的錯誤代號（proto8 放在公開標頭 aos/exec.hpp；proto9 收進這裡，程式裡一律寫 code::Xxx）
//   entry_name()  $AOS_ENTRY，沒設（或空的）＝"_entry"；只讀不設（每次都重讀：.env 可能剛改過它）
//   Kind、Found   一跳（hop）找到的入口：種類、值、實際的檔
#pragma once

#include "aos/exec.hpp"
#include "directive/directive.hpp"
#include "util/error.hpp"
#include "util/io.hpp"

#include <string>

namespace aos::exec {

using aos::Error;
using aos::Json;

// 錯誤代號（共用的在 util/error.hpp 的 aos::code；這裡只加 aos-exec 自己會吐的）
namespace code {
using namespace aos::code;   // ArgumentsBad、FlagUnknown、LaunchFailed、Internal…
inline constexpr const char* WsMissing = "WsMissing";               // WS 不是資料夾
inline constexpr const char* EntryMissing = "EntryMissing";         // 入口找不到（檔、.json 補找、指標指不到、多段路徑中間不是資料夾）
inline constexpr const char* EntryBad = "EntryBad";                 // 找到了但跑不了（種類不對、# 寫錯、繞圈、inst 單子〔proto9 不收〕）
inline constexpr const char* DotenvBad = "DotenvBad";               // .env 讀不到（權限、是資料夾；原因開頭「cannot read .env」）、.env 壞
                                                                    // （格式不合、${名字} 沒設、不是 UTF-8；JSON 的 .env key 指示詞解不開、
                                                                    // 名字不合；原因開頭「bad .env」）。只印位置、不印值
}  // namespace code

std::string entry_name();

enum class Kind {
    Executable,   // 有 +x、看內容是程式的檔（is_program：#!／ELF 或不是 JSON；11-10）：exec（shebang 由 kernel 處理；沒 #! 由 execvp 改用 /bin/sh，ideas § 22）
    Argv,         // 非空 JSON 陣列：當 argv exec（元素可放 $env／$ref，開跑前才解，10-20 ideas D2、D8；
                  // execvp：照 PATH 找 argv[0]；帶 / 又 exec 不了＝前面插 aos-exec，D3）
    Redirect,     // 字串：路徑轉向＝交給下一層、全新的一跳（10-21 .env）
};
// proto9: no Kind::Inst -- a JSON object with "argv" is EntryBad (inst sheets are not supported in proto9).

// 一跳找到的東西。file＝實際那個檔（realpath，不帶 #/）；doc＝陣列或轉向的路徑（指示詞還沒解）。
// 找完時已經 cd 到 file 所在的資料夾、AOS_WS 與 AOS_CF／AOS_CD／AOS_CO 都設好了。
struct Found {
    Kind kind = Kind::Executable;
    std::string file;
    Json doc;
};

}  // namespace aos::exec
