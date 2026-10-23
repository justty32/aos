// aos/error.hpp：【aos-util】aos 這一家命令列工具共用的錯誤型別，和「好幾支工具都會吐」的錯誤代號。
//
// 每個工具出錯都丟同一種 aos::Error{code, msg}；命令列在 stderr 印一行 {"error": {"code", "msg"}}、退出 1
// （印的函數在 aos/io.hpp）。code＝錯誤代號（跟 Python 版 proto8/lib 同名，看 code 分是哪種錯），
// msg＝給人看的白話（字面不保證）。代號寫成常數，打錯字編譯就會抓到。
//
// 規矩：一個代號只定義一次。
//   - 兩支以上的工具都會吐的 → 放這裡（aos::code）
//   - 只有一支工具會吐的    → 放那支工具自己的 code namespace（例如 aos::inst::code::CommandNotFound）
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
// 命令列、stdin
inline constexpr const char* Usage = "Usage";               // 命令列用錯（給了不收的參數、旗標少了值）
inline constexpr const char* FlagUnknown = "FlagUnknown";   // 不認得的旗標
inline constexpr const char* JsonSyntax = "JsonSyntax";     // stdin（或某個檔）有東西但一份 JSON 都解不出來
inline constexpr const char* InputExtra = "InputExtra";     // stdin 有好幾份 JSON（設定只要一份）
// 設定的內容
inline constexpr const char* FieldType = "FieldType";       // 不是物件、某個 key 型別不對、必填的沒寫
inline constexpr const char* Conflict = "Conflict";         // 兩個欄位互相衝突（stderr_merge 又寫 stderr、ctl 放在 ctl_dir 裡…）
// 檔案與子程序
inline constexpr const char* ReadFailed = "ReadFailed";     // 檔讀不到
inline constexpr const char* WriteFailed = "WriteFailed";   // 檔寫不了
inline constexpr const char* MkdirFailed = "MkdirFailed";   // 資料夾建不了
inline constexpr const char* LaunchFailed = "LaunchFailed"; // 子程序起不來（fork／spawn 失敗、執行檔不在）
// 其他
inline constexpr const char* Internal = "Internal";         // 照理不會發生的例外（記憶體不夠、cwd 被刪）
}  // namespace code

}  // namespace aos
