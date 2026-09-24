# agent 線規範第 3 輪：改了什麼

← [README](README.md)｜審查：[review-agent2-report.md](review-agent2-report.md)｜上一輪：[agent-round2-changes.md](agent-round2-changes.md)｜改後：[agent.md](../../spec/agent.md)（A）、[aos-agent.md](../../spec/aos-agent.md)（G）、[aos-llm-call.md](../../spec/aos-llm.md)（L）

2026-09-24。照第 2 輪審查的 E（定稿前必改）、D（實作者還得猜）、B-6～B-8、C-1～C-3 修改，另補上一輪留下的 `.tmp` 殘檔問題。三份仍是草稿，程式還沒跟上。
第 2 輪 changes 表裡 C-6、C-8 原本寫「通」，已改成「沒通」並指到這份。

## E：定稿前必改

1. **E-1 同名再投遞被吞（擋）**：**已落**。選擇的做法是「每次消費給一個身分」，而不是規定檔名永不重用：
   - 輸入檔和 consume 的檔，先 rename 到唯一封存名 `<原名>.<消費 id>.done`，再從封存名讀。
   - `intake`／`consuming` 記的是 `{src, dst}` 成對紀錄。恢復時看到 dst 已在，就不再碰 src。
   - 連敗暫停的訊號改成每次不同名：`continue-<批 id>.json`。
   - 位置：A 裁決 8、§4.1、§4.2、§4.4；G 裁決 7、§2、§3、§8、§9。
2. **E-2 空環境的 `clear`**：**已落**。有 clear 就一定寫，`$val` 是空物件也照寫。只有沒 clear 時，空物件才可以省略。G §5.3。
3. **E-3 info 的跨 cpu 環境**：**已落**。
   - aos-llm-call 只解驗六格：`_metainfo`、`system`、`history`、`tools`、`llm.model`、`llm.params`，其他格不碰。
   - info 的頂層和 `llm` 那格要是字面物件。
   - 六格裡的 `$env`，兩顆 cpu 都要有，而且值要相同。
   - 位置：A §2；L 裁決 7、§3。
4. **E-4 K 的退出碼相容**：**已落**。
   - `start` 會讀 K 的 info；`done_exit` 是 1 或 101 就回 `KernelIncompatible`，拒絕登記。
   - 寫明 `bad_after=0` 表示不退件，會一直重跑。
   - 位置：G §11 第 2 步與末段。
5. **E-5 記憶的路徑形狀**：**已落**。`system`、`history` 必須是單一檔案。只有 `input`、`tools` 的元素、`waits` 可以指到資料夾。A §1、§3。

## D：原本要實作者猜的地方，逐條寫死

1. 記憶目的地：history 必須是單一檔案，整份原子重寫（跟 E-5 同一處改動）。
2. 工具驗證：`type` 等於 function、`function` 是物件、`name` 非空、`description`／`parameters` 的型別、`_timeout_ms` 的型別。工具檔的錯一律回 `ToolInvalid`。A §3.3。
3. llm.json 身分錯：缺欄位、不是物件、`_type` 不對，都回 `ConfigInvalid`；有 `_version` 但不是整數 1，回 `UnsupportedVersion`。L §2。
4. 正規化順序：先拿掉空的 `tool_calls`，再把 null 的 `content` 補成空字串；附一個例子。L 裁決 5、§5。
5. `HistoryChanged` 的範圍：只查長度、尾巴、call id。前綴被人改成同樣長度的內容，不偵測也不擋，人的改動會保留。A §5；G §7。
6. `tick.json` 跟 K 不一致：`envs.AOS_K` 不等於現在的 `AOS_K`，回 `KernelMismatch`、退 1，並提示刪掉 tick.json 再 start。G §11 第 3 步。
7. start／stop 等回音逾時：request 檔名固定為 `aa-<資料夾名>-<ns>-<pid>.json`；逾時時 stderr 印出回音路徑，由人自己讀、自己 ack。G §11。
8. 日常 CLI：維持不做。G §13 和 A §6 寫明「日常 CLI 還沒完」，列出現在走得通的最小流程，以及還沒有的指令。

## B、C

- **B-6**：同 E-4。
- **B-7**：「think 在途不寫記憶」只限於當前還沒取消的批次。被 Removed 的舊問可能讀到新記憶，但它的回音會被丟掉，不會接進記憶。G §13。
- **B-8**：同 E-3。
- **C-1**：同 E-2。
- **C-2**：`done_exit` 不再寫死成 100，改由 start 檢查；補上 `bad_after=0` 的例外。G §11。
- **C-3**：同 E-5。
- **上輪留的 `.tmp` 殘檔**：定為保證外。主人只收 `.json` 檔，不會誤收；沒有人自動清，人在 kernel 和 agent 都停著時可以手動刪。G §13。

## 調度者裁決（這輪新增或改寫的）

- A 8：每次消費給一個身分（唯一封存名，先搬再讀）。
- G 7：連敗暫停的訊號檔每次不同名（`continue-<批 id>.json`）。
- L 5：正規化順序固定。
- L 7：aos-llm-call 只解驗 info 的六格。

## 要使用者拍的

跟上輪一樣三題，都還開著：`fail` 狀態、將來 `pause` 的語意、agent 屬於哪個 kernel 記在哪。這輪沒有新增。
另外提醒一件事：封存檔 `*.<id>.done` 會一直累積，agent 不清。之後要不要清、由誰清，可以跟 pause 一起定。

## E-1 時序自走（取代上輪的 C-6／C-8）

| 窗口 | 下次怎麼認 | 結果 |
|---|---|---|
| 記下 intake 之後、搬檔之前崩 | src 還在（生產者不能蓋掉還沒收的檔），照樣搬 | 通 |
| 搬完、寫記憶之前崩，生產者又投了同名 B | dst 已在，不碰 src，從 dst 讀 A | 通（B 留到下一次收） |
| 寫完記憶、寫 state 之前崩 | 用前綴重寫，檢查長度和尾巴，結果相同 | 通 |
| consume 劃掉之後、搬檔之前崩 | consuming 裡有 `{src, dst}`，補搬 | 通 |
| 搬完、清 consuming 之前崩，人又 touch 同名檔 | dst 已在，不碰新檔 | 通（新檔留著；加門的人要先確定檔不在） |
| 連敗暫停：舊的 continue 檔先在 | 訊號名每次不同，不會有舊檔 | 通 |
