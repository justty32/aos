# 隊 D 回報：heartbeat on aos——`core/tick`、`every_ms`、登記 CLI、這個 repo 自己當第一個世界

← [交接書 proto-D-heartbeat](../done/proto-D-heartbeat.md)｜[PROTOCOL](../PROTOCOL.md)｜[dispatch](../../README.md)

**終局 STATUS：`DONE`**（7 條驗收全部有證據，`ctest` 7/7 全綠）
**worktree**：`/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a157afb5ecd302bce`
**分支**：`worktree-agent-a157afb5ecd302bce`（**未 merge、未 push**）

## 做了什麼

一個新的核心小專案 `core/tick`（2,811 行，單檔最大 298 行），加上 `core/loop` 的一個新欄位、
三個工作流檔的改寫，以及這個 repo 自己的 dogfood。

| 產物 | 路徑 |
|---|---|
| tick 小專案 | `core/tick/`（README、公開標頭、8 個 `.cpp`、5 份測試） |
| loop 擴充 | `core/loop/`（`every_ms`）、`PROTOCOL.md` §1 |
| markdown 端 | `wf/workflows/{tick,routines,schedule}.md`、`.claude/commands/wf-tick.md` |
| dogfood | `.gitignore`（隊 C 已加 `.aos/`）、本 repo `.aos/heartbeat/`（不進版控） |
| 登記 | `core/README.md`、`AGENTS.md`、`wf/workflows/common/code-map.md` |

**「本包不是排程器、執行引擎一律外借」這句話消失了**：`aos run` 就是引擎、`every/tick.json` 就是
心跳、資料夾裡的 agent 就是 tick 醒來要動腦的那個人。

### 三個關鍵形狀

- **時間一律注入**。所有判定函式收 `Instant now`（UTC epoch 秒），函式庫層**一行 `system_clock::now()`
  都沒有**（只有 CLI 層讀真實時鐘）。所以 tick 的 11 個判定測試不 sleep、不靠牆上時鐘、跑完 0.01 秒。
- **`run_tick` 先算 plan 再執行**，`--dry-run` 在 plan 之後就 return。副作用只有一個出口，
  不必在每個 deliver／say／寫表前面各加一次 `if (!dry_run)`——那種寫法遲早會漏掉一個。
- **`every_ms` 讓常駐投遞匣有自己的節奏**。`aos run --interval 100` 是每 0.1 秒一回合，
  但心跳想要 30 分鐘一次；沒有這個欄位的話 `aos tick` 一小時會被叫起三萬六千次。

## 7 條驗收的證據

| # | 驗收 | 證據 |
|---|---|---|
| 1 | 根目錄 build＋ctest 全綠 | `100% tests passed out of 7`。既有 6 個目標繼續綠，新增 `aos_tick_tests`。**四條 codex 整合後第一次編譯就過，零修正。** |
| 2 | `heartbeat init --interval 1s` | `.aos/every/tick.json` ＝ `{"id":"tick","argv":["aos","tick"],"every_ms":1000}`；兩張表建好，`wf/tools/tabledb.py` 兩張都讀得到（`contract: wf-table/1`、`columns` 正確） |
| 3 | `--every 2s` 跑 4 秒 | `/tmp/hb-r` **恰好 2 行**；`last_run` ＝ `2026-08-30T17:23:17+08:00`；`log.md` 兩行 `run=r-tkksqr→hb-r-tkksqr-1` 與 `…-21`。中間的回合印 `idle`——`every_ms` 真的擋掉了 39 次多餘的 tick |
| 4 | schedule 到點執行、刪列 | `/tmp/hb-s` 存在；`schedule.json` `count: 0`（該列已刪）；log 那一行同時帶了 routine 與 schedule 兩個事件 |
| 5 | `ask` 走 `aos say` | `aos agent init` 後 `agent 名 = hbA`；`aos tick` → `.aos/agents/hbA/say/1788081842612001036-…md` 內容**就是**「報一次時間」；log `ask=r-tkkss2→hbA`。0 隻 agent 的世界記 `ask=…→none`（不呼叫 say） |
| 6 | `--dry-run` 對錯過 7 小時的項 | 印 `[dry-run] … missed=s-tkksrh→none`（**不是**執行）；跑完 `/tmp/hb-missed` 不存在、該列**還在**表裡 |
| 7 | 本 repo dogfood | `aos routine ls` 印出 wf-lint 那條，`NEXT` ＝ **`2026-09-06 00:00`**；`git status --short` 空的，`git check-ignore` 回 `.gitignore:8:.aos/` |

驗收腳本是暫存物（scratchpad），不進 repo。**驗完沒有留下常駐 `aos run`**——開常駐是使用者的事。

## commit

| hash | 內容 |
|---|---|
| `78d1362` | 取用使用者工作樹裡較新的 heartbeat 四檔當改寫基準 |
| `a9ffaa5` | `core/tick` 規格與三個工作流檔改寫成以 aos 為引擎 |
| `4658c57` | `core/tick` 心跳判定 ＋ `core/loop` 的 `every_ms` |
| （本檔的 commit） | 回報與 code map 登記 |

`git add` 全程只加明確路徑；**未 push**。

## 隊形與分工

| 誰 | 做了什麼 |
|---|---|
| Fable 規劃者 ×1 | 把交接書 §資料格式落成 `core/tick/README.md`（188 行）與公開標頭草稿（177 行）。**標頭的簽名最後一個字都沒改就被三條實作採用** |
| codex gpt-5.6-sol ×4 條線 | ① paths／clock／ids／table ② due／log／tick ③ 四個 CLI＋CMake ④ `core/loop` 的 `every_ms` |
| 隊長（我） | 標頭定案、寫五份任務書、**自己寫 `tests/test_support.hpp`**（三條都要 include，交給任一條寫都會撞）、加 `add_subdirectory(tick)`、審 diff、跑 build／ctest／7 條驗收、code map 登記、commit |

①②③ **完全平行**（檔案零重疊，靠標頭當唯一契約），這是這次能一次編過的主因。

## 隊長裁決

1. **`<folder>` 直接做成可選，沒有先做必填版。** 調度者的第一段指示是「先必填、等隊 C 落地再改可選」，
   但 `aos::loop::current_folder()`／`find_folder()` 是**隊 A 就寫好的**、PROTOCOL §6 也早就這樣定，
   前提不成立。照既有 `aos deliver` 的作法做，零成本、少一次改寫。
2. **先把四個 md 檔同步成使用者工作樹裡的版本再改寫**（commit `78d1362`）。分支上那四檔還是帶
   `{{佔位符}}` 的模板版，直接改會把使用者的實例化成果蓋掉，而且 diff 看不出真正改了什麼。
3. **`ask` 在第一段就接真的 `aos::agent::say()`，沒有做「介面留空」的 `deliver_ask()`。**
   `say()` 是隊 B 就有的公開 API、簽名穩定，留空反而多一次改寫。
4. **`every/.last/<stem>` 存上次投遞時間**（而不是塞進 `state.json`）。跟著 every 檔走；
   `.last` 是點開頭的**目錄**，而 `list_json_files` 只收 `*.json`，不會被誤當成指令檔。
5. **`agent::say()` 的例外一定接住**——它在 agent 目錄存在但 `say/` 不存在時會丟 `runtime_error`。
   接住就改記 `error` 事件且**不更新 `last_run`**（下次心跳會重試）。
6. **無事的心跳不寫 log**。`--every 2s` 的世界一天有四萬多次心跳，全記只會把有用的行淹掉；
   心跳活著的證據在 loop 的 `batch/<turn>/out/`。
7. **`ask` 型投出去就更新 `last_run`**（含沒有 agent 的 `→none`）。tick 沒有管道知道 agent 何時做完，
   等回覆會每次心跳重複 say。
8. **dogfood 的 `last_run` 用 `tabledb.py update` 設**，沒有為此加一個 `--last-run` 旗標。
   順帶證明了這兩張表對 repo 既有工具是真的可讀**可寫**。
9. **`.gitignore` 維持隊 C 寫的 `.aos/`**（不改成交接書寫的 `/.aos/`）。前者是後者的超集，
   子資料夾裡的測試世界也一起擋掉。

## 已知不管（`core/tick/README.md` 有完整一節，這裡只列最重要的）

- **沒有鎖**：`aos tick` 與 `aos routine add` 同時改 `routines.json`，後寫的贏（整檔 rename）。
- **投出去就算做了**：不追 `batch/<turn>/out/hb-*.json` 的結果，失敗的 argv 不重試；
  ask 有沒有被 agent 做完也不追。
- **沒有崩潰恢復**：deliver 成功後、寫表前被殺 → 下一次心跳會再投一次同一件事。
- **未知欄位改寫時丟掉**：`tabledb.py` 加進去的多餘欄會在下一次 tick 改寫時消失。
- **表裡的無效列每次心跳都記一次 `error`**，不會自動移除，要人去修或 `rm`。
- **相對時間不解析**（「今晚 8 點」）：只收 `YYYY-MM-DD HH:MM` 與 `Nd/Nh/Nm/Ns`，換算是 agent 的事。
- **`--at` 只到分鐘**，所以驗收 4 用的是「現在這一分鐘」而不是「現在 +2 秒」。

## 收線時要注意的三件事

1. **`.aos/` 是 gitignore 的，所以 dogfood 不會跟著 merge 過去。** 使用者要在主 repo 根目錄自己跑
   一次 `aos heartbeat init --interval 30m` 加那條 `aos routine add`（指令在 `wf/workflows/tick.md`
   的「怎麼開這個 repo 的心跳」一節）。
2. **主 repo 的工作樹對那四個 md 檔有未提交的改動**（就是 commit `78d1362` 取用的那份）。
   ff-merge 前要先把它們 stash 或 checkout 掉，否則 git 會拒絕覆蓋。
3. **`wf/tools/` 與 `wf/workflows/common/data-files.md` 目前是未追蹤檔**，不在任何分支上。
   `core/tick` 寫出的兩張表依 `wf-table/1` 契約而生、也實測被 `tabledb.py` 讀寫過，
   但那份契約本身還沒進版控。
