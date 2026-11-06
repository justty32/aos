// aos/error.hpp：【aos-util】aos 這一家命令列工具共用的錯誤型別，和通用的錯誤代號。
//
// 每個工具出錯都丟同一種 aos::Error{code, msg}；命令列在 stderr 印一行「程式名: 代號 原因」、退出 1
// （11-04 起照 CONVENTION P-44，各程式自己印；aos/io.hpp 的 emit_error 印 {"error": {"code", "msg"}} 那種只剩 aos-util 自己的測試小程式用）。
// code＝錯誤代號（看 code 分是哪種錯），
// msg＝給人看的白話（字面不保證）。代號寫成常數，打錯字編譯就會抓到。
//
// 規矩：一個代號只定義一次。
//   - 通用的代號 → 放這裡（aos::code）
//   - 領域代號   → 放負責專案的公開標頭或自己的 code namespace
// 每支工具在自己的 code namespace 裡 `using namespace aos::code;`，程式裡一律寫 code::Xxx。
// 全家的代號總表見 impls/README.md。
#pragma once

#include <string>

namespace aos {

struct Error {
    std::string code;
    std::string msg;
};

namespace code {
// 代號照 10-23 命名統合（proto8/thinking/2026-10/23/naming）：沒有＝…Missing、不認得＝…Unknown、壞了或不合＝…Bad、
// 動作做不成＝動作＋Failed；Internal＝照理不會發生的錯。
// 命令列、stdin
inline constexpr const char* ArgumentsBad = "ArgumentsBad"; // 命令列用錯（給了不收的參數、旗標少了值、開關帶值、沒給或多給位置參數）
inline constexpr const char* FlagUnknown = "FlagUnknown";   // 不認得的旗標
inline constexpr const char* InputBad = "InputBad";         // stdin 有東西但一份 JSON 都解不出來
inline constexpr const char* InputExtra = "InputExtra";     // stdin 有好幾份 JSON（設定只要一份）
// 設定檔（loop.json、fsm.json、daemon.json；load_cfg）
inline constexpr const char* CfgMissing = "CfgMissing";     // 設定檔不在、`#/` 指不到
inline constexpr const char* CfgBad = "CfgBad";             // 設定檔讀不了、不是 JSON、`#` 後不是 `/`、某個 key 型別不對、必填的沒寫
// 檔案與子程序
inline constexpr const char* WriteFailed = "WriteFailed";   // 檔寫不了
inline constexpr const char* MkdirFailed = "MkdirFailed";   // 資料夾建不了
inline constexpr const char* LaunchFailed = "LaunchFailed"; // 子程序起不來（fork／spawn 失敗、執行檔不在）
// 子命令
inline constexpr const char* CommandUnknown = "CommandUnknown"; // 命令列：不認得的子命令（aos-json、aos-post、aos-lock）
// 程式環境
inline constexpr const char* StackMissing = "StackMissing"; // 要 AOS_STACK 卻沒設
// 其他
inline constexpr const char* Internal = "Internal";         // 照理不會發生的例外（記憶體不夠、cwd 被刪）
}  // namespace code

}  // namespace aos
