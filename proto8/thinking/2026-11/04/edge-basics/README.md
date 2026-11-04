← [2026-11-04](../README.md)｜同晚 A 線（llm kernel）：[think-as-function 08](../think-as-function/08-邊緣狀況實測.md)｜B 線（daemon／aos-agent）：[four-elements 09](../four-elements/09-邊緣狀況實測-11-04-夜.md)

# 基礎積木邊緣狀況實測（11-04 夜，C 線：aos-exec、aos-loop、aos-json、aos-post、aos-tools、aos-mcp）

使用者 11-04 夜（在打遊戲、沒空回答）：「你先多嘗試，看看各種邊緣狀況」「我還在打遊戲，麻煩你繼續...」。

做法：scratchpad 自建測試場（不碰 `~/code/playground`），以 `proto8/impls`、`proto8/bin`、`proto8/extras/ai_tools` 現行程式與 docs 為準；沒開模型、沒用真 LLM。試了 **44 類情境**（一類裡多半好幾種輸入），**修了 6 處**（4 個 commit），**1 題**要你看。改 C++ 的只重建了 aos-exec、aos-post、aos-json 本身；aos-loop／aos-fsm／aos-daemon／aos-llm-kernel 靜態連著 libaos-exec、libaos-post，下次建置才帶上新的錯誤訊息與名字檢查（只影響報錯，不影響正常路徑）。

處理欄：**已修**＝附 commit；**列題**＝見下方；**天然**＝照設計／docs 已寫就是這樣；**風險自擔**＝照你「很多都是自己要承擔的風險」的口徑不處理，只記在這裡。

## 結果表

| # | 情境 | 怎麼重現 | 結果 | 處理 |
|---|---|---|---|---|
| 1 | aos-exec 的 XXX 是空字串 | `aos-exec ""`（例 `aos-exec "$X"` 而 X 沒設） | 修前：當成 `.`，**默默跑 cwd 的 `_entry`**；修後：`ArgumentsBad …（XXX 是空字串）` | 已修 `3a28f5fa` |
| 2 | JSON 字串轉向寫 `""` | `{"r": ""}`、`aos-exec 'r.json#/r'` | 修前：轉到寫著它的資料夾；修後：`EntryBad 轉向的路徑是空字串` | 已修 `3a28f5fa` |
| 3 | 單子的 stdout／stderr 上層資料夾不在、是資料夾、上層唯讀；stdin 不在 | 各一 | 修前：一律「串流開不了（stdin／stdout／stderr 其中一個）」；修後：說哪個串流、哪個路徑、為什麼（上層不在時提示 `stdout_mkdir: true`） | 已修 `3a28f5fa` |
| 4 | `stderr_merge: true` 又寫 `stderr` | 單子兩個都寫 | 修前：`PathConflict libaos 回報（true）`；修後：`PathConflict stderr_merge 是 true 又寫了 stderr（二選一）` | 已修 `3a28f5fa` |
| 5 | `檔#/指標` 指到數字 | `aos-exec 'c.json#/num'` | 修前：訊息只有檔名、沒有 `#/num`；修後帶指標 | 已修 `3a28f5fa` |
| 6 | `.env` 帶 BOM（Windows 記事本） | `printf '\xef\xbb\xbfA=1'` | 修前：「名字要是英數字和底線」（肉眼看不出錯在哪）；修後多一句「檔頭有 BOM，存成不帶 BOM 的 UTF-8」 | 已修 `3a28f5fa` |
| 7 | 單子各 key 型別錯、`argv` 空、`timeout_ms` 0／負／小數、`envs` 值不是字串、`cwd` 不在、`cwd_mkdir` 撞到檔 | 各一 | 都是 `EntryBad`／`LaunchFailed`／`MkdirFailed`，訊息說哪個 key、什麼值 | 天然 |
| 8 | `envs_clear: true` | 跑 `env` | 只剩五個 `AOS_*`；PATH 也沒了（sh 用自己的預設 PATH） | 天然（docs 已寫） |
| 9 | 逾時、`grace_ms` 0、子程式擋 TERM | `sleep 5`／`trap "" TERM` | 0.3 秒 137；擋 TERM 的過 grace 被 KILL，137 | 天然 |
| 10 | `.env` 各種壞：引號沒收尾、`${沒設}`、沒 `=`、`\r\n`、沒結尾換行、`.env` 是資料夾、壞捷徑 | 各一 | 都 `DotenvBad` 帶檔名行號、不印值；`\r\n`、沒換行照讀 | 天然 |
| 11 | `AOS_ENTRY` 寫 `.env`、`../自己`、絕對路徑 `/bin/echo` | `.env` 裡設 | `.env`＝不是 JSON；繞回＝`EntryBad 資料夾繞圈`；絕對路徑被當成一段段相對路徑（`…/v1/bin 不是資料夾`） | 天然（N-61：入口名是一段段走，不收絕對路徑；訊息看得出走到哪） |
| 12 | `#/` 指標：`~0`／`~1`、`#/arr/00`、`#/arr/-`、`#/~2`、`#`、`#a`、空 key `#/`、補 `.json` 再加指標 | 各一 | 照 RFC 6901；前導 0、`-`、壞跳脫都「指不到」；`#` 後不是 `/`＝`EntryBad` | 天然 |
| 13 | loop 的 `exec` 寫成 `["sh", "-c", …]` | loop.json | `aos-exec: EntryMissing 入口不存在：sh`——exec 陣列是「aos-exec 目標＋參數」，不是 argv | 天然（要 argv 寫單子 `{"argv": …}`） |
| 14 | **aos-loop README 的範例** `{"exec": ["aos-fsm", "fsm.json"]}` | 照抄 | 同 #13，範例本身跑不起來 | 已修 `78822851`（範例改單子，附一行注意） |
| 15 | loop.json `exec: ""` | — | 修 #1 後由那次的 aos-exec 報 `ArgumentsBad`（loop 那行「第 1 次  失敗」誰是空的） | 天然 |
| 16 | `max`／`interval_ms` 負、小數、`1e2`、字串、超大；`state: ""`、`/abs/…`、`sub/…`；`ctl` 與 `state` 同名；`ctl: "../x"` | 各一 | 型別錯＝`CfgBad`；寫不了的位置＝`WriteFailed`；同名＝state 被當 ctl 讀（沒 `cmd`、無害）；`../` 出 stack 照用 | 天然／風險自擔（同名、出 stack） |
| 17 | ctl：pause／壞 cmd／不是 JSON／resume 帶 `max`；跑著把 `max` 改小到已跑次數以下；改成 0 | 寫 ctl.json | 壞的進 `ctl_warning`、維持原狀；改小＝下一次就收工退 0 | 天然 |
| 18 | 跑到一半 SIGTERM、睡 interval 時 SIGINT、身體自己被 kill -9、沒設 `AOS_STACK`、跑著把 stack 刪掉 | 各一 | 143／130 寫 `stopped`；身體 137 照轉；`StackMissing` 說「不要窗就寫 null」；stack 被刪＝`WriteFailed` 退 1 | 天然 |
| 19 | fsm 的 `stage.txt` 寫怪值、前後空白、兩行、非 UTF-8、是資料夾；`next` 指到不在的格 | 各一 | `StateUnknown`／`StateBad`／`CfgBad`，都說清楚；前後空白照去 | 天然 |
| 20 | aos-json `set` 負數 | `set 'x.json#/a' -5` | 本來就能寫；但「多了參數」的提示說「寫在 -- 後面」，照做反而把 `--` 當值 | 已修 `78822851`（提示與 docs 改對） |
| 21 | aos-json 陣列 `#/c/3`（尾巴外）、`#/c/-`；穿過數字；`--parents`；值不是 JSON；整份檔是壞 JSON 時 `set` 整份 | 各一 | 叫你用 append；`TargetBad`；壞檔一律 `FileBad`、**整份覆蓋也不准**（不毀原檔） | 天然 |
| 22 | aos-json `$ref` 互指、指到資料夾；沒加 `--follow` 改穿過 `$ref` 的位置；寫捷徑 | 各一 | 繞圈、讀不到都 `DirectiveBad`；`FollowMissing` 說要加 `--follow`；寫到捷徑指的檔、捷徑留著 | 天然 |
| 23 | aos-json 寫唯讀檔（444） | `chmod 444`；`set` | **照寫**（rename 換新檔、權限照設回 444） | 風險自擔（同 `sed -i`）；唯讀資料夾裡＝`WriteFailed` |
| 24 | aos-json 重複 key | `{"a":1,"a":2}` 再 `set /b` | get＝後者；寫回時前一個 `a` 消失（docs 已寫「整份重排」） | 天然 |
| 25 | aos-json 大檔 | 15 MB、20 萬個 key 的物件；100 MB、20 萬元素的陣列 | **物件 key 很多時是平方慢**：2 萬 key 0.17 秒、4 萬 0.8 秒、20 萬 16 秒（get、set、peek 都一樣；aos-exec 讀同樣的 JSON 也是）。陣列不受影響：100 MB 陣列 get 0.4 秒、append 0.7 秒 | 天然（nlohmann 的 `ordered_json` 保序的代價；aos 的設定、表、history 都遠低於上萬 key） |
| 26 | aos-post 信件名稱帶換行 | `send box "$(printf 'a\nb')"` | 修前：收下；`take-all` 一行一個，**印成 `a`、`b` 兩個不存在的名字**，接著 `see a` 找不到；修後：`ArgumentsBad 信件名稱不能有換行、tab 等控制字元` | 已修 `c193edbb` |
| 27 | 名字含空白、中文、`~`、12 位數字沒點、14 位數字＋點、300 字、`..` | 各一 | 照收（後兩個：`MkdirFailed File name too long`、`ArgumentsBad`）；只有「12 位數字＋點」擋（像有序名） | 天然 |
| 28 | `done --reply` 時 `reply_to` 信箱已被刪 | 寄、take、刪回信信箱、done --reply | 修前：`MailboxMissing 信箱不在：…/rb`（看不出是回信）；修後：「回信寄不出去（L 的 reply_to），原信留在 cur/：…」 | 已修 `c193edbb` |
| 29 | 20 個 `send --ordered` 同時寄 | 背景平行 | 1～20 號不重不漏、`order.json`＝20 | 天然 |
| 30 | `order.lock/` 是空資料夾（持有者剛 mkdir 就死）、名牌是死掉的 pid | 手建 | 空的等 10 秒收屍後寄出（我第一次用 3 秒 timeout 以為卡死）；死 pid 當場收 | 天然（aos-lock ⑤） |
| 31 | `order.json` 壞、負數、序號超過 12 位 | 手改 | 壞＝`OrderBad`；**13 位的名字不再算有序**，排到無序後面 | 天然（docs 已知限制「序號滿 12 位之後不管」） |
| 32 | 被 timeout 打斷的 `send --ordered` | `timeout 3` | 半截留在 `tmp/` | 天然（決定 23：收屍歸寄信人上層） |
| 33 | regret 已處理的、done 沒 `--reply` 的帶 `reply_to` 信、`--reply` 對沒 `reply_to` 的信 | 各一 | `RegretFailed`；不回信直接收；不回、不印、退 0 | 天然 |
| 34 | `cur/` 裡壞信、`new/` 裡放一般檔、沒有 `cur/` 時 `see`、寄到沒 init 的信箱 | 各一 | 壞信 `LetterBad`、done 丟掉；一般檔認領得到、算壞信；`MailboxMissing` 叫你先 init | 天然 |
| 35 | aos-tools `--tooldef` 卡住、而且起了孫行程 | `#!/bin/sh` 背景 `sleep` | 修前：10 秒 `ToolDefBad`，**孫行程留著繼續跑**；修後：整群收掉、沒殘留 | 已修 `5183b00a` |
| 36 | aos-tools 可執行檔沒 `#!`、名字有空白、`_tooldef.json` 不是物件／description 不是字串／壞 JSON／不在 | 各一 | 都說清楚（含 `ToolDefMissing` 提示 11-04 改名） | 天然 |
| 37 | 登記的工具有一個壞掉 | 把某個 `_tooldef.json` 改壞再 `ls` | 整份 `ls` 失敗（帶工具名）；aos-mcp 的 tools/list 也整份失敗 | 風險自擔（照 aos-tools「不猜不跳過」） |
| 38 | `tools.json` 壞、`tools` 是陣列、項是字串、路徑不在、`{}` | 各一 | `RegistryBad`／`PathMissing`；`{}`＝沒工具 | 天然 |
| 39 | call 資料夾工具時 arguments 不是 JSON、空、陣列 | `echo notjson \| aos-tools call echo` | 原樣進 stdin，工具自己判 | 天然（aos-tools 不替工具驗） |
| 40 | call 可執行檔工具：沒 `AOS_STACK`、`AOS_STACK` 資料夾不在、相對路徑 | 各一 | `StackMissing`；不在的會建；相對照 cwd | 天然 |
| 41 | aos-mcp：沒這個工具、壞 JSON 行、不是物件、不認得的方法、notification、arguments 是字串 | 一串餵 stdin | 各回對的 JSON-RPC 錯誤碼；字串 arguments 照轉 | 天然 |
| 42 | aos-mcp：工具逾時（還起了背景子行程） | `_metainfo.json` `time_ms.max` 500 | 0.5 秒「整群收掉了」，沒殘留 | 天然 |
| 43 | aos-mcp：工具失敗、原因只在 stderr | 工具 `echo partial; echo why >&2; exit 3`；入口檔壞（aos-exec 報 `EntryBad`） | **外部 agent 只看到 `partial` 或「退 1、stdout 沒東西」**；原因（`why`、`aos-exec: EntryBad …`）只進 aos-mcp 的 stderr（MCP 用戶端的 log），agent 看不到 | **列題 1** |
| 44 | aos-mcp：跑著時登記檔被改壞；啟動時不在、壞 | 各一 | 啟動＝`ToolMissing`／`ToolsBad` 退 1；跑著＝那則 tools/list 回錯、不退，但訊息只有「aos-tools ls … 退 1」（原因同 #43 在 stderr） | 併題 1 |


## 要你看的題

### 題 1：工具失敗時，外部 agent（Claude Code 等）看不到原因

**白話**：Claude Code 經 aos-mcp 叫 aos 的工具，工具失敗了，Claude 只會收到「失敗」加上工具印在 stdout 的東西。真正的原因——工具自己寫在 stderr 的那句，或 aos-exec 說的「入口壞」「找不到入口」——只進了 aos-mcp 自己的 stderr，那是 MCP 用戶端的 log，Claude 看不到。所以常見的情況是 Claude 收到「aos-mcp: CommandFailed bin8 退 1、stdout 沒東西」，不知道該改什麼、只能亂試（#43、#44）。

這跟「每層不偷讀下層的 stderr」（C-56）有點打架，所以拿來問你。

**選項**：
1. **（推薦）失敗時把那次 stderr 的最後一段（例最多 2 KB）附在回給 agent 的文字後面**：stderr 照樣也印到 aos-mcp 自己的 stderr；成功時不附。後果：aos-mcp 要接住工具的 stderr（現在是直接繼承）；agent 能看到「aos-exec: EntryBad …」這種句子，自己修得動；C-56 要加一句例外（「出口要給外部 agent 看原因」）。
2. **只在 stdout 是空的時候附**：後果：工具印了一半再失敗（#43 的 `partial`）時照舊看不到原因。
3. **不管**：照 C-56，原因在 log。後果：外部 agent 看到失敗卻不知道為什麼，人要去翻 MCP log。

## 沒測到的

- aos-agent／agent-fsm 的 act 格怎麼把工具失敗交給腦（B 線範圍）；aos-mcp 的 `--enable-logs`、多份登記檔撞名。
- aos-loop 內嵌單子在新 libaos-exec 下的訊息（aos-loop 沒重建，見開頭）。
