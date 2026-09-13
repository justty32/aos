# fix-r6：r5 試玩（遊樂場六站）抓到的程式坑（proto4-3、proto4-6、proto4-7）

兩份報告 `proto4/notes/play/2026-09-13-r5-opus.md`、`2026-09-13-r5-gptsol.md` 可以看，其他 `proto4/notes/` 不用讀。遊樂場指南的部分 Fable 已改好，**不要碰 `playground/`**。

## 規矩

- 你在 repo `/home/lorkhan/repo/simple_tools/aos`。先讀 `AGENTS.md` 開頭三軸、`wf/workflows/dev-env.md`，再讀要改的 README 與原始碼。
- baseline：`proto4-3`（`cd proto4-3 && python -m unittest discover -s test`，237）、`proto4-6`（77）、`proto4-7`（29）、`proto4-5`（64）、`proto4-4`（`cd proto4-4 && for t in aos step cpu; do janet test/$t.janet; done`，42／48／12；`janet` 在 `~/.local/bin`）。做完全部重跑，只能變多。
- 單檔 ≤ 300 行；每個行為變更有測試；文件大白話、繁體中文。**不打真 LLM**（模型已卸載）、不碰 DeepSeek／API key。
- **不 commit、不 push、不開 agent。** 最後 markdown 回報：改了哪些檔、每條怎麼做、五邊測試數字、沒做的說清楚。

## 要做的

### proto4-3（kernel）

1. **`aos-kernel rm NAME` 連 `procs/done/`、`procs/bad/` 一起清**（Opus #1，今晚最痛）：現在做完的行程留在 `done/`，同名再 `add` 說「名字已經存在」、`rm` 又說「找不到」，只能手動刪檔。`rm` 找不到活的就去 done／bad 找，找到就刪並印「清掉 done 裡的舊紀錄：NAME」；三處都沒有才退 1。`add` 撞到的只有 done／bad 裡的舊紀錄時，直接把舊的清掉再排（印一行說清了什麼），不要擋。
2. **`ls` 的 daemon 那行**（Opus #5）：daemon 正常收工會把 state.json 清掉，現在被印成「找不到 daemon 的家：AOS_DAEMON_HOME 沒設？」。分三種：環境變數沒設或家資料夾不存在 → 「找不到 daemon 的家（AOS_DAEMON_HOME 沒設？）」；家在、沒 state.json → 「daemon 沒在跑（正常收工過）」；有 pid 但不活 → 「daemon dead（pid N 不在了）」。
3. **`ls` 表格**（Opus #6、#7）：`RUNS` 不要印裸的 `None`，沒有就 `-`；PROC 欄寬跟著最長名字走（其他欄一樣，用算好的寬度 format），名字長也對得齊。

### proto4-6（逐步執行器）

4. **成功也出一聲**（Opus #12）：三支跑完一格在 stderr 印一行 `第 N 格 ok（步驟名）`，等待中那行已經有；README 一句。proto4-4 的 `aos-step` 已經會印 form 的值，不動。
5. **Python 例外的一行訊息用 traceback 的行號**（Opus #10）：現在指到 `def` 那行，改成例外真正發生的那行（traceback 最後一個落在 PROG 檔的 frame）。

### proto4-7（agent）

6. **一題一封信**（gpt-sol #2）：`idle` 現在把 inbox 所有信一次全接進 messages，連丟兩封第二封會插隊。改成一次只拿最舊的**一個檔**（檔裡是陣列就整個陣列算一題），其他留在 inbox 等這題做完（`status` 的 unread 會看得到）。
7. **`--reset` 後請求名不撞**（gpt-sol #6、Opus 第 3 站同因）：state 多一個 `epoch`（預設 0），`--reset` 不是刪 state.json，而是寫回預設值但 `epoch+1`；請求名改 `<name>-e<epoch>-q<q>-s<s>`。README 那句「同名同內容冪等」補上 epoch。
8. **`listen --once` 沒新回話要說**（兩人都提）：`--once` 印完既有的就退出會像跳針。改成：`listen --once` 只印**還沒印過的**（記在 `A/.listen-seen` 或用 outbox 檔名最大號記在 state 之外的小檔），沒新的就印 `（沒有新回話）` 退 0；`--new --once` 維持「等下一則」；不帶 `--once` 維持一直聽。README 對齊。
9. **stuck 的用詞統一**（gpt-sol #9、Opus #11）：到步數上限的 outbox 訊息改「這題走了 N 格到上限，先停（stuck）；回我一句就從頭算」，連錯五次那句改「連錯 5 次，這句先放著（stuck）；回我一句再試」。README 的表跟著改。

## 測試

proto4-3：rm 清 done／bad、add 撞 done 自動清、ls 三種 daemon 訊息、RUNS `-`、長名字對齊。proto4-6：成功那行、例外行號。proto4-7：一次一封（兩封→第一題只有第一封、unread=1）、epoch 命名與 reset、listen --once 兩種輸出、stuck 用詞。
