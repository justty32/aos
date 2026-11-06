// aos/lock.hpp：aos-lock 公開介面——mkdir 取鎖、flock 判存活、兩鐘租約、改名放鎖。
// library 的 holder.flock 持有到 release 或行程結束；CLI 不建存活標記，只靠放鎖與租約。
// acquired_at 永遠寫；有樹時鐘才寫 acquired_at_ticks。租約優先比雙方 tick，否則換牆鐘。
// 名牌缺失或無效時，資料夾 mtime 相差正負 10 秒才收；release 不驗身分。
#pragma once

#include "aos/util/io.hpp"

#include <optional>
#include <string>

namespace aos::lock {

// 錯誤代號：全家共用的（ArgumentsBad、FlagUnknown、WriteFailed、MkdirFailed、CommandUnknown、Internal）＋鎖會吐的。
namespace code {
using namespace aos::code;
inline constexpr const char* LockMissing = "LockMissing";       // 命令列 release：鎖不在
inline constexpr const char* HolderBad = "HolderBad";           // 命令列 show：鎖在，名牌不在或讀不懂
}  // namespace code

inline constexpr long long STALE_MS = 10000;   // 名牌不在或讀不懂時，鎖資料夾多久沒動算死（同 daemon 收子項的 10 秒；不開 key）

struct Holder {
    std::string holder;                        // 身分路徑
    bool flock = true;                         // library 存活標記；CLI false
    std::optional<long long> acquired_at_ticks;
    std::string acquired_at;
    std::optional<long long> lease_ticks;
    std::optional<std::string> note;
};

struct Seen {
    bool held = false;
    std::optional<std::string> raw;
    std::optional<Json> holder;   // raw 解得出、是物件才有
    long long age_ms = 0;
    std::optional<bool> alive; // 有 flock 標記才有值；探測失敗保守當活著
    unsigned long long ino = 0;   // 鎖資料夾的 inode（收屍時認「還是不是同一把」）
};

std::string lock_dir_of(const std::string& target);
// 庫預設保管 flock；CLI 傳 false。真正拿到鎖時會重新取 acquired_at 與 acquired_at_ticks。
Holder holder_of(bool flock = true);
Json to_json(const Holder& h);
Seen look(const std::string& lock_dir);
bool reapable(const Seen& s);
bool try_acquire(const std::string& lock_dir, const Holder& h);
bool acquire(const std::string& lock_dir, const Holder& h, long long wait_ms);
bool release(const std::string& lock_dir);

}  // namespace aos::lock
