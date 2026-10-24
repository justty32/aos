# WAIT_USER — 等待使用者的事

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

需要**使用者親自做 / 驗證 / 拍板**才能繼續的事——例如：實機/實環境測試、外部服務登入、環境變數設定、權限操作、需要帳號的下載、**催/開/fork 另一個 agent 處理急件**（見 [inbox](workflows/inbox/README.md)：寄了信但很急、對方可能沒開）。Claude 能做結構性驗證＋打包到極限；跨不過去的那一關記這裡等使用者。

**設計裁決也算**——照 [AGENTS 鐵律 5](../AGENTS.md)「大方向是使用者的」，需要你一句話才動得了工的，
對我來說跟「沒有帳號密碼」是同一種卡住。**本檔只留一行 ＋ 連結**，脈絡在各自的原始文件裡，不在這裡重講。

**只列還沒做的**——做完即移除（不留已完成清單，歷史看 git log）。

> **膨脹就拆**：待使用者項堆多了，就開 **`wait-user/`** 資料夾按類別拆檔，本檔退回只留一張 `| 類別 | open | 清單 |` 導航表（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

## 待使用者項

- 還沒確認的：tasks、兩種 kernel 兩個方向題 → [plan § 1.2](../proto8/thinking/2026-10-21-plan.md)
- 腦的工具呼叫做完後要你看的三題（都不擋、已照推薦做）：agent 當腦的工具時題目怎麼交（範本只定 stdin 進 stdout 出；10-24 agent-eve 叫 pyfix 照這條做出一個實例：轉接寫在工具自己的 `_entry`、`tool.json` 不加 `input`，見 [thinking 10-24 agent-as-tool](../proto8/thinking/2026-10-24-agent-as-tool.md)；那份另有五個選項要你看：子 agent 失敗停下還是回給腦、記憶、子 agent 換強模型、轉接做成共用一支、等 LiteLLM 開著真跑一次）、腦叫了不存在的工具是停下等人還是回給腦、對話太長 → [thinking 10-23 tool-calls](../proto8/thinking/2026-10-23-tool-calls.md) 文末
> 2026-10-12 使用者清帳：「舊帳可以清掉」「proto6 已經是老黃曆了，不管」——A 區 71 題、B 區 proto6 帳號真 root 驗收、C 區「先不決定」各項全部結案不再追。原 `wait-user/` 分類檔已封存（見 common/archive 索引），編號不回收。
