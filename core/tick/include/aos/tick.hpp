#pragma once

/* tick —— aos 的心跳判定：掃 routines／schedule 兩張表，把到期的投進 inbox 或
 * 交給 agent，更新表、寫 log。自己絕不呼叫 LLM。
 *
 * 所有「現在」一律由呼叫端注入（Instant）；本函式庫沒有任何函式讀真實時鐘，
 * 只有 CLI 層才 system_clock::now()。
 *
 * 內部分層單向：paths ← clock ← ids ← table ← due ← log ← tick ← init ← cli。
 * 各層只透過本標頭互相看見，沒有共用的內部標頭（cli_common.hpp 只給 CLI 層）。
 */

#include <aos/export.h>
#include <aos/loop.hpp>

#include <array>
#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace aos::tick {

/* ---- 型別 ---- */

using Instant = std::int64_t;   // UTC epoch 秒。所有判定與比較都用它，不用當地時間

struct LocalTime {              // 某時區下的牆上時間，只由 to_local／from_local 產生
    int year = 0, month = 0, day = 0;
    int hour = 0, minute = 0, second = 0;
    int weekday = 1;            // ISO：1＝週一 … 7＝週日
};

struct Run {                    // 一列的 run 欄：argv 非空＝argv 型；否則 ask 非空＝ask 型；
    std::vector<std::string> argv;   // 兩者皆空＝無效列
    std::string ask;
};

struct Routine {                // routines.json 一列（欄位順序即 columns 順序）
    std::string id;
    std::string kind;           // "interval" | "slot"
    std::string every;          // interval 用："7d" / "30m" / "2s"（單一單位）
    std::string slot;           // slot 用："HH:MM" 或 "HH:MM 11111.."（週一→週日遮罩）
    std::string last_run;       // "YYYY-MM-DDTHH:MM:SS+08:00"；空＝從未執行
    Run run;
    std::string note;
};

struct ScheduleItem {           // schedule.json 一列
    std::string id;
    std::string at;             // "YYYY-MM-DD HH:MM"，以 Config::tz 解讀
    Run run;
    std::string note;
};

struct Config {                 // heartbeat/config.json；缺檔＝全預設、缺欄＝該欄預設
    std::string tz = "Asia/Taipei";     // IANA 名稱
    std::string missed_after = "6h";    // 期間字串：schedule 過期超過它＝「錯過很久」
};

struct SlotSpec {
    int hour = 0, minute = 0;
    std::array<bool, 7> days{};         // [0]＝週一 … [6]＝週日
};

enum class ScheduleState { pending, due, missed };

struct Event {                  // log.md 一行裡的一個事件
    std::string kind;           // "run" | "ask" | "missed" | "error"
    std::string id;             // 表列的 id
    std::string target;         // run→投出的指令 id；ask／missed→agent 名或 "none"；error→原因
};

struct Paths {
    std::string heartbeat;      // <folder>/.aos/heartbeat
    std::string routines_file;  // heartbeat/routines.json
    std::string schedule_file;  // heartbeat/schedule.json
    std::string log_file;       // heartbeat/log.md
    std::string config_file;    // heartbeat/config.json
};

/* ---- paths：路徑推導；single_agent 以外不碰檔案系統 ---- */

AOS_API Paths paths_of(const loop::Layout &layout);
/* agents_dir 底下剛好一個子目錄 → 其名字；0 個或 ≥2 個 → nullopt。 */
AOS_API std::optional<std::string> single_agent(const loop::Layout &layout);

/* ---- clock：時間的解析、格式化與時區換算（純函式，不讀時鐘） ---- */

AOS_API bool parse_duration(std::string_view text, std::int64_t &seconds);  // "Nd|Nh|Nm|Ns"，N>0
AOS_API bool valid_zone(const std::string &tz);                             // locate_zone 找得到
AOS_API bool to_local(Instant at, const std::string &tz, LocalTime &local,
                      std::string &error);
/* 忽略 local.weekday；夏令時間空缺／重疊一律取最早的解。 */
AOS_API bool from_local(const LocalTime &local, const std::string &tz,
                        Instant &at, std::string &error);
/* "YYYY-MM-DDTHH:MM:SS" 後接 "Z" 或 "±HH:MM"（last_run 與 log 用）。 */
AOS_API bool parse_timestamp(std::string_view text, Instant &at);
AOS_API std::string format_timestamp(Instant at, const std::string &tz);
/* "YYYY-MM-DD HH:MM"（schedule 的 at、CLI 的 --at 用），以 tz 解讀。 */
AOS_API bool parse_at(std::string_view text, const std::string &tz, Instant &at);
AOS_API std::string format_at(Instant at, const std::string &tz);

/* ---- ids：列 id 的檢查與產生 ---- */

AOS_API bool valid_id(std::string_view id);   // ^[A-Za-z0-9_.-]{1,64}$（會進檔名）
/* "<prefix>-<base36(now)>"；撞到 taken 就依序加 "-2"、"-3"…。prefix 為 "r" 或 "s"。 */
AOS_API std::string make_id(std::string_view prefix, Instant now,
                            const std::vector<std::string> &taken);

/* ---- table：wf-table/1 檔的讀寫（缺欄＝空字串；未知欄位讀時忽略、寫時丟棄） ---- */

/* 檔不存在＝空表、回 true；壞 JSON、缺 rows、重複 id → false。 */
AOS_API bool read_routines(const std::string &path, std::vector<Routine> &rows,
                           std::string &error);
AOS_API bool read_schedule(const std::string &path,
                           std::vector<ScheduleItem> &rows, std::string &error);
/* 整檔原子改寫（.tmp＋rename）；extracted＝now 在 tz 的日期，source＝""。 */
AOS_API bool write_routines(const std::string &path, const std::vector<Routine> &rows,
                            Instant now, const std::string &tz, std::string &error);
AOS_API bool write_schedule(const std::string &path,
                            const std::vector<ScheduleItem> &rows, Instant now,
                            const std::string &tz, std::string &error);
/* 檔不存在→預設值、回 true；存在但壞掉→false。 */
AOS_API bool read_config(const std::string &path, Config &config, std::string &error);
/* mkdir -p heartbeat/；兩張表不存在就各寫一張空表。已存在的檔一律不動。 */
AOS_API bool ensure_heartbeat(const Paths &paths, Instant now,
                              const std::string &tz, std::string &error);

/* ---- due：到期判定（純函式；規則見 README「到期規則」） ---- */

AOS_API bool parse_slot(std::string_view text, SlotSpec &spec);
/* 列無效（kind／every／slot／run 壞掉）→ false 且 error 非空；有效→ error 空。 */
AOS_API bool routine_due(const Routine &routine, Instant now, const std::string &tz,
                         std::string &error);
/* 下次到期時刻；已到期或列無效 → nullopt（ls 分別印「到期」「無效」）。 */
AOS_API std::optional<Instant> routine_next(const Routine &routine, Instant now,
                                            const std::string &tz);
/* at 壞掉→ pending 且 error 非空。 */
AOS_API ScheduleState schedule_state(const ScheduleItem &item, Instant now,
                                     const Config &config, std::string &error);

/* ---- log：log.md 一行的格式化與追加 ---- */

/* "<format_timestamp(now)> turn=<turn> <kind>=<id>→<target> …\n"，單一空白分隔。 */
AOS_API std::string format_log_line(Instant now, const std::string &tz,
                                    std::uint64_t turn, const std::vector<Event> &events);
AOS_API bool append_log(const std::string &path, const std::string &line,
                        std::string &error);

/* ---- tick：一次心跳 ---- */

struct TickOptions {
    bool dry_run = false;       // 只算不做：不投遞、不 say、不改表、不寫 log
    std::uint64_t turn = 0;     // 進指令 id 與 log；CLI 由 AOS_TURN 或 read_turn 取得
};

struct TickReport {
    std::vector<Event> events;  // 依處理順序：routines 表序，再 schedule 表序
    std::string line;           // 這次寫（dry-run 下：本來會寫）的 log 行；無事＝空
};

/* 讀 config → 讀兩表 → 逐列判定並執行 → 改寫有變動的表 → 追加 log。
 * 有 error 事件仍算完成、回 true；回 false 只在 tz 不合法、讀表、寫表或寫 log 失敗。 */
AOS_API bool run_tick(const loop::Layout &layout, Instant now,
                      const TickOptions &options, TickReport &report,
                      std::string &error);

/* ---- init：aos heartbeat init ---- */

/* ensure_layout → ensure_heartbeat → 原子寫 every/tick.json（覆蓋既有檔）：
 * {"id":"tick","argv":["aos","tick"],"every_ms":<every_ms>} */
AOS_API bool heartbeat_init(const loop::Layout &layout, Instant now,
                            std::uint64_t every_ms, std::string &error);

}  // namespace aos::tick
