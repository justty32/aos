← [notes 索引](README.md)｜[教程](../tutorials/README.md)｜同一輪的另一隊：[advice-r1（check／ls）](2026-09-24-advice-r1.md)

# 2026-09-24 advice-r1 B 隊：README 教程拆成 tutorials/

使用者今天的建議（原話）：

- 「proto5/readme.md 中的 #2 中，AOS_LLM_CONFIG 是在 kernel.json 中設置的，希望在 #1 中就順便設置。因為這個 llm config 一定是設置好之後很久都不會變。」
- 「readme 中的這些範例教程，希望可以獨立到 tutorials/。」主題五個：daemon／kernel 的設定啟動關閉、kernel 的一次性與持續性任務、第一個 agent、加工具與暫停、管一大堆 agent。

## 拆了什麼

| 篇 | 從舊 README 哪裡來 | 新加的 |
|---|---|---|
| [01 daemon 和 kernel](../tutorials/01-daemon-kernel.md) | 第 1、2 段、第 5 段的 kernel／daemon 停機、「每天重開機」 | `env.sh` 環境檔（PATH、兩個家）；`llm.json`＋`kernel.json`（含 `AOS_LLM_CONFIG`）放在同一步一次寫好，講清楚「內容隨時改、路徑很久不動、真要搬怎麼做」；`ls` 各段怎麼讀、`-v`／`--json` |
| [02 kernel 的工作](../tutorials/02-kernel-jobs.md) | 第 3 段 | once 不等＋`ack`、一直失敗被退件、`rm`、回音怎麼判（0／101／100／其他） |
| [03 第一個 agent](../tutorials/03-first-agent.md) | 第 4 段、第 5 段的 agent stop | 家的結構表、`aos-agent check --probe`（新指令）、「listen --wait 只等下一則」的陷阱 |
| [04 工具與暫停](../tutorials/04-tools-and-pause.md) | 第 6 段、第 4 段的 pause／continue | 工具壞了（chmod -x）實跑、看 history.json、故意改壞 port 看連敗暫停與兩階段恢復 |
| [05 管一大堆 agent](../tutorials/05-many-agents.md) | 第 4 段「agent 多了要多開 cpu」一句 | 活加 cpu（改 `K/info.json`、不用 halt／boot）、`for` 迴圈批次 init／check／start／stop、平行 `say --wait`、`ls` 全局表、health 三階段、`continue --all`；結尾指向 proto5-2 |
| [06 附錄：手寫家](../tutorials/06-appendix-manual-home.md) | 「附：不用 init 的手動做法」 | — |

每篇：目標、前提、照抄指令（heredoc）、你會看到什麼（實跑摘錄）、底下在幹嘛（連 spec 小檔）、常見錯誤表、收工。大小 2～8.6 KB（05 略超 8 KB，是實際的 `ls` 表佔的）。

## README 留什麼

「這是什麼」一段＋架構圖（daemon／三種池的 cpu／kernel／agent）、「五分鐘看到 agent 回話」（14 行指令，01＋03 的濃縮）、指令一覽（每個指令一句＋指向哪篇教程）、去哪讀，後面的規範表、程式表、筆記、還沒定的原樣保留（規範表的 aos-agent 列補了 `check`）。19.4 KB → 11.5 KB。

錨點：`grep -rn 'README.md#' proto5/ wf/` 沒有任何連進 proto5 README 段落的連結（只有 notes 索引自己的錨點），不用改。歷史筆記裡的「README 第 N 段」是當時的紀錄，照原樣留。

## 對接 A 隊

A 隊（`aos-agent check`、`ls` 對齊表＋`-v`＋`--json`）合進 main 後 rebase；教程原本留的 9 處 TODO 全換成新 CLI 的實際輸出，0 處剩下。
`aos-kernel check --agent` 在教程與 README 裡都已經改成 `aos-agent check --target … [--probe]`；ls 的說法照新表格（bad 的提示在表下另起一行、agent 暫停標在「備註」欄）。

## 實跑

工作目錄在 scratchpad `advice-r1-b/`（`$HOME/aos-try` 換成那裡），模型走 LiteLLM `localhost:4000`／`deepseek-chat`，沒碰 LM Studio／ollama。
做法：寫一支小腳本把每篇的 ```sh 區塊**原樣**抽出來依序跑（02 以後先 `. env.sh`，模擬新終端），只替換三處：家的路徑、`listen --follow` 前加 `timeout 8`（代替 Ctrl-C）、`ack` 的單名換成實際那張。

| 篇 | rebase 後最後一輪 | 時間 |
|---|---|---|
| 01 | 過（boot 4 顆、halt、每天重開機 boot 回來 `health ok`） | 2 秒 |
| 02 | 過（once 等／不等＋ack、count done runs 3、boom bad 10 次、rm） | 37 秒 |
| 03 | 過（check --probe 全 ok、say --wait 約 12 秒回話、listen 三種、status、stop） | 31 秒 |
| 04 | 過（add 工具 5555、chmod -x 後 check bad＋模型看到 exit 126、pause／continue、port 改壞 15 秒內連敗暫停、continue 後回話） | 55 秒 |
| 05 | 過（活加到 8 顆、三個 agent 平行自我介紹、ls 全局、三個一起連敗暫停、`continue --all` 3／4、批次 stop） | 42 秒 |
| 06 | 過（手寫家 check ok、20 秒內報時） | 22 秒 |
| README 五分鐘 | 過（另開一個乾淨的家，16 秒看到回話；停機那行也跑過） | 16 秒 |

rebase 前用舊 CLI 也全跑過一輪（那時 `aos-agent check` 暫以舊指令代替）。跑完 `pgrep -fa advice-r1-b` 與本 worktree 的 `proto5/cli` 行程都是空的。

## 發現的文件／行為不符（沒改 lib／spec，攤給使用者）

1. **`aos-agent init` 的提示指到不存在的段落**：`lib/aos_agent_init.py:36` 印「見 proto5/README.md 第 2 段」，README 瘦身後沒有第 2 段了。建議改指 `proto5/tutorials/01-daemon-kernel.md`。
2. **舊 README 的家放 `/tmp/aos-try`，卻說「關機後家還在」**：很多系統開機會清 `/tmp`（tmpfs），每天重開機那段就沒東西可開。教程改用 `$HOME/aos-try`。
3. **舊 README 的 daemon 那行只重導 stderr**（`2>>daemon.log &`）：daemon 的 stdout 還接著終端或管線；在 `… | sed` 這種管線裡跑，管線要等 daemon 退出才收得了（我實際卡住一次）。教程改成 `setsid aos-daemon boot >>$W/daemon.log 2>&1 </dev/null &`，預設就用 `setsid`（r4 兩份試玩都說放在區塊外的那句容易漏）。
4. **用路徑 `pgrep` 找不到 daemon**：daemon 的命令列只有 `aos-daemon boot`，家是從 `AOS_DAEMON_HOME` 來的，`pgrep -fa <工作目錄>` 抓不到它，只抓得到 cpu。試玩任務書要人「pgrep 工作目錄要空」時會漏掉 daemon；要用 `aos-daemon halt` 或看 `D/state.json` 的 `pid`。
5. **舊 README 叫人加 cpu 要 halt→改 info→boot**：kernel 規範 [§1.1](../spec/kernel/home.md) 說每格重讀 info、多的 cpu 下格就拉。實測活改 `K/info.json` 3 秒內 `ls` 就是 8 顆、帳本的 `cpus` 也有新的；教程照規範寫「不用 halt、不用 boot」。
   但「活加的 cpu 真的有被派到工作」這次沒直接看到：第一輪 4 個 agent 的反覆工作錯開、同時到期的最多 2 個，所以只用到 0、1；重 boot 後 4 個同時到期才看到 0～3 都忙。沒看到反例，也沒看到正例，值得補一條測試。
6. **`add --once` 不等時，回音「過一兩秒」不一定到**：一次 `sleep 2` 之後 `K/responses/` 還是空的，`sleep 3`～`5` 才有。教程改寫「過幾秒（等 kernel 走到下一格）」。
7. **kernel 停了、daemon 也停了時，`ls` 的 health 說「停機中（aos-kernel boot …）」**：照括號去 boot 會得到 `NotRunning: daemon 沒在跑`。health 判定順序是 `stopped` 先於 `daemon`，這種兩個都停的情況提示少了「先開 daemon」。教程 01 的常見錯誤表有寫 boot 前要先開 daemon。
8. **批次 `say` 之後逐個 `listen --wait` 會白等**：行為照規範（`--wait` 只等下一則新的），但這是管很多 agent 時最自然的寫法，實測 carol、dave 各白等 120 秒。教程 05 改教平行 `say --wait`，並寫明這個陷阱。
9. **`aos-agent check` 的 bad 總結說「修好再 aos-agent start」**：agent 已經登記著時，修好工具下一格就生效，不用 start（再 start 也只印 `already started`）。教程 04 加了一句說明；要不要改訊息由使用者定。
