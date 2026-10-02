# 舊程式碼盤點：拆出來重用 vs 廢棄

依 code-map.md／ideas/README.md／2026-09-05 拍板 8 條盤點。只讀不改。

判定三檔：**RU**＝可直接重用｜**改**＝拆開改一改能用｜**廢**＝廢棄。

已抽到 [asset-inventory.json](asset-inventory.json)（37 列）。

欄位：
- `組件（路徑）`：舊組件的檔案路徑
- `今天做什麼`：該組件今天的功能
- `新構想對應`：對應到新構想的哪一章（或沒有直接對應）
- `判定`：RU／改／廢／不確定等判定
- `理由`：判定理由
- `測試`：是否有測試

統計：共 37 列；判定：改 21 件、RU 11 件、廢 3 件、不確定 2 件。

## 建議第一批拿出來重用的

- `core/exec` 全部五塊（start_all／wait_all／interrupt／tempfile／clock）：POSIX 執行原語，跟協定無關。
- `core/loop/src/fs.cpp` 的 `write_atomic`：題目點名的「原子改名投遞」，到哪個版面都要用。
- `core/loop/src/wake.cpp`：F-03 已經照現有做法拍板，直接搬。
- `core/tool/src/probe.cpp`、`contacts.cpp`／`contact_status.cpp`：K-03 定案的通訊錄形狀就是現有實作。
- `core/llm/src/llm.cpp`：OpenAI 相容 client，跟並行策略無關，LLM 世界照樣要用它打端點。
- `core/tick/src/due.cpp`：純函式到期判定，不涉及 LLM 同步問題。

## 一定廢的

- `core/llm/src/slot.cpp`：G-04 明講鎖檔槽機制作廢，改由 daemon 走時鐘時數並行。
- `core/agent/src/step.cpp`：F-02 裁定 LLM 是獨立世界，同回合同步等 LLM 的模式架構上不成立。
- `core/agent/src/engine.cpp`／`engine_pi.cpp`：同上，且 pi 同步做完思考+工具跟 09 章的呼叫協定衝突更大。

## 不確定、要使用者看的

- `core/tick` 的 heartbeat/routine/schedule CLI 整組：G-01 說「所有時鐘由 daemon 走並登記在一處」，不確定這是指 daemon 接手 tick 現有的兩張表機制，還是 tick 繼續當 daemon 底下的一個獨立小專案運作。這個邊界會決定 `table.cpp`／四支 CLI 是整批搬進 daemon 還是原樣保留。
  → 答：`core/tick` 那組留著當 daemon 底下的小專案，daemon 只管起停，tick 自己判到期（R-01）。
- `core/agent/src/user.cpp`（`~` 使用者世界 say/listen）：ideas 13 章的待決定總表裡沒有任何一條點名它，看不出新構想要不要保留「使用者世界」這個獨立概念，還是併進一般的呼叫協定(09章)。
  → 答：`~` 使用者世界的 say/listen 保留，使用者就是住 `~` 的一個 agent（R-02）。
