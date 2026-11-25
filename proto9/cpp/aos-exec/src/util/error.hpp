// util/error.hpp: the error type aos-exec throws, and the shared error codes it uses (trimmed copy of proto8 aos-util aos/util/error.hpp).
//
// 每個工具出錯都丟同一種 aos::Error{code, msg}；命令列用 aos::fail 在 stderr 印一行
// 「程式名: error: 代號 原因」、退出 1（util/io.hpp）。
// code＝錯誤代號（看 code 分是哪種錯），
// msg＝給人看的白話（字面不保證）。代號寫成常數，打錯字編譯就會抓到。
// proto9: only the codes aos-exec still throws are kept (MkdirFailed, ClockBad, ... went with AOS_STACK and inst sheets).
#pragma once

#include <string>

namespace aos {

struct Error {
    std::string code;
    std::string msg;
};

namespace code {
// 代號照 10-23 命名統合：沒有＝…Missing、不認得＝…Unknown、壞了或不合＝…Bad、
// 動作做不成＝動作＋Failed；Internal＝照理不會發生的錯。
inline constexpr const char* ArgumentsBad = "ArgumentsBad"; // 命令列用錯（旗標少了值、開關帶值、沒給位置參數）
inline constexpr const char* FlagUnknown = "FlagUnknown";   // 不認得的旗標
inline constexpr const char* CfgBad = "CfgBad";             // split_hash: `#` 後不是 `/`（aos-exec 接住換成 EntryBad）
inline constexpr const char* LaunchFailed = "LaunchFailed"; // 子程序起不來（exec 失敗）
inline constexpr const char* Internal = "Internal";         // 照理不會發生的例外（記憶體不夠、cwd 被刪）
}  // namespace code

}  // namespace aos
