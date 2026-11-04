# 2026-10-24 給人用的 say／listen：對跑著的 fsm agent 下指令、看回覆

← [thinking](../../README.md)｜月份表 [2026-10](../README.md)｜程式 [proto8/human](../../../extras/human/README.md)｜測試 `proto8/tests/test_human.py`

## 使用者原文（整理版，10-24）

- 前文：「然後我這邊有不少想法，都麻煩你試着去思考去實作。我隨便說，你隨便做，反正只是嘗試」
- 本題：「5.讓現有的fsm agent這套東西變成人類可用，弄一些cli程式讓我可以給他下指令，看其回覆，也就是先前幾個proto中的say/listen」
- 同日稍晚（經頂層轉達）：「我現在沒空管這些小事，都按建議做」——下面的題一律照推薦定，標「照推薦定、可翻案」。

以前說過、這次照著做的：

- proto5（09-24）talk：「來一個 `aos-agent talk` 指令。這就只是來回 say/listen，類似 repl。沒有說要達到 claude code cli 那樣的體驗，我要的是極簡版，ctrl+c 就退出那種。啊，要加一些 slash command，比如 /status、/context 之類，看著加上。相關 flag 你也自己看著辦。」
- proto5（09-24）listen：「比如 `--last 10`，就是讀最後十筆訊息。然後 `--last` 不要是預設。然後有 `--show-calls`，連同工具呼叫一起印出來（但是簡化版，就是說明呼叫了啥工具）」

沿用 proto5 的：`--last N` 不是預設、`--trace` 簡化版工具呼叫、聊天極簡＋少數 slash 指令、Ctrl-C 就走；proto5 踩過、這次照著擋的坑：回話在開始等之前就到了會乾等（「開始聽之後才算」）、沒人在跑時人會再說一次（「已投入，不要再說一次」；沒人在跑就提醒「已放進去、不要再說一次」）、L1 試用最痛的「失敗會把使用者的話吃掉」。

## 決定（照推薦定、可翻案；使用者 10-24「都按建議做」）

1. **三支命令列**：`aos-say`（放一題）、`aos-listen`（等答案／跟著看／快照）、`aos-chat`（一問一答）。名字照 C-54「對外指令名＝檔名換連字號」。
2. **對的是工作區，不是 agent 資料夾**：題目＝`$AOS_WS/new/<題名>` 純文字一題一檔、答案＝`out/<題名>`（P-11、P-15 定義資料夾不被寫），所以 say／listen 收 `--ws`（＞ `$AOS_WS` ＞ cwd，同 aos-exec，N-58）。只有 chat 另收 agent 資料夾，因為它可以替你跑。
3. **題名**：預設＝UTC 時間，ISO 8601 基本格式到毫秒（`20261024T031500.123Z.txt`，沒有冒號、帶 `.txt`）；排序＝先後，agent 照檔名排序取題（P-12）。`--name` 自己取；在 new/cur/out/done 任一處用過＝`NameBad`（免得拿到舊答案）。
4. **原子寫入**（N-05）：暫存檔寫在工作區頂層 `.say-<pid>.tmp`、再 `link` 進 `new/`（不蓋已有的檔）。暫存檔不放 `new/` 裡：agent-dan／bob 的 brain 列 `new/` 不濾 `.` 開頭的檔。
5. **對應「我剛問的那一題」**：照下面 11-01 晚，正規用法是 `aos-say 話 && aos-listen`；chat 自己記。答案已經到了就立刻印（先 say 後 listen 不漏）。
6. **「有沒有人在跑」**：看 `/proc`——環境變數 `AOS_WS` 是這個工作區、`argv[0]` 是 aos-loop／aos-fsm／aos-exec／aos-daemon 的行程。沒人跑時**提醒一次、繼續等**（可以先開 listen 再去跑 agent）；題目在 `cur/` 而 trace 最後一格非 0，就說「停在哪格、結束碼幾、錯誤一行在跑它的終端機、修好再跑會接著做」。
7. **chat 兩種**：給 agent 資料夾＝chat 每句之後自己 `aos-exec --ws WS <agent>` 跑一次（loop 跑到 new/ 空自己停，P-19），agent 的 stderr 原樣在你眼前；沒給＝只放題等答案，要別人跑。開 chat 時工作區裡已有沒答的題，一起認下來，答案到了一起印（上次 agent 停在半路，`/run` 接著做）。
8. **slash 指令**只留 `/status`、`/run`、`/trace`、`/help`、`/quit`；`//` 開頭送出 `/` 開頭的話。stdout 只有答案，其餘都在 stderr。
9. **語言 Python**；旗標解析共用 `proto8/bin/aos_flags.py`（規則同 aos-exec）。放題、等答案、讀 stack 跟 aos-ai 共用 `lib/aos/aos_ws.py`（[工具＝函式庫](tool-lib/README.md) 遷移 7）。
10. **錯誤一行** `程式名: 代號 原因`、退 1，代號照 C-54 四種：`ArgumentsBad`、`FlagUnknown`、`WsMissing`、`NameBad`、`QuestionUnknown`、`AnswerMissing`、`AgentMissing`。提醒不是錯，用括號包、不帶程式名。
11. **常駐跑法不另做程式**：要 agent 一直在，就用 aos-loop 包一層（`{"exec": {"argv": ["aos-exec", "<agent>"]}, "interval_ms": 1000}`、不寫 `max`），寫法在 [human/README](../../../extras/human/README.md)。
12. **agent 的錯誤一行不另外存**：外面跑的 agent，錯誤一行只在跑它的終端機；listen 只看得到 trace 的結束碼。要存得改慣例（stack 裡多一份 stderr），不動。
13. **忘記對話不加指令**：照 P-41「要忘記＝換 stack」，用 `AOS_STACK=… aos-chat …` 或換工作區。

不用的：`aos-agent` 一支程式掛子命令（照 C-54：一支程式一件事，`aos-xxx`）、`--target`（用 `--ws`）、kernel 登記／`wake`／`health`／暫停連敗（proto8 沒有 kernel，P-20 失敗就停下等人）。

## 連續對話（照現行範本）

- **agent-dan**：對話接在 `$AOS_STACK/history.jsonl`、只附加，同一個工作區（同一個 stack）連問三句，三句 user 都在同一段對話裡，腦看得到前面的（測試 `test_two_questions_keep_history`）。腦失敗時那題的 user 已接上、重跑不重複接。
- **agent-bob**：每題獨立，沒有記憶。

## 邊緣狀況

- agent-dan／bob 的 brain 列 `new/` 不濾 `.` 開頭的檔：別人若把暫存檔寫在 `new/` 裡，會被當成題目認領（say 已避開）。
- 同一毫秒兩個 say：`link` 撞名就等 2 毫秒重取，不蓋。
- 「有人在跑」是猜的：daemon 管的子 agent 工作區不同（`$AOS_WS/bob`）、別人的行程讀不到 environ、包一層的 loop 沒經 aos-exec 起（環境裡沒 `AOS_WS`）都會被當成「沒人跑」——只影響提醒，不影響等。
- 外面跑的 agent 失敗時，錯誤原因只在它自己的終端機；listen 只能說「停在哪格、結束碼幾」。
- chat 給了 agent、跑一次之後還有題沒答（例如別人同時丟了十題、max 用完）：提醒「還有 N 題沒答」，打 /run 再跑。
- Ctrl-C 在 chat 跑 agent 時同時送到 agent（同一個行程群組）：loop 收完那次就走（P-36），chat 等它最多 10 秒再離開；題目留在 cur/，下次會接著做。
- 兩個 chat 對同一個工作區：各自只印自己送的題，但 agent-dan 的 history 是同一段，兩邊的話會混在同一段對話裡。
- `--last N` 照 out/ 的 mtime 排，人手動碰過 out/ 的檔順序會變。
- 10-30 晚：say 之後拿舊協議的 agent 跑、信留在 queue 沒人認領，listen 改成說一句就退（`LetterUnclaimed`）——代定見 [aos-round 實作時代定的「真腦實測發現 2」](../30/aos-round/07-決定.md#實作時代定10-30隊長與工人照原則定的細節可翻案)。

## 11-01 晚使用者：`aos-say "..." && aos-listen` 才是正規用法

使用者原文（逐字，看到 amy README 與頂層回覆裡寫 `N=$(aos-say 現在狀況); aos-listen "$N"` 之後）：

> aos-listen "..."這種使用方式是誰定的，我不喜歡。aos-say "..." && aos-listen才是正規用法。

決定（11-01 晚，使用者定；實作細節頂層代定、可翻案）：

- 正規用法只有一種：`aos-say 話 && aos-listen`。`aos-listen` 不帶參數＝等**最新那封**（queue 裡最後寄出的、或剛被認領的）的回答，印出來就退 0；答案已經到了就立刻印。
- `aos-listen 信號` 這個位置參數拿掉（少一種機制）；aos-chat 內部要對應信號是函式庫的事，不露在命令列。
- 跟著看（tail -f）要明寫 `--follow`；`--last N`、`--status`、`--timeout`、`--trace` 不動。

### 實作時代定（11-02 晚，照上面的決定與原則定的細節；都可翻案）

1. **「最新那封」怎麼挑**：開始等的那一刻，取 queue `new/`、`cur/` 裡信號最大的一封（信號前面是 12 位序號，照名字排＝寄的順序），之後就盯這一封；**不管是誰寄的**——別人在你之後又寄一封，你等到的是他那封的回答。`done/` 不看：`new/`、`cur/` 都空＝答案已經到了，直接印 history 最新那則回答（先 say 後 listen 不漏，跟以前一樣）。
2. **什麼都沒有**：`new/`、`cur/` 空、history 也沒有回答＝`QuestionUnknown`（沿用舊代號），不等「之後才寄的信」——先開 listen 再 say 的用法不支援（正規用法是 say 在前）。反過來，沒寄新信就 `aos-listen`＝立刻印上一則回答。
3. **還給信號**：`aos-listen 信號`＝`ArgumentsBad`，訊息提示「不收位置參數；要等剛寄的那封就 aos-say 話 && aos-listen」。不留舊用法當別名（決定「少一種機制」）。
4. **旗標組合**：不帶 `--last`／`--follow`／`--status`＝等最新那封，`--timeout` 只在這時收（跟 `--last`／`--follow` 一起＝`ArgumentsBad`）；`--last N` 不帶 `--follow`＝印完就走（不變）；`--last N --follow`＝先印再跟著看；`--trace` 兩種都收。Ctrl-C：等的時候退 130、跟著看退 0（不變）。
5. **aos-say 照舊在 stdout 印信號一行**：決定沒說要拿掉；`aos-say 話 && aos-listen` 在終端機上會先看到那行信號、再看到回答。程式對帳（測試、aos-chat 結束時的提醒）還用得到。要安靜就再議。
6. **aos-chat 離開時的提醒**改成「之後 `aos-listen --stack S` 看（等最新那封）」；nvim 外掛 `use_say=true` 那條改成不帶信號。
7. **thinking 舊檔裡的 `aos-listen 信號`／`N=$(aos-say …); aos-listen "$N"` 不回頭改**（當時的結論）；有在用的說明與例子改成新寫法。

## 未決

- 只用假腦跑過；真模型那段等 LiteLLM 開著再跑（步驟在 WAIT_USER）。
