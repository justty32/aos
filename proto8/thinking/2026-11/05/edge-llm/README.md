# 2026-11-05 llm kernel 改掛 daemon 之後的邊緣狀況實測（A 線）

← [thinking README](../../../README.md)｜日 [2026-11-05](../README.md)｜依據：[kernel-daemon 08 實作結果](../kernel-daemon/08-實作結果.md)、[04 邊緣狀況](../kernel-daemon/04-邊緣狀況.md)；昨天測過的不重測：[think-as-function 08](../../04/think-as-function/08-邊緣狀況實測.md)｜程式：[aos-llm-kernel](../../../../impls/aos-llm-kernel/README.md)、[aos-llm](../../../../impls/aos-llm/README.md)

使用者 11-05：「你先自己多測試測試各種邊緣狀況，有問題就修。當然，我會時不時回來看一下，有事可以問我。」——他不在線上，照推薦代定。判準：會壞資料、卡死、誤導的錯誤訊息、文件與行為不符就修；使用者自己亂用、成本高的寫一句文件。

做法：WSL `/tmp/edgeA-1`，一台 llm daemon（`aos-exec --stack . def`，`timeout_ms` 8000／4000），自寫幾個 endpoint 函數（退 3、輸出不是 JSON、空輸出、60 MB、卡住、不理 TERM 卡住、留孫行程、慢 3 秒的假腦）。LM Studio 沒開（Windows `localhost:1234` 連不上），沒去開它：真腦 08 已測過。

## 修了什麼（commit `07305e54`）

1. **信箱 `new/` 裡混進一個一般檔＝llm daemon 永遠起不來**：kernel 把它當信認領、寫 `reply.json` 失敗退 1，daemon 照 P-20 停；重起時又把它改名回 `new/`、又死。所有 `ask` 默默等。改成 `new/`、`cur/` 只看子資料夾（信＝資料夾，N-16），一般檔不理。
2. **endpoint 函數不理 SIGTERM 時，逾時被說成「退 137」**：aos-exec 先 TERM、寬限後 KILL，退 137；kernel 只把 143 當逾時。改成 143 或 137 而且過了 `timeout_ms`＝`EndpointFailed 逾時`。
3. **`ask` 等的時候回信信箱被刪，訊息說「信在信箱裡不見了」**：改成直接說「回信信箱不見了（kernel 寄不進回信）」。

另外在 aos-llm 已知限制補一句：`AOS_LLM_KERNEL` 指錯資料夾的三種常見樣子、怎麼對（文件，不改行為；昨天使用者對這題說過「自擔」）。

## 實測表（沒寫「已修」的都是照設計走、沒問題）

| 類 | 情境 | 結果 |
|---|---|---|
| endpoint 失敗 | 退 3／輸出不是 JSON／空輸出 | `EndpointFailed 退 3：<stderr 第一行>`／`ReplyBad`／`ReplyBad`，只那一封 |
| | 卡住（理 TERM） | 8 秒 `EndpointFailed 逾時` |
| | 卡住、不理 TERM | 修前「退 137：aos-loop…」，**已修**＝逾時 |
| | 60 MB 輸出 | 6 秒拿到，信箱收完只剩 32 KB |
| | 留孫行程（`(sleep 30) &`，佔著／不佔 stdout） | 都馬上回答；孫行程活到自己結束（見別線 2） |
| | 端點 `localhost:9` | 這台 WSL 是 mirrored 網路，`localhost:9` 會卡住不拒絕，所以是逾時、不是「連不上」（環境，不是 bug） |
| 很多信 | 200 封、`slots` 2 | 31 秒全回、沒錯、表上不留列、ctl 信箱不堆 |
| | 200 封、`slots` 50 | 3.7 秒全回 |
| | 6 封 low 之後 1 封 high、`slots` 2 | high 排在第一批之後就跑（第 3 個回） |
| | 額度 `max_calls` 2、一次 4 封 | 2 封答、2 封 `BudgetMissing`（在飛的有算進去） |
| 壞信 | `letter.json` 不是 JSON／沒 `letter.json`／沒 body | 各回 `LetterBad`，kernel 照跑 |
| | `new/` 裡一個一般檔 | **已修**（上面 1） |
| | 信資料夾 555（寄信的人自己弄的） | 改名不動，一直留在 `new/`、寄信的一直等；不影響別封。自擔 |
| | daemon ctl 信箱裡一個一般檔 | aos-daemon 記一行 `mailbox_warning`、照跑 |
| 回信信箱 | `ask` 等的時候刪掉 `mailbox/reply` | kernel stderr 一行、信照刪；修前訊息誤導，**已修**（上面 3） |
| `ask` 中斷 | 在飛時 Ctrl-C | 跑完後回信被撤回，`reply/new` 乾淨 |
| | 還在 `new/` 時 `kill -9` ask、之後才起 llm daemon | 那封被丟掉、沒跑（`counter_all_calls` 不變） |
| `AOS_LLM_KERNEL` 指錯 | 不在 | `LlmKernelMissing` |
| | 指到 `def/`、指到漏了 `--stack .` 起的資料夾 | 默默等；指 `def/` 還會在原始碼裡多一個 `mailbox/`——文件補一句，見題 1 |
| 啟停順序 | 同一個 stack 起第二台 | `DaemonRunning`，第一台照跑 |
| | 漏了 `--stack .`（`aos-exec def`） | stack 變成 `.stack/`，信箱在那裡 |
| | 在飛時整群 `kill -9`、再起 | 重掛、答完（一封） |
| kill -9 各時點 | 認領了、寄了掛信、還沒寫 `proc.json`（手工擺出這狀態再起） | 只答一次，信箱乾淨 |
| 兩台 agent 寄信 | 兩個回信信箱路徑長得一樣（`ws1/.stack/think/reply`、`ws2/…`） | `reply_to` 存相對、各自收到自己的 |

沒測：磁碟滿（WSL 沒 sudo、掛不了小 tmpfs）；跨帳號信箱；LM Studio 真腦（08 已測過）。

## 代定（可翻案）

1. 信箱裡的一般檔＝不理（不刪、不回信）：信只會是資料夾，不知道是誰放的，不碰最省事。
2. 137 只有「過了 `timeout_ms`」才算逾時；沒到時限的 137（例如有人 `kill -9`、OOM）照舊報 `EndpointFailed 退 137`。
3. 信資料夾 555 卡在 `new/`：不修（寄信的人自己弄壞的，又不影響別封）。

## 別線看到的（沒改，交頂層）

1. **aos-daemon**：身體的執行檔一時不能執行（我重建 aos-llm-kernel 的那一刻剛好拍到）＝daemon `LaunchFailed`、整台停（P-20）。開發時才會撞到；要不要讓「起不來」重試幾拍，是 aos-daemon 線的事。
2. **aos-exec**：endpoint 函數丟到背景的孫行程，在函數結束後還活著（沒人收）。只有逾時才會收整群。
3. **aos-daemon**：一般檔進 ctl 信箱只會記 `mailbox_warning`，正常；`mailbox_warning` 只留最後一封（04 #4 已知）。

## 使用者裁定

> 11-05（頂層轉達）：題 1「按照推薦」＝(a)。另一句新規矩：「我發現我們做出來的程式，輸出的各種東西，裡面都有中文...全都用英文吧」——今天新加／改過的輸出都用英文。

落實：aos-llm `send`、`ask` 寄之前看 `$AOS_LLM_KERNEL/state.json`（不在＝沒起過或指錯；`phase` 不是 running／stopping 或 pid 不在＝停了）→ stderr 一行 `aos-llm: warning: …`，照寄照等。手跑：沒起過、指 `def/`、Ctrl-C 停、kill -9（state 還寫 running、pid 不在）四種都提醒；正常跑不印。上面修的 2、3 兩條訊息也改成英文。

## 原本的題（已裁）

**題 1：llm kernel 不在、或 llm daemon 停了，`ask`／`send` 一聲不吭地等**
昨天的題 1（`AOS_KERNEL` 打錯默默寄）你說「自擔」，今天沒改行為、只補了文件。不過變數的意思改成「llm daemon 的 stack」之後，多了兩種常見的指錯（指到 `def/`、起的時候漏了 `--stack .`），還有一種新情況：kernel 出錯讓 llm daemon 整台停了，寄信的人也看不出來。
- (a) **只多印一行警告、照樣寄、照樣等**（推薦）：寄的時候 `$AOS_LLM_KERNEL/procs_state.json` 不在（不是一台 daemon）、或 `state.json` 顯示 daemon 已經停了，就在 stderr 印一行「這裡沒有在跑的 llm daemon，信會等到它起來」。後果：先寄、後起 kernel 照樣可以；人一看就知道指錯或 kernel 停了；多一次讀檔。
- (b) 照現況，靠文件那一句自己對。

## 別線後續（11-05 晚）

- 別線 1（身體一時不能執行＝整台停）→ 使用者裁 edge-daemon 題 1「記一行、下一圈再跑 (Recommended)」，`34f17425` 落實，見 [edge-daemon 裁定落實](../edge-daemon/README.md#裁定落實11-05-晚隊長)。
- `AOS_LLM_KERNEL` 相對路徑改照「基準點＝管我的 daemon 的 stack／人殼＝cwd」解（`59395748`，代定）。
- 問腦 proc 出錯結束現在會被 daemon 留 `stopped`＋reason，aos-llm-kernel 當收尾處理（`d1ed1abe`）。
