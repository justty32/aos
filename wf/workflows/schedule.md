# schedule — 一次性行程（臨時、指定時刻）

← [WORKFLOWS](../WORKFLOWS.md)｜[INDEX](../INDEX.md)

記「指定一個時刻、做一次就沒了」的請求，並由 [tick](tick.md) 心跳在到點時投遞、
做完自動刪列。live 清單的真源是 `.aos/heartbeat/schedule.json`，使用 `wf-table/1` 資料檔契約。

**何時用**：① **登記**——你說「幫我登記行程：17:00 重啟 X」；
② **執行**——agent 收到 `aos tick` 投來的 `ask`。
**何時不用**：不常變動、固定循環的常規事務 → [routines](routines.md)。重活不在心跳回合裡跑。

## Done when

- **登記**：`aos schedule add` 成功，且 `aos schedule ls` 看得到含日期的絕對時刻。
- **執行**：`aos tick` 已投遞到點項、從清單刪列並寫入 log；收到 `ask` 的 agent 已完成判斷與可做的部分。

## 流程

### A. 登記（使用者請求時）

1. 聽清「**時刻 + 誰處理 + 內容**」。
2. agent 先把「五點」「今晚 8 點」「明天」依當地現在時間換算成
   `YYYY-MM-DD HH:MM`；`aos schedule add` **不解析相對時間**。
3. 需要 agent 判斷的內容用 `--ask` 登記：

   ```sh
   aos schedule add --at "2026-09-01 17:00" --ask "檢查部署狀態，判斷是否提醒使用者" --note "下班前確認"
   ```

4. 能直接執行的內容放在 `--` 後：

   ```sh
   aos schedule add --at "2026-09-01 17:00" -- touch /tmp/deploy-check
   ```

5. `[folder]` 可省略；省略時從 cwd 往上找最近含 `.aos/` 的目錄。回一句確認登記內容與絕對時刻，**不當場做**。

### B. 執行（tick 心跳到點時）

1. `aos tick` 掃 `.aos/heartbeat/schedule.json`，機械判定哪些項目的時刻已到；agent 不判時間、不掃表。
2. 到點的 argv 由 tick 投進 inbox；到點的 `ask` 由 tick 透過 `aos say` 交給資料夾裡的 agent。
3. agent 只在收到 `ask` 時判斷並做。**使用者親自排的＝已有授權來源（鐵律 2）**，照做；但做的當下情況有變、或會有登記時預期外的不可逆影響 → 先問再動。重活記一行 open、另開 session。
4. tick 投遞後自動刪列並寫一行 log；agent 不手動維護清單。
5. **錯過很久才醒到的**：若 `at` 早於現在超過 6 小時（可設定），tick 不自動補做，改用 `ask` 問 agent「這項錯過了，補做還是跳過」，並刪列。補做或跳過，**兩種都要告知使用者**。
6. 沒到點的留在清單。心跳本身不推外部通知；後續由投遞的指令或收到 `ask` 的 agent 處理。

## 一次性時刻表（live）

live 資料只存在 `.aos/heartbeat/schedule.json`；本檔不留表的副本。給人查看跑
`aos schedule ls`，刪除跑 `aos schedule rm <id>`。

## 交接

- 到點項需要使用者親自做 / 決定 → [WAIT_USER](../WAIT_USER.md) 一行。
- 同一件事開始每次都要做 → 改登記到 [routines](routines.md)，這裡用 `aos schedule rm <id>` 刪列。
