# 備忘甲：合一＋脫離檔案
← [README](README.md)

立場：daemon＋kernel 合成一支長駐程式 `aosd`，帳放 sqlite，cpu 不再是行程。（故意站這邊，壞處照實寫。）

## 草圖

- **執行檔**：`aosd`（長駐）＋`aos`（指令，連 socket）。`aosd` 的爸爸：systemd --user，或一支只會重拉的小 `aos-boot`。
- **cpu 變「池的名額」**：池 P 有 N 個名額＝最多同時跑 N 件。派工＝`aosd` 直接 fork 一個 `aos-exec`、等它結束。cpu 資料夾、`aos-cpu`、kernel cpu、tick 鏈全不要。
- **帳放 sqlite**（`aos.db`）。為什麼：一次交易改好幾件事；`aosd` 活著或死了別人都能讀（`sqlite3` 直接查）；Python 內建。自寫 journal 要自己做壓縮與復原；只放記憶體則一崩就沒帳。
- **講話**：Unix socket，信封照舊 JSON-RPC 2.0。`add／rm／ls／status <名>`，加一個 `add --once --wait`（取名、放單、等回音、ack 五步變一個呼叫）。
- **停機**：`aos halt`＝不收新單，等在跑的跑完（逾時 TERM→KILL），寫帳、退出。
- **崩潰恢復**：跑中的 `aos-exec` 跟 `aosd` 同一個行程組，`aosd` 死就一起收；重開時帳上「在跑」的一律記 `Interrupted`，照現有規則重跑或回報（agent 已認得，r5 殺 llm cpu 就走這條）。

## 哪些痛消失

| 現在 | 合一後 |
|---|---|
| 崩潰窗口：先記後放、四張出貨箱、補放、stop 箱分不出「沒送到／已處理」、daemon 回音沒人 ack 的殘檔 | 「記帳」和「交出去」是同一筆交易；沒有信箱就沒有殘檔與重放 |
| tick 鏈、kernel cpu、鏈斷要人 boot、EEXIST 推理 | 程式內計時器＋事件迴圈，沒有鏈可斷 |
| 帳本每格整份讀、寫最多四次 | 只改有變的那幾列 |
| 每顆 cpu 每 0.2 秒掃資料夾；一顆＝一支 Python（1 萬顆約 100～200 GB） | 閒時零消耗；1 萬名額＝1 萬列資料 |
| aos-agent 每格偷看整份 `K/state.json`（scale.md 說的最大 O(N²)） | 問 `status <名>`，查一列 |
| proto5-2 為規模加的通知檔、巡檢、交接、daemon 對帳 | 大半不用寫 |

## 新的痛

1. **單點**：`aosd` 一出 bug，排程和收屍一起停，在跑的全變 `Interrupted`。現在 kernel 崩了 daemon 還在；但 daemon 一重啟本來就要重 boot kernel（daemon §5），所以真正多出來的只是「排程的 bug 會拖垮收屍」。
2. **看不見**：`ls requests/`、`cat state.json` 沒了，改用 `aos ls`、`sqlite3 aos.db`，另留一份人讀的事件 log。靠檔案卡步驟的崩潰測試（HUB／GATED 閘門）整套要重寫。
3. **agent 偷看要改**：`already_posted`、清工作檔、`status`、`continue --all` 都直接讀 `K/state.json`，要改走 RPC；aos-agent.md §5、§10、§11 要動。
4. **「pipe 只管生死」**：`aosd` 跟 `aos-exec` 之間只有 fork／wait，字面守得住；但工作改走 socket 不走資料夾，精神上已經換了。
5. **跟已拍板的前提衝突**（要使用者拍）：cpu 範式（一個家一個主人、四樣檔）對 kernel／daemon／cpu 不再成立；「kernel 是一格一格的 exec」「kernel cpu 死了靠 restart」沒了；「daemon 最單純、只管生死」沒了；「多機才上 socket」提前；link 原子投遞改成交易。**仍守住**：JSON-RPC 2.0、工作一律是 `aos-exec` 且 params＝argv、cpu 的環境＝工作的環境（變成池的環境）。

## 手感

- `aos-agent say／listen／talk`：**不變**。agent 家（info、state、記憶、input）照舊是檔案，我不主張動。`say --wait` 少等一格 tick，可能更快。
- `aos-kernel ls` → `aos ls`（舊名可留別名），內容一樣、更快；`aosd` 掛了也能直接讀 db 印「aosd 沒在跑」。
- 每天重開機：`aos-daemon boot` → `aos-kernel boot` 兩步變一步 `aos boot`，交給 systemd 連這步都省。r5 撞到的「daemon 死了 health 還叫你 boot」「halt 指錯家說 not running」這類順序陷阱整類消失。

## 遷移代價

- **不改**：`aos-exec`、inst、指示詞、`aos-llm call`、agent 家規範；程式約 1450 行。
- **小改**：aos-agent（約 1900 行）碰 kernel 的那層（ledger／submit／ack／sweep，估 200～300 行）改走 RPC。
- **重寫**：daemon、kernel 九檔、exec_cpu、home／client，約 2500 行，**lib 的四成**；kernel／daemon／cpu 規範與崩潰測試幾乎全換，1177 條測試估三到四成要重寫。
- **順 proto5-2 做**：可以且划算。proto5-2 還沒實作，其中 kernel-ledger、cpu-notify、handoff、daemon-reconcile 多半是在繞檔案的限制，合一後不用寫；它的指令長相（`cpu add --count`、`ls --pool`）照搬，底下只剩「改一個數字」。
- **老實說**：使用者講過「規模先不動」（WAIT_USER C 段）；這條路等於換個方向回答那三題，要不要現在開由他定。
