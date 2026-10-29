// aos/lock.hpp：aos-lock 的公開介面——鎖（NORMS N-15 的 10-29 補）：拿、放、看、判死活、收屍。
// aos-lock 命令列用這組；aos-post 的有順序投遞（order.lock/）直接連這個庫。
//
//   鎖＝一個資料夾，mkdir 成功＝拿到（只有一種獨佔鎖、不分讀寫、不檢查上下層）：
//     資料夾的鎖 <資料夾>/.lock/、檔的鎖 <檔>.lock/（lock_dir_of 照目標算；也可以直接給鎖資料夾的路徑，例 <信箱>/order.lock）
//   名牌 <鎖>/holder.json：{"holder": 身分路徑（$AOS_WS，沒設才 $HOME）, "pid", "started_at_ticks", "boot_id",
//                          "acquired_at": ISO 8601 UTC 到毫秒, "lease_ms"?, "note"?}——先寫 .holder.json.tmp 再改名（N-05）
//   放鎖＝先把鎖資料夾改名成 <鎖>.releasing.<信號> 再刪：別人不會 mkdir 到一個正在被刪的資料夾；殘骸名字不同，不擋人
//   收屍：mkdir 失敗就讀名牌——
//     boot_id 跟現在的不同、或 pid＋started_at_ticks 對不上（行程不在、pid 被重用）＝持有者死了；
//     started_at_ticks 是 null（非 Linux 寫的）＝只看 pid 在不在；寫了 lease_ms 且 acquired_at＋lease_ms 已過＝租約到期；
//     名牌不在或讀不懂（持有者 mkdir 完還沒寫好名牌就死了）＝鎖資料夾 10 秒沒動過才算死（STALE_MS）
//     判定能收：先在鎖裡 mkdir 收屍牌 .reaping（只有一個人建得成；牌子 10 秒沒動＝收的人也死了，拔掉）→ 再讀一次名牌，
//     跟判的那份不同（牌子掛進了別人剛拿到的新鎖）＝拔掉牌子、不收 → 照放鎖的步驟改名再刪
//
//   lock_dir_of   目標 → 鎖資料夾：結尾是 / 或是現有的資料夾＝<目標>/.lock，否則（檔、還不存在的名字）＝<目標>.lock
//   identity      身分路徑：$AOS_WS（絕對），沒設或空＝$HOME（絕對），都沒有＝/
//   holder_of     替一個行程填名牌（pid 0＝自己）：started_at_ticks、boot_id 讀 /proc、acquired_at＝現在
//   to_json       名牌 → holder.json 的內容（lease_ms、note 沒有就不寫）
//   look          看一把鎖：held＝鎖資料夾在不在、raw＝holder.json 原文（沒有＝nullopt）、holder＝解得出的物件、age_ms＝鎖資料夾多久沒動
//   reapable      這把鎖能不能收（規則見上）
//   try_acquire   拿一次：mkdir，失敗就看能不能收、收了再 mkdir；拿到回 true（名牌寫好了）
//   acquire       try_acquire，拿不到每 20 毫秒再試，最多等 wait_ms（0＝只試一次、負的＝一直等）
//   release       放鎖：回 true；鎖不在回 false。不看是誰的（約定，決定 10）
//
// 錯一律丟 aos::Error{code, msg}（aos-util 的 aos/error.hpp）：鎖資料夾建不了（上一層不在、沒權限）MkdirFailed、名牌寫不了 WriteFailed。
#pragma once

#include "aos/io.hpp"

#include <optional>
#include <string>
#include <sys/types.h>

namespace aos::lock {

// 錯誤代號：全家共用的（ArgumentsBad、FlagUnknown、WriteFailed、MkdirFailed、Internal）＋鎖會吐的。
namespace code {
using namespace aos::code;
inline constexpr const char* CommandUnknown = "CommandUnknown"; // 命令列：不認得的子命令（同 aos-json、aos-post）
inline constexpr const char* LockMissing = "LockMissing";       // 命令列 release：鎖不在
inline constexpr const char* HolderBad = "HolderBad";           // 命令列 show：鎖在，名牌不在或讀不懂
}  // namespace code

inline constexpr long long STALE_MS = 10000;   // 名牌不在或讀不懂時，鎖資料夾多久沒動算死（同 daemon 收子項的 10 秒；不開 key）

struct Holder {
    std::string holder;                        // 身分路徑
    long long pid = 0;
    std::optional<long long> started_at_ticks;
    std::optional<std::string> boot_id;
    std::string acquired_at;
    std::optional<long long> lease_ms;
    std::optional<std::string> note;
};

struct Seen {
    bool held = false;
    std::optional<std::string> raw;
    std::optional<Json> holder;   // raw 解得出、是物件才有
    long long age_ms = 0;
    unsigned long long ino = 0;   // 鎖資料夾的 inode（收屍時認「還是不是同一把」）
};

std::string lock_dir_of(const std::string& target);
std::string identity();
Holder holder_of(pid_t pid);
Json to_json(const Holder& h);
Seen look(const std::string& lock_dir);
bool reapable(const Seen& s);
bool try_acquire(const std::string& lock_dir, const Holder& h);
bool acquire(const std::string& lock_dir, const Holder& h, long long wait_ms);
bool release(const std::string& lock_dir);

}  // namespace aos::lock
