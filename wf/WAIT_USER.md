# WAIT_USER — 等待使用者的事

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

需要**使用者親自做 / 驗證**才能繼續的事——例如：實機/實環境測試、外部服務登入、環境變數設定、權限操作、需要帳號的下載、**催/開/fork 另一個 agent 處理急件**（見 [inbox](workflows/inbox/README.md)：寄了信但很急、對方可能沒開）。Claude 能做結構性驗證＋打包到極限；跨不過去的那一關記這裡等使用者。

**只列還沒做的**——做完即移除（不留已完成清單，歷史看 git log）。

> **膨脹就拆**：待使用者項堆多了，就開 **`wait_todo/`** 資料夾按類別拆檔，本檔退回只留導航到各分類檔（照 [DEV-GUIDE「結構整理原則」](DEV-GUIDE.md)）。

## 待使用者項

- **要不要解凍 `core/inst` 核心層？**（擋 [roadmap 的 T1](../docs/roadmap.md)）
  已拍板的「每筆 instruction 自帶 non-blocking 欄位」做不到不解凍：新增 JSON 欄位一定
  要改 `format.cpp`（它對不認得的 key 直接回 `UnknownKey`，不是忽略），thread 化要改
  `exec.cpp`／`run.cpp`。這三個檔都在 [code map](workflows/common/code-map.md) 的凍結
  名單上。**繞不過去，需要使用者明確點頭**。

- **移植 S2 的決策 A：`core/tooljson` 的 exec 引擎自己寫，還是動 `core/inst`？**
  `_type: "exec"` 看起來就是 `core/inst` 在做的事，但接不起來——EXEC.md 要求
  `stderr.mode: "merge"` 是真的共用一條管子，而 `inst` 的重導向走檔案路徑，
  `core/inst/src/exec.cpp` 對 stdout 與 stderr 各開一次 `O_TRUNC`，同一個路徑
  給兩邊會互相蓋寫。選項與代價寫在
  [`reference/PORTING.md`](../reference/PORTING.md) 的「三、兩個要使用者拍板的
  決策」。**A2 會動到凍結的 `inst` 核心層，所以一定要使用者點頭**，不可以自己選。
  這題沒解掉之前 S2 不要開工。
  **2026-08-24 補**：回合制模型把這題改寫了一半——tooljson 不再需要自己的 exec 引擎，
  但 `stderr` merge 變成「`inst` 要不要加這個欄位」。使用者當天拍板 `core/tooljson`
  與 `core/llms` **先不動**（排在 agent loop 之後），所以這題**跟著延後**，不再是任何
  事情的前置條件。完整說明見 [roadmap 的 D5](../docs/roadmap.md)。
