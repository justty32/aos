# WAIT_USER — 等待使用者的事

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

需要**使用者親自做 / 驗證**才能繼續的事——例如：實機/實環境測試、外部服務登入、環境變數設定、權限操作、需要帳號的下載、**催/開/fork 另一個 agent 處理急件**（見 [inbox](workflows/inbox/README.md)：寄了信但很急、對方可能沒開）。Claude 能做結構性驗證＋打包到極限；跨不過去的那一關記這裡等使用者。

**只列還沒做的**——做完即移除（不留已完成清單，歷史看 git log）。

> **膨脹就拆**：待使用者項堆多了，就開 **`wait_todo/`** 資料夾按類別拆檔，本檔退回只留導航到各分類檔（照 [DEV-GUIDE「結構整理原則」](DEV-GUIDE.md)）。

## 待使用者項

- （目前無）

> 2026-08-24：原本卡著的「移植 S2 的決策 A（`core/tooljson` 的 exec 引擎自己寫還是動
> `core/inst`）」已經整條解掉——使用者批准解凍 `core/inst`，並拍板 `stderr` 併流用
> `{"$opt": "merge"}` 由 `inst` 自己支援（見
> [`docs/inst-directives.md`](../docs/inst-directives.md)）；`core/tooljson` 本身則
> 先不動、排在 agent loop 之後。設計上還沒答完的細節不放這裡——它們不卡使用者，記在
> [`docs/roadmap.md`](../docs/roadmap.md) 與各 idea 文件的開放問題。
