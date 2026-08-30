#pragma once

/* loop —— 一個 aos 資料夾的回合機。
 *
 * 一回合的順序是固定的（協定 §5）：匯聚 inbox 與 every → 整批並行 fork → 寫一次
 * state.json → 全部等完 → 寫 out/ → 再寫一次 state.json → turn +1。中間那次
 * state.json **必須**在 fork 之後、等完之前落檔：外面的人就是靠它在執行期間
 * 看到 running[] 與 pid，這是「回合正在跑」唯一的對外證據。
 *
 * 內部分層單向：layout ← deliver ← aggregate ← state ← turn ← cli。
 */

#include <aos/export.h>
#include <aos/exec.hpp>
#include <aos/wire.hpp>

#include <cstddef>
#include <cstdint>
#include <map>
#include <string>
#include <vector>

namespace aos::loop {

/* ---- layout：<folder>/.aos/ 的路徑推導，不碰檔案系統（ensure_layout 除外） ---- */

struct Layout {
    std::string folder;       // 絕對路徑（realpath 後）
    std::string aos;          // <folder>/.aos
    std::string inbox;        // .aos/inbox
    std::string every;        // .aos/every
    std::string turn_file;    // .aos/turn
    std::string state_file;   // .aos/state.json
    std::string agents_dir;   // .aos/agents
};

AOS_API Layout layout_of(const std::string &folder);
/* 從 start 往上（含自己）找最近一個含 .aos/ 的目錄；找不到回傳空字串。 */
AOS_API std::string find_folder(const std::string &start);
/* AOS_FOLDER 有值就用它；否則往 cwd 上找世界；再找不到就用 cwd。 */
AOS_API std::string current_folder();
AOS_API std::string insts_dir(const Layout &layout, std::uint64_t turn);  // .aos/batch/<turn>/insts
AOS_API std::string out_dir(const Layout &layout, std::uint64_t turn);    // .aos/batch/<turn>/out

/* mkdir -p .aos/inbox、.aos/every、.aos/agents；turn 檔不存在就寫 "1"。deliver 與 run 都會
 * 呼叫，所以不需要一條獨立的 init 子命令。 */
AOS_API bool ensure_layout(const Layout &layout, std::string &error);
AOS_API std::uint64_t read_turn(const Layout &layout);                    // 讀不到＝1
AOS_API bool write_turn(const Layout &layout, std::uint64_t turn,
                        std::string &error);

/* ---- deliver：原子投遞進 inbox/<id>.json（先寫 .json.tmp 再 rename） ---- */

AOS_API bool deliver(const Layout &layout, const wire::Inst &inst,
                     std::string &error);
/* 從 argv 現做一份 Inst，id 由 make_delivery_id() 產生。 */
AOS_API wire::Inst inst_from_argv(const std::vector<std::string> &argv);
AOS_API std::string make_delivery_id();                                   // "d-<epoch_ms>-<pid>-<seq>"

/* ---- aggregate：inbox 搬入、every 複製入 batch/<turn>/insts/ ---- */

/* inbox 先 rename，every 後複製且強制 id=<stem>-<turn>；every_ms 可限制個別
 * every 指令的投遞間隔。回傳解析成功的那些；解析失敗的照樣留在 insts/
 *（現場證據），但跳過不執行。 */
AOS_API std::vector<wire::Inst> aggregate(const Layout &layout,
                                          std::uint64_t turn,
                                          std::string &error,
                                          std::size_t *every_count = nullptr);

/* every/<stem>.json 的可選欄位 every_ms：距上次投遞不足 every_ms 毫秒就跳過這一回合。
 * 沒有這個欄位或值 ≤ 0＝每回合都投（原本的行為）。上次投遞時間記在 every/.last/<stem>。
 * 回傳 false＝這回合不該投；true＝該投（並由呼叫端負責在投出後 mark_every_delivered）。 */
AOS_API bool every_due(const Layout &layout, const std::string &stem,
                       std::int64_t every_ms, std::int64_t now_ms);
AOS_API bool mark_every_delivered(const Layout &layout, const std::string &stem,
                                  std::int64_t now_ms, std::string &error);

/* ---- state：組 state.json 並原子寫出 ---- */

/* agents/<name>/status.json 的**原文**鏡射。loop 不解讀內容，只轉手。 */
AOS_API std::map<std::string, std::string> mirror_agents(
    const Layout &layout);
AOS_API bool write_state(const Layout &layout, const wire::State &state,
                         std::string &error);

/* ---- turn：一回合 ---- */

struct InstFailure {
    std::string id;
    int exit = 0;            // signal == 0 時才有意義
    int signal = 0;
    std::string argv0;
    std::string stderr_line; // stderr 的第一行非空白內容，可能是空字串
};

struct TurnSummary {
    std::uint64_t turn = 0;          // 剛跑完的那一回合編號
    std::size_t count = 0;           // 執行了幾條；0＝idle 回合
    std::size_t every_count = 0;     // 其中有幾條來自 every/
    std::uint64_t elapsed_ms = 0;
    std::vector<InstFailure> failures;
};

/* 匯聚 → start_all → 寫 state(phase=running) → wait_all → 寫 out/ →
 * 寫 state(phase=idle) → turn +1。
 * inbox 與 every 都空＝idle 回合：**不建** batch/<turn>/，但 state.json 照寫、
 * turn 照加。 */
AOS_API bool run_turn(const Layout &layout, TurnSummary &summary,
                      std::string &error);

}  // namespace aos::loop
