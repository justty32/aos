# talk 唯讀審查任務書（給 astra）

你是唯讀審查者，**不要改任何檔案**，只把審查結果寫成 Markdown 輸出。用繁體中文。

## 背景

使用者 09-24 原話：「來一個 `aos-agent talk` 指令。這就只是來回 say/listen，類似 repl。沒有說要達到 claude code cli 那樣的體驗，我要的是極簡版，ctrl+c 就退出那種。啊，要加一些 slash command，比如 /status、/context 之類，看著加上。相關 flag 你也自己看著辦。」

這一輪照這段話加了 `aos-agent talk`。看 `git log --oneline main..HEAD` 與 `git diff main..HEAD -- proto5/` 就是全部改動（本任務書除外）。

已知的坑（試玩 r5 撞到的）：`listen --wait` 只等「開始聽之後」才到的回話；回話若在開始聽之前就寫進記憶，會乾等到逾時。talk 不能踩這個坑。另一個痛點：`say --wait` 失敗時把整段 status 混進 stdout。

## 要審的檔

- 規範：`proto5/spec/aos-agent/cli-talk-repl.md`（新，§1.8；`cli-talk.md` 是舊的 say／listen，名字撞了所以另取）、`cli.md`、`essentials.md`、`README.md`、`history.md`。
- 實作：`proto5/lib/aos_agent_talk.py`（新）、`proto5/lib/aos_agent_cli.py`。
- 測試：`proto5/lib/test/test_agent_talk.py`（新）。
- 參考：`proto5/lib/aos_agent_listen.py`（`wait_reply`、`_stopped`）、`aos_agent_say.py`（`deliver`）、`aos_agent_status.py`（`collect`、`agent_health`）、`aos_agent_pause.py`、`aos_agent_results.py`（工具結果字串）、`proto5/spec/aos-agent/cli-talk.md`（§1.2、§1.5）、`tick.md`、`idle.md`（intake 怎麼把輸入接進記憶）。

## 請回答

1. **回話會不會漏印或重印**：`shown`（印到哪）與 H0 的關係；回話在開始等之前就到、中途叫工具、同一輪合併了好幾則輸入（intake 一次收好幾個檔）、逾時後晚到、逾時後再送下一句、記憶被改短、記憶讀到一半壞掉、兩個 talk 同時開或旁邊有人 `say`。有沒有情況「這一句回完了」永遠判不成立（例如同一句話送兩次、TEXT 頭尾空白被去掉、`_done` 的 `text` 比對）或太早成立。
2. **Ctrl-C 時序**：在 `input()` 中、在 `deliver` 中（暫存檔、rename／link 之間）、在 `wait` 的 `collect`／`sleep` 中、在 slash 指令（`/pause`、`/continue`）中按 Ctrl-C，會不會留半截狀態、印出 traceback、退出碼不是 0、或「上一句還沒回」的提醒該印沒印／不該印卻印。
3. **slash 與模型輸入的邊界**：`/` 開頭、`//` 開頭、前面有空白的 `/`、只有 `/`、`/status  -v`、大小寫、全形斜線「／」、看起來像路徑的字（例如 `/usr/bin 是什麼`）；未知指令確實不送；參數錯不退出。
4. **tty 與非 tty**：非 tty 不印提示符與等待提示；stdout 只有回話與 slash 輸出、stderr 才有提示（拿 stdout 當對話紀錄是否乾淨）；等待提示的 `\r\033[K` 清行在回話、錯誤、逾時訊息前都有清掉嗎；readline 在非 tty 不載入；stdin 關掉／EOF 的處理。
5. **規範與實作對得上嗎**：逐條對 `cli-talk-repl.md`，找實作不照做的地方（字串、順序、退出碼、旗標驗證、`/status` 一行的欄位、`/context` 的字數算法、`--show-calls` 的行格式）。
6. **測試漏什麼**：列出值得補的測試（具體到情境）。
7. **其他 bug**。

## 輸出格式

分「必修」（會讓使用者看到錯的行為、回話漏或重、規範與實作不一致）與「建議」（可不修）。每條寫：檔:行、問題、怎麼重現或為什麼、建議改法。沒有問題的節寫「無」。
