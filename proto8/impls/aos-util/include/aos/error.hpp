// aos/error.hpp：【aos-util】aos 這一家命令列工具共用的錯誤型別，和「好幾支工具都會吐」的錯誤代號。
//
// 每個工具出錯都丟同一種 aos::Error{code, msg}；命令列在 stderr 印一行 {"error": {"code", "msg"}}、退出 1
// （印的函數在 aos/io.hpp）。code＝錯誤代號（看 code 分是哪種錯），
// msg＝給人看的白話（字面不保證）。代號寫成常數，打錯字編譯就會抓到。
//
// 規矩：一個代號只定義一次。
//   - 兩支以上的工具都會吐的 → 放這裡（aos::code）
//   - 只有一支工具會吐的    → 放那支工具自己的 code namespace（例如 aos::exec::code::EntryMissing）
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
// 代號照 10-23 命名統合（proto8/thinking/2026-10-23-naming）：沒有＝…Missing、不認得＝…Unknown、壞了或不合＝…Bad、
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
// 子命令、投遞（10-30 從 aos-post、aos-lock、aos-json、aos-llm-kernel 各定一份收來；medium-plan 實作時代定 12）
inline constexpr const char* CommandUnknown = "CommandUnknown"; // 命令列：不認得的子命令（aos-json、aos-post、aos-lock）
inline constexpr const char* MailboxMissing = "MailboxMissing"; // 信箱不在、或 tmp/ new/ cur/ 沒建好（aos-post、aos-llm-send）
inline constexpr const char* LetterMissing = "LetterMissing";   // 指名的信不在該在的格（aos-post 的 check、finish；aos-llm-send 等的信不見了）
inline constexpr const char* LetterBad = "LetterBad";           // 信壞了：letter.json 讀不懂、缺必填、型別不對（aos-post check；aos-llm-kernel 的回信）
// 其他
inline constexpr const char* Internal = "Internal";         // 照理不會發生的例外（記憶體不夠、cwd 被刪）
}  // namespace code

}  // namespace aos
