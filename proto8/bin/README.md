# bin — aos 的指令（資料夾＝程式）

← [proto8](../README.md)｜慣例：[CONVENTION](../CONVENTION.md)｜demo：[demo](../demo/README.md)｜測試：`python3 -m unittest discover -s proto8/tests`

**2026-10-19 從 proto8-2 併進來。** 資料夾＝程式；入口＝資料夾裡 `$AOS_ENTRY`（預設 `_exec`；10-19 晚改，原 `.aos/exec`）指的可執行檔。純標準庫（shell 與 Python），在 WSL／Linux 跑。**aos 只訂環境變數**（`AOS_ENTRY`、`AOS_WS`、`AOS_STACK`），入口拿到之後「這次要做啥」怎麼收、怎麼用是入口自己的事（使用者 10-19，[ideas § 4](../thinking/2026-10-19-ideas.md)）；aos-exec 只是把多的 args／stdin 原樣交給它。

> **這一版還沒照 10-19 下班前的新規則改**（[ideas § 14～§ 19](../thinking/2026-10-19-ideas.md)；條文 [N-57～N-62](../NORMS/10-基礎設施-定義與工作區.md)、C-73、P-40）：入口四種（可執行檔、inst 單子、argv 陣列、`js[$AOS_ENTRY]`）、`aos-exec XXX`（XXX 可為檔、`檔#/指標`、補找 `XXX.json`）、五個環境變數（加 `AOS_CF`、`AOS_CD`）、字串轉向與繞圈偵測。這些目前只有 `proto8/impls/aos-exec`（使用者假日寫的 C++ 參考實作，git 未追蹤）做了，而且 impls **只提供 `aos-exec` 一支命令列**、inst 是 C lib、沒有 `aos-inst`（§ 20）。下面寫的是這一版現在的行為；要不要把 bin 版改到新規則，使用者還沒說（[NORMS 待定](../NORMS/08-待定.md)）。

```
sh proto8/demo/run.sh                                  # 建暫時工作區、放一題、跑 agent-bob 與 agent-ann、印工作區與 stack 樹
python3 -m unittest discover -s proto8/tests
proto8/bin/aos-exec proto8/demo/agent-bob <工作區>      # 自己跑
cd workspace && aos-exec ../agent-bob                  # 慣例用法（WS 省略＝-、沒設 AOS_WS 就用 cwd）
```

（舊的 `bin/aos` 與 `lib/` 那一套 10-16 實作是另一代，併入時進 git 歷史，見 [proto8 README](../README.md)。）

## 逐支說明

- `aos-exec DIR [WS [args...]]`：WS 省略＝`-`；`-`＝沿用現有 `AOS_WS`，沒設才用 `.`（呼叫當下的 cwd）；給路徑就用那個。轉絕對路徑設成 `AOS_WS`；`AOS_STACK` 沒設就用 `$AOS_WS/.aos/`（轉絕對路徑、不存在就建），有設就沿用，都 export 給子程式；`cd DIR`、exec 入口；args／stdin 原樣透傳；把自己的 `bin/` 放進 PATH（已在就不再疊一份，P-39），所以入口裡直接寫 `aos-loop`、`aos-exec`。入口是可執行檔；沒有它但有旁邊的 `$AOS_ENTRY.json`（例 `_exec.json`）就交給 `aos-inst` 跑。入口兩種都沒有／不可執行、工作區或 DIR 不存在 → 結束碼 1 並印原因。（**待照新規則更新**：N-58 的 `XXX`＝檔／`檔#/指標`／補 `.json`、N-61 沒 `+x` 當 JSON 讀與 `js[$AOS_ENTRY]`、N-57 的 `AOS_CF`／`AOS_CD`、N-59 cd 到入口檔所在的資料夾，這版都還沒有。）
- `aos-inst FILE [args...]`（`aos_inst.py`，純標準庫）：讀一張單子，第一行是 `#!` 就丟掉，其餘當 JSON，跑一次。所以 `_exec` 第一行寫 `#!/usr/bin/env aos-inst`、下面接 JSON、`chmod +x` 就是入口（P-28 (A)）。認得的 key：`argv`（必填，args 接在後面）、`cwd`、`envs`、`stdin`、`stdout`、`stderr`、`stdout_append`、`stderr_append`、`timeout_ms`、`grace_ms`（沒寫 2000；逾時先 SIGTERM、過 grace 再 SIGKILL）；其他 key 忽略。子程式自成一個行程群組，逾時與轉來的訊號打整個群組（killpg），孫程式一起收掉（P-36）。單子裡任何位置的 `{"$env": 名, "path": 子路徑}` 換成該環境變數底下的路徑（P-31）。沒寫的串流接呼叫者的；命令列結束碼＝子程式的碼（不另吐結果 JSON），aos-inst 自己的錯退 1、stderr 一行 `aos-inst: 原因`。行程內用 `aos_inst.run(單子或檔)` 回 `{"code","signal","timed_out","pid","ms"}`。（**impls 線沒有這支**：inst 是 C lib、不提供命令列，單子當入口時由 aos-exec 行程內跑、aos-exec 以子程式的碼結束；行程內的函數是 aos-exec 公開 API 的 `run_inst`。所以 `#!/usr/bin/env aos-inst` 與 `exec aos-inst _exec.json` 兩種寫法只在這版能用；同一個檔拿掉 `+x` 就是 impls 認的 JSON 入口，P-40。使用者 10-19 晚，[ideas § 20](../thinking/2026-10-19-ideas.md)）
- `aos-loop loop.json`（Python）：`{"run": 子資料夾 或 一張單子, "max": 最多幾圈}`，每圈 `aos-exec <run>`（`run` 是物件＝單子，行程內 `aos_inst.run()`，取它的 `code`）；檔讀不到／不是 JSON／`run` 不對／單子壞 → 退 1、stderr 一行 `aos-loop: 原因`。子程式結束碼 0＝下一圈、**10＝要求停（loop 以 0 結束）**、其他非 0＝失敗（loop 以原碼結束）；跑滿 max 圈也以 0 結束、stderr 不寫（N-43 正常退出；有沒有跑滿看 `trace.jsonl` 行數）。
- `aos-fsm FSM.json`（Python，import `aos_inst`）：一拍只跑一格。`{"start": "idle", "states": {名: {"val": 子資料夾名或單子, "next": 下一個狀態}}}`；讀 `$AOS_STACK/state`（沒有＝start；純文字一行；寫的時候先寫 `.state` 再改名，N-05），`val` 字串＝`aos-exec` 它（相對路徑從 cwd 算）、物件＝行程內 `aos_inst.run()`；每拍在 `$AOS_STACK/trace.jsonl` 追加一行 `{"at","state","code","signal","timed_out","ms"}`（`at`＝這拍開始的 UTC 時間，P-38）；格的碼 0 才把 next 寫進 state，然後以格的碼退出（10 與其他非 0 原樣往上、state 不動）。只看結束碼、不讀格的 stdout、不轉述格的 stderr。沒設 `AOS_STACK`／表壞／查不到格／單子壞 → 退 1、stderr 一行 `aos-fsm: 原因`。

執行中狀態（`state`、`trace.jsonl`、`plan`、`current`）在 `$AOS_STACK`（預設 `$AOS_WS/.aos/`）；工作區只放交辦的東西與成果（`inbox/`、`out/`、`done/`）；定義資料夾不被寫，所以同一個 agent 可同時被兩個工作區跑。結果＝工作區內容；沒有別的結果通道。

## 已定值（10-19）

- `AOS_ENTRY` 預設 `_exec`（使用者已定；10-19 晚改，原 `.aos/exec`：「換。AOS_ENTRY 預設改成 _exec，工作區的 .aos/ stack 照舊」，[ideas § 13](../thinking/2026-10-19-ideas.md)），環境變數可覆寫。入口只佔資料夾的一層，跟 table 的一個 key 對上（`js["_exec"]`，C-72）；工作區的 `.aos/` 是 stack 的預設位置，跟入口無關。
- `AOS_STACK`（使用者已定）：預設 `$AOS_WS/.aos/`，是被叫的那個程式自己的 stack。它的子程式的 stack 由它自己訂（例如給 `$AOS_STACK/think`、`$AOS_STACK/act`），aos 不管巢狀。
- 工作區變數名 `AOS_WS`（使用者已定）。
- `aos-exec DIR [WS]`：WS 省略＝`-`；`-`＝沿用 `$AOS_WS`，沒設才用 `.`（使用者 10-19 定）。10-19 下班前放寬成 `aos-exec XXX [WS [args...]]`（N-58；這版未改）。
- `AOS_CF`、`AOS_CD`（使用者 10-19 下班前定，「同意做」）：實際被執行的檔、它所在的資料夾，aos-exec 每層覆寫（N-57；這版未做）。
- `#/` 尋址（使用者 10-19 下班前定，「#/。」「尋址一定值得。」）：`檔#/指標` 指進 JSON（N-62；這版未做）。
