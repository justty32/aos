# bin — aos 的指令（資料夾＝程式）

← [proto8](../README.md)｜慣例：[CONVENTION](../CONVENTION.md)｜demo：[demo](../demo/README.md)｜測試：`python3 -m unittest discover -s proto8/tests`

**2026-10-19 從 proto8-2 併進來。** 資料夾＝程式；入口＝資料夾裡 `$AOS_ENTRY`（預設 `_exec`；10-19 晚改，原 `.aos/exec`）指的檔。純標準庫 Python，在 WSL／Linux 跑。**aos 只訂環境變數**（`AOS_ENTRY`、`AOS_WS`、`AOS_STACK`、`AOS_CF`、`AOS_CD`），入口拿到之後「這次要做啥」怎麼收、怎麼用是入口自己的事（使用者 10-19，[ideas § 4](../thinking/2026-10-19-ideas.md)）；aos-exec 只是把多的 args／stdin 原樣交給它。

> **10-19 晚照下班前的新規則改完**（使用者 § 21「舊版一起改」；[ideas § 14～§ 20](../thinking/2026-10-19-ideas.md)；條文 [N-57～N-62](../NORMS/10-基礎設施-定義與工作區.md)、C-73、P-40）：`aos-exec` 從 sh 改寫成 Python，行為對齊 `proto8/impls/aos-exec`（C++ 參考實作）——入口四種、`aos-exec XXX`（XXX 可為資料夾、檔、`檔#/指標`、補找 `XXX.json`）、五個環境變數、字串轉向與繞圈偵測、cd 到入口檔所在的資料夾。跟 impls 版不同的只有：錯誤一行沒有代號（N-60 兩種都合）；inst 單子在行程內交給 `aos_inst.run()`（Python），不是 C lib。`aos-inst` 命令列留著（`#!/usr/bin/env aos-inst` 與小殼 `exec aos-inst _exec.json` 兩種寫法只在這版能用），但 aos-exec 不再依賴它。

> **10-19 夜（[ideas § 24](../thinking/2026-10-19-ideas.md)）**：`aos-loop`、`aos-fsm` 跟 impls 版一樣擋 SIGINT／SIGTERM／SIGHUP、轉給正在跑的那拍／那格、收完再以 128＋N 結束（共用新的 `aos_beat.py`）；aos 的程式（兩版的 aos-exec、aos-loop、aos-fsm）**都不動 PATH**，原樣傳下去，要叫的指令由呼叫端放進 PATH（`demo/run.sh`、測試都這樣做）。所以兩版 loop／fsm 的差異只剩：錯誤一行沒有代號；字串 run／格是叫 PATH 上的 `aos-exec` 子程序（impls 是子行程裡走 aos-exec 的公開 API）；單子沒有 `$ref`；fsm 的 `trace.jsonl`／`.state` 寫不了是 traceback（impls 是 `WriteFailed` 一行）。

```
sh proto8/demo/run.sh                                  # 建暫時工作區、放一題、跑 agent-bob 與 agent-ann、印工作區與 stack 樹
python3 -m unittest discover -s proto8/tests
PATH=$PWD/proto8/bin:$PATH aos-exec proto8/demo/agent-bob <工作區>   # 自己跑（aos 的程式不動 PATH，bin/ 由你放）
cd workspace && aos-exec ../agent-bob                  # 慣例用法（WS 省略＝-、沒設 AOS_WS 就用 cwd；bin/ 已在 PATH）
```

（舊的 `bin/aos` 與 `lib/` 那一套 10-16 實作是另一代，併入時進 git 歷史，見 [proto8 README](../README.md)。）

## 逐支說明

- `aos-exec XXX [WS [args...]]`（Python）：在 WS 這個工作區執行 XXX 這個程式。
  - **WS** 省略／`-`／空＝沿用現有 `AOS_WS`，沒設才用 `.`（呼叫當下的 cwd）；給路徑就用那個；轉絕對路徑設成 `AOS_WS`。`AOS_STACK` 沒設就用 `$AOS_WS/.aos/`，有設就沿用（相對路徑照呼叫當下的 cwd），都建好、轉絕對、結尾 `/`。
  - **找入口**（N-61、N-62）：XXX 先在第一個 `#` 切開（後面一定要 `/`，JSON pointer、`~1`＝`/`、`~0`＝`~`）。資料夾 → `XXX/$AOS_ENTRY`，沒有再找 `XXX/$AOS_ENTRY.json`（`$AOS_ENTRY` 是資料夾＝找不到、不往下補）；檔 → 就用它；不在、basename 沒有 `.` → 補找 `XXX.json`。解開捷徑得到實際的檔。
  - **種類**：有 `+x` ＝可執行檔，`exec` 它、內容不讀（沒 `#!`、exec 得到 ENOEXEC 時同 glibc `execvp` 改用 `/bin/sh 那個檔 args...` 跑；使用者 [ideas § 22](../thinking/2026-10-19-ideas.md)「乙」）；沒 `+x` 當 JSON 讀（第一行 `#!` 跳過，有 `#/` 就照指標取值）：全字串的非空陣列＝argv，`exec`（`argv[0]` 沒 `/` 時自己照 PATH 一段段 `execv`、找不到或沒 `+x` 換下一段；檔 `+x` 沒 `#!` 同樣改用 `/bin/sh` 跑，跟 `execvp` 一樣，§ 22）；有 `argv` 的物件＝inst 單子，行程內 `aos_inst.run()`、以子程式的碼結束（被訊號停掉＝128＋N）；沒 `argv` 的物件＝取 `[$AOS_ENTRY]` 再判一次（只往下一層）；字串＝路徑轉向，等同 `aos-exec 那個路徑`、相對路徑從寫著它的檔所在的資料夾算，走回走過的位置（檔＋指標）＝入口壞、訊息列出 `a → b → a`。
  - **開跑前**：export `AOS_WS`、`AOS_STACK`、`AOS_CF`（實際的檔）、`AOS_CD`（它所在的資料夾）；**PATH 不動、原樣傳下去**（ideas § 24，使用者「也套用，都不動path吧」；入口裡要叫 `aos-exec`、`aos-loop`、`aos-fsm`，由呼叫者事先把 `bin/` 放進 PATH；沒設 PATH 時照 `/bin:/usr/bin` 找 argv[0]，但不 export）；**cd 到 `AOS_CD`**；SIGPIPE 還原成預設再 exec（Python 預設忽略、會被入口繼承）。args 接在入口後面（單子／陣列：接在 `argv` 尾），stdin 不讀、原樣給入口；不收旗標。
  - **自己的錯**退 1、stderr 一行 `aos-exec: 原因`，原因開頭固定：`工作區不存在`、`入口不存在`（資料夾／檔／補 `.json` 都沒有、`#/` 指不到）、`入口壞`（沒 `+x` 又不是 JSON、種類不對、`#` 後不是 `/`、資料夾或可執行檔帶 `#/`、轉向繞圈）、`起不來`（exec 失敗）、`單子跑不起來`（aos_inst 的錯：欄位型別、`$env` 沒設、程式找不到、cwd 不在、串流開不了）、`建不了 AOS_STACK`、`usage: …`。
- `aos-inst FILE [args...]`（`aos_inst.py`，純標準庫）：讀一張單子，第一行是 `#!` 就丟掉，其餘當 JSON，跑一次。所以 `_exec` 第一行寫 `#!/usr/bin/env aos-inst`、下面接 JSON、`chmod +x` 就是入口（P-28 (A)）。認得的 key：`argv`（必填，args 接在後面）、`cwd`、`envs`、`stdin`、`stdout`、`stderr`、`stdout_append`、`stderr_append`、`timeout_ms`、`grace_ms`（沒寫 2000；逾時先 SIGTERM、過 grace 再 SIGKILL）；其他 key 忽略。子程式自成一個行程群組，逾時與轉來的訊號打整個群組（killpg），孫程式一起收掉（P-36）。單子裡任何位置的 `{"$env": 名, "path": 子路徑}` 換成該環境變數底下的路徑（P-31）。`argv[0]` 是 `+x` 但沒 `#!` 的檔（ENOEXEC）時照 execvp 的做法改用 `/bin/sh 那個檔 args...` 再起一次（使用者 § 21「不擋」，跟 impls 經 glibc `execvp` 一樣；§ 22 起 aos-exec 的可執行檔與 argv 陣列入口也一樣）。沒寫的串流接呼叫者的；命令列結束碼＝子程式的碼（不另吐結果 JSON），aos-inst 自己的錯退 1、stderr 一行 `aos-inst: 原因`。行程內用 `aos_inst.run(單子或檔)` 回 `{"code","signal","timed_out","pid","ms","received"}`（`received`＝跑的期間收到、轉給子程式的第一個訊號，沒有＝`null`；§ 24 加，給 loop／fsm 用）。（**impls 線沒有這支**：inst 是 C lib、不提供命令列，單子當入口時由 aos-exec 行程內跑、aos-exec 以子程式的碼結束；行程內的函數是 aos-exec 公開 API 的 `run_inst`。所以 `#!/usr/bin/env aos-inst` 與 `exec aos-inst _exec.json` 兩種寫法只在這版能用；同一個檔拿掉 `+x` 就是兩版 aos-exec 都認的 JSON 入口，P-40。使用者 10-19 晚，[ideas § 20](../thinking/2026-10-19-ideas.md)）**這版的 aos-exec 不叫 aos-inst 命令列**（行程內 import `aos_inst`）。
- `aos-loop loop.json`（Python）：`{"run": 子資料夾 或 一張單子, "max": 最多幾圈}`，每圈 `aos-exec <run>`（`run` 是物件＝單子，行程內 `aos_inst.run()`，取它的 `code`）；檔讀不到／不是 JSON／`run` 不對／單子壞 → 退 1、stderr 一行 `aos-loop: 原因`。子程式結束碼 0＝下一圈、**10＝要求停（loop 以 0 結束）**、其他非 0＝失敗（loop 以原碼結束）；跑滿 max 圈也以 0 結束、stderr 不寫（N-43 正常退出；有沒有跑滿看 `trace.jsonl` 行數）。**訊號**（§ 24，同 impls）：整支程式的壽命都接著 SIGINT／SIGTERM／SIGHUP——那拍跑到一半收到就轉給它（字串 run＝`os.kill` 給那個 `aos-exec` 子行程，同一個行程群組、不另設 SIGKILL 期限；單子＝`aos_inst.run()` 轉整群、過 `grace_ms` SIGKILL），等它結束、不起下一拍，以 128＋第一個收到的訊號結束、stderr 不寫；拍與拍之間收到就直接 128＋N。終端機 Ctrl-C：字串 run 那拍同群組，會收到兩次（直接一次、轉的一次）。
- `aos-fsm FSM.json`（Python，import `aos_inst`）：一拍只跑一格。`{"start": "idle", "states": {名: {"val": 子資料夾名或單子, "next": 下一個狀態}}}`；讀 `$AOS_STACK/state`（沒有＝start；純文字一行；寫的時候先寫 `.state` 再改名，N-05），`val` 字串＝`aos-exec` 它（相對路徑從 cwd 算）、物件＝行程內 `aos_inst.run()`；每拍在 `$AOS_STACK/trace.jsonl` 追加一行 `{"at","state","code","signal","timed_out","ms"}`（`at`＝這拍開始的 UTC 時間，P-38）；格的碼 0 才把 next 寫進 state，然後以格的碼退出（10 與其他非 0 原樣往上、state 不動）。只看結束碼、不讀格的 stdout、不轉述格的 stderr。沒設 `AOS_STACK`／表壞／查不到格／單子壞 → 退 1、stderr 一行 `aos-fsm: 原因`。**訊號**（§ 24，同 impls）：跑格期間收到就轉給那格（同 aos-loop），等格結束、**trace 與 state 照常寫完**（格收好自己退 0 就照樣換狀態），再以 128＋N 結束；跑格之前就收到＝不跑、直接 128＋N。
- `aos_beat.py`（§ 24，aos-loop、aos-fsm 共用）：`block()` 接住三個訊號、`take()` 取拍外收到的、`run(字串或單子)` 跑一拍回 `{"code","signal","timed_out","ms","received"}`（字串＝子行程 `aos-exec <它>`、轉訊號給它；單子＝`aos_inst.run()`）。對齊 impls aos-loop 的 `block_signals`／`take_signal`／`run_beat`。

執行中狀態（`state`、`trace.jsonl`、`plan`、`current`）在 `$AOS_STACK`（預設 `$AOS_WS/.aos/`）；工作區只放交辦的東西與成果（`inbox/`、`out/`、`done/`）；定義資料夾不被寫，所以同一個 agent 可同時被兩個工作區跑。結果＝工作區內容；沒有別的結果通道。

## 已定值（10-19）

- `AOS_ENTRY` 預設 `_exec`（使用者已定；10-19 晚改，原 `.aos/exec`：「換。AOS_ENTRY 預設改成 _exec，工作區的 .aos/ stack 照舊」，[ideas § 13](../thinking/2026-10-19-ideas.md)），環境變數可覆寫。入口只佔資料夾的一層，跟 table 的一個 key 對上（`js["_exec"]`，C-72）；工作區的 `.aos/` 是 stack 的預設位置，跟入口無關。
- `AOS_STACK`（使用者已定）：預設 `$AOS_WS/.aos/`，是被叫的那個程式自己的 stack。它的子程式的 stack 由它自己訂（例如給 `$AOS_STACK/think`、`$AOS_STACK/act`），aos 不管巢狀。
- 工作區變數名 `AOS_WS`（使用者已定）。
- `aos-exec DIR [WS]`：WS 省略＝`-`；`-`＝沿用 `$AOS_WS`，沒設才用 `.`（使用者 10-19 定）。10-19 下班前放寬成 `aos-exec XXX [WS [args...]]`（N-58；10-19 晚這版也改了）。
- `AOS_CF`、`AOS_CD`（使用者 10-19 下班前定，「同意做」）：實際被執行的檔、它所在的資料夾，aos-exec 每層覆寫（N-57；已做）。
- `#/` 尋址（使用者 10-19 下班前定，「#/。」「尋址一定值得。」）：`檔#/指標` 指進 JSON（N-62；已做）。
