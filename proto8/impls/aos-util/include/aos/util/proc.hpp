// aos/util/proc.hpp：【aos-util】整群送訊號、/proc 身分資訊、UTC 時間與唯一名稱。
#pragma once

#include <optional>
#include <string>

#include <sys/types.h>

namespace aos {

// 對整群送訊號；群組不在、沒權限都不管。
void signal_group(pid_t pgid, int sig);

// 一個行程的啟動時間（/proc/<pid>/stat 第 22 欄，clock ticks）；pid 0＝自己。讀不到＝nullopt。
// pid＋啟動時間對得上＝同一個行程（pid 會被重用，啟動時間不會一樣）。
std::optional<long long> proc_started_at_ticks(pid_t pid);

// 開機 id（/proc/sys/kernel/random/boot_id）；讀不到＝nullopt。
std::optional<std::string> boot_id();

// 現在的 UTC 時間，ISO 8601 到毫秒（毫秒無條件捨去），同 Python
// datetime.now(timezone.utc).isoformat(timespec="milliseconds")：2026-10-23T01:58:45.123+00:00
// （10-23 命名統合：state 的 at、fsm trace 的 at 都用這一種寫法）。
std::string utc_now_ms();

// 現在（UTC epoch 奈秒，system_clock）。
long long utc_now_ns();

// 一個時間點（UTC epoch 奈秒）的 ISO 8601 UTC 到毫秒，寫法同 utc_now_ms（aos-post 讓預設的信件名稱與 sent_at 取自同一刻）。
std::string utc_ms_at(long long ns);

// 獨一無二的名字：<UTC 奈秒 20 位>.<pid>.<started_at_ticks>（讀不到 ticks＝-1）；ns 省略＝現在。
// 照字典序排＝照產生的先後（同一刻以後的比較不保證）；pid、ticks 只讓名字在同機不撞。aos-post 預設的信件名稱、aos-lock 放鎖時的改名都用這個
// （10-30 從 aos-llm-kernel、aos-post、aos-lock 三份一樣的寫法收來，medium-plan 實作時代定 12）。
std::string unique_id();
std::string unique_id(long long ns);

// 自己的身分（路徑）：$AOS_WS ＞ $AOS_STACK ＞ $AOS_CF ＞ cwd，空字串算沒設，一律轉絕對路徑。
// aos-post 信封的 sender、aos-lock 名牌的 holder 都用這個（N-15 ③「跟信封 sender 同一條」；11-03 拿掉 $HOME）。
// cwd 拿不到（被刪了）丟 Error{Internal}。
std::string identity();

}  // namespace aos
