# 該變成 `.aos` 的

← [本檔索引](README.md)｜[本場索引](../README.md)｜[workshop](../../../README.md)

機械化那一半：共同長出的 `wf start／wait／resume／done／status／accept` 與 tick、兩個尚未合併的磁碟版面、一個候選的動作順序，以及安裝與升級的三方 diff。

---

## 該變成 `.aos` 的

邊界比具體路徑更穩定：**aos 不判斷這個需求該走哪條 workflow；它在 workflow 已選定之後，原子地保存
活狀態、移交 owner、到期時投遞下一步。**

### 共同長出的動作

| 動作（候選） | 做什麼 | 原本手工做什麼 |
|---|---|---|
| `aos wf start FLOW` | 建立一筆 open task，記 workflow、step／resume、owner 與目前 phase；需要時投遞第一步 | 在 SESSION-LOG 加一行、另記入口與下一步，兩邊容易漏一邊 |
| `aos wf wait ID --question FILE` | 把 owner 改成人，保存問題／resume 資訊，從 ready 移到 wait-user | 手動把 agent 進度搬到 WAIT_USER，再確保原處刪掉 |
| `aos wf resume ID` | 保存人的答覆，把 task 移回 ready，原子投遞續步 | 手改兩份清單、找回中斷前脈絡，再記得喚醒 agent |
| `aos wf done ID`／`resolve ID` | 關閉 open item；不再讓完成史留在 open view | 手動刪 open、決定是否另歸檔，容易留下已完成項 |
| `aos wf status --format md` | 從唯一活狀態渲染 SESSION-LOG／WAIT_USER 兩種 view | 人同時維護資料與展示，容易雙寫漂移 |
| `aos wf accept MAIL` | 明示把一封可忽略的信升成 task／ready，必要時再 Deliver instruction；信箱與 instruction queue 分開 | 收信者憑記憶決定它算知會、待辦還是立即執行 |
| `tick`／schedule wake | 讀 ready／`next_at`，成功 Deliver 到 `inst.tempd` 後才更新 cursor／下次時間 | 人／cron 要掃文件、判到期、投遞，並避免投遞失敗卻先前進狀態 |

這些命令共同依賴 temp＋rename，但不等於每個 workflow 都要變成 lane：短流程只是跨回合 work item；
只有獨立等待、喚醒與收件才升 lane。**不把每條 markdown 流程編譯成一顆常駐行程。**

### 磁碟版面有兩個尚未合併的版本

| 版本 | 版面 | 得到什麼 | 代價／疑問 |
|---|---|---|---|
| **`.aos` 是活狀態真源** | `.aos/wf/tasks/<id>/state.json`，或 `.aos/wf/{ready,wait-user,schedule}/<id>.json`；位置／phase 表示狀態 | 原子 move 容易；status 可產生 markdown view；文件不再同時兼任資料庫 | 若 `.aos` 通常不進 Git，跨機／協作時 open 狀態不會跟著走；JSON 是否允許人直接改也要定 |
| **`wf/open` 是活狀態真源，`.aos` 只執行 next** | `wf/open/{agent,user,peer}/<id>.md`，front matter 記 workflow、since、resume；`.aos` 只放本次投遞／`.runi` | open item 可讀、可 Git diff、可隨 repo 跨機；仍能按 owner 產生 view | move markdown 與 Deliver next 要如何形成一個可恢復動作，還沒具體化 |

選哪個取決於：open 狀態是否要隨 Git 跨機。這個答案決定哪個版面在對的層，不能靠偏好選。

### 一個候選的動作順序

```text
模型讀 WORKFLOWS.md，選到 workflow
        │
        ▼
aos wf start FLOW ───────────────► ready
                                      │
                    tick／立即 Deliver 到 inst.tempd
                                      │
                     ┌────────────────┴───────────────┐
                     ▼                                ▼
             aos wf wait ID                    aos wf done ID
                     │
                  wait-user
                     │ 人回答
                     ▼
             aos wf resume ID ─────────────────► ready

inbox/MAIL ── aos wf accept MAIL ──────────────► ready
```

這張圖只描述狀態轉換，不決定真源是 `.aos/*.json` 還是 `wf/open/*.md`。`tick` 必須先確認 Deliver 成功，
再更新 task／cursor；否則下一次會以為已喚醒，實際 queue 裡卻沒有 instruction。

### 安裝與升級也可以機械化，但不應覆蓋客製

source version／base hash＋三方 diff。命令名稱候選：`aos wf install dev`、`aos init --with workflows:dev`、
`aos module add workflows --flavor dev --layout wf`。安裝非侵入式文件骨架，記下來源版本／base hash；
升級比較「舊基底／新基底／本地修改」，只自動替換未修改檔，客製檔只顯示差異。**不拿新版 template 直接
覆蓋活實例。**另可做只讀的 `doctor`，掃 placeholder、壞連結、孤兒路由。
