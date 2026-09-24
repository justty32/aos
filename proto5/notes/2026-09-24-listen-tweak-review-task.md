# 任務書：aos-agent listen 微調 唯讀審查（2026-09-24）

你是唯讀審查者。**不要改任何檔**，只把發現寫成報告（繁體中文）。

## 背景

使用者原話：「aos-agent listen 還可以微調一下。比如 `--last 10`，就是讀最後十筆訊息。然後 `--last` 不要是預設。然後有 `--show-calls`，連同工具呼叫一起印出來（但是簡化版，就是說明呼叫了啥工具）；`--show-calls-full`，則是印出更細節的內容。」

這次改了（倒數第二個 commit `de39dbc`，`git show de39dbc --stat` 看範圍；最後一個 commit 只是本任務書）：

- 規範：`proto5/spec/aos-agent/cli-listen.md`（新，§1.5 從 `cli-talk.md` 搬來並改寫）、`cli.md`、`essentials.md`、`README.md`、`history.md`
- 程式：`proto5/lib/aos_agent_cli.py`（listen 的參數解析）、`proto5/lib/aos_agent_listen.py`、`proto5/lib/aos_agent_listen_render.py`（新，印法）
- 測試：`proto5/lib/test/test_agent_listen_tweak.py`（新，20 條）；舊測試裡裸 `listen` 補了 `--last`
- 記憶格式參考：`proto5/spec/agent/info.md` §3.2（記憶與 message）、`proto5/spec/agent/state.md` §4.1（輸入封存 `done/` 檔名）、`proto5/lib/aos_agent_inputs.py`（封存怎麼取名）、`proto5/lib/aos_agent_batch.py`（tool 訊息怎麼寫回）

## 要看的

1. **程式與規範對不對得上**：`cli-listen.md` 每一句規定，程式有沒有照做；`aos-agent listen -h` 與規範是否一致。
2. **邊緣狀況**：記憶裡奇怪的東西（非物件元素、`tool_calls` 形狀怪、`arguments` 非字串、`content` 非字串、tool 訊息對不到 id、同一輪兩個 user 連著、記憶開頭是 assistant）會不會讓 `--last N`／`--show-calls*` 當掉或印錯；`--last` 的 N 很大、`--json` 搭 `--show-calls`、`--follow` 時記憶被改短。
3. **輪次與時間**：`rounds()`／`round_times()` 的對法（每輪第一句 user 對封存裡同內容的收件、往後找不回頭）在什麼情況會對錯輪、對錯時間；`input` 是檔或資料夾、多個路徑、封存被清掉、`state.json` 壞掉時的行為。讀 `done/` 會不會太慢或讀到不該讀的檔。
4. **相容**：`--last`／`--last 1` 不帶 `--show-calls*` 時輸出跟改之前一模一樣嗎（stdout、stderr 警告與時間）？`say --wait` 有沒有被影響？
5. **截斷**：`--show-calls` 的 40／120／60 字與 `--show-calls-full` 的 4000 字截斷是否正確、註明是否清楚，有沒有把多位元組字截壞的問題。
6. **測試**：新測試有沒有漏掉規範裡的重要行為；有沒有會不穩（flaky）的地方（`--follow` 真程序那兩條）。

## 報告格式

- 開頭一段總評。
- **必修**（程式錯、規範與程式不符、會當掉）：每條寫「在哪（檔:行）、怎麼重現、建議怎麼改」。
- **建議**（可改可不改）：同上格式，簡短。
- **不用改**（你看過、判斷沒問題的重點）：一句一條。

測試指令（可以跑，唯讀沙箱跑不了就跳過）：`cd proto5/lib && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s test -p 'test_agent_*.py'`
