#pragma once

/* loop —— 一個 aos 資料夾的回合機。
 *
 * 一回合的順序是固定的（協定 §5）：匯聚 inbox → 整批並行 fork → 寫一次
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
    std::string turn_file;    // .aos/turn
    std::string state_file;   // .aos/state.json
    std::string agents_dir;   // .aos/agents
};

AOS_API Layout layout_of(const std::string &folder);
AOS_API std::string insts_dir(const Layout &layout, std::uint64_t turn);  // .aos/batch/<turn>/insts
AOS_API std::string out_dir(const Layout &layout, std::uint64_t turn);    // .aos/batch/<turn>/out

/* mkdir -p .aos/inbox、.aos/agents；turn 檔不存在就寫 "1"。deliver 與 run 都會
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

/* ---- aggregate：inbox/*.json → batch/<turn>/insts/<id>.json ---- */

/* 先 rename 再讀：搬移是提交點，搬過去了才算這一回合收下的。回傳解析成功的
 * 那些；解析失敗的照樣留在 insts/（現場證據），但跳過不執行。 */
AOS_API std::vector<wire::Inst> aggregate(const Layout &layout,
                                          std::uint64_t turn,
                                          std::string &error);

/* ---- state：組 state.json 並原子寫出 ---- */

/* agents/<name>/status.json 的**原文**鏡射。loop 不解讀內容，只轉手。 */
AOS_API std::map<std::string, std::string> mirror_agents(
    const Layout &layout);
AOS_API bool write_state(const Layout &layout, const wire::State &state,
                         std::string &error);

/* ---- turn：一回合 ---- */

struct TurnSummary {
    std::uint64_t turn = 0;          // 剛跑完的那一回合編號
    std::size_t count = 0;           // 執行了幾條；0＝idle 回合
    std::uint64_t elapsed_ms = 0;
};

/* 匯聚 → start_all → 寫 state(phase=running) → wait_all → 寫 out/ →
 * 寫 state(phase=idle) → turn +1。
 * inbox 空＝idle 回合：**不建** batch/<turn>/，但 state.json 照寫、turn 照加。 */
AOS_API bool run_turn(const Layout &layout, TurnSummary &summary,
                      std::string &error);

}  // namespace aos::loop
