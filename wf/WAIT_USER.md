# WAIT_USER — 等待使用者的事

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

需要**使用者親自做 / 驗證 / 拍板**才能繼續的事——例如：實機/實環境測試、外部服務登入、環境變數設定、權限操作、需要帳號的下載、**催/開/fork 另一個 agent 處理急件**（見 [inbox](workflows/inbox/README.md)：寄了信但很急、對方可能沒開）。Claude 能做結構性驗證＋打包到極限；跨不過去的那一關記這裡等使用者。

**設計裁決也算**——照 [AGENTS 鐵律 5](../AGENTS.md)「大方向是使用者的」，需要你一句話才動得了工的，
對我來說跟「沒有帳號密碼」是同一種卡住。**本檔只留一行 ＋ 連結**，脈絡在各自的原始文件裡，不在這裡重講。

**只列還沒做的**——做完即移除（不留已完成清單，歷史看 git log）。

> **膨脹就拆**：待使用者項堆多了，就開 **`wait-user/`** 資料夾按類別拆檔，本檔退回只留一張 `| 類別 | open | 清單 |` 導航表（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

## 待使用者項

- 還沒確認的：tasks、腦的 tool_calls、兩種 kernel 三個方向題 → [plan § 1.2](../proto8/thinking/2026-10-21-plan.md)；10-21 晚 aos-tick 的 8 條代定 → [session log 10-21 aos-tick 那節](session_logs/2026-10/2026-10-21.md#使用者不在時代定aos-tick計畫第-4-段10-21-晚)（10-21 下午 loop／daemon／fsm 那 11 條使用者已確認）；還有「站在 agent 資料夾裡跑會寫進定義資料夾，要不要擋」與「impls 要不要補 C++ 版 aos-tick」兩題 → [session log 10-21](session_logs/2026-10/2026-10-21.md)

> 2026-10-12 使用者清帳：「舊帳可以清掉」「proto6 已經是老黃曆了，不管」——A 區 71 題、B 區 proto6 帳號真 root 驗收、C 區「先不決定」各項全部結案不再追。原 `wait-user/` 分類檔已封存（見 common/archive 索引），編號不回收。
