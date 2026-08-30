# 順手的判準：在 shell 打 `aos xxx`，就要有 pi coding agent 的效果

← [ideas](README.md)

**使用者 2026-08-30 原話**：「關於測試『用起來順手與否』這件事，我希望的是，在 shell 環境下，我透過輸入
`aos xxxx`，就能達到類似 pi coding agent 的效果，使用情境也會類似。好比說我想要修改某個程式碼區塊這樣。
進階的，就是指揮和管理 agent 團隊。」

## 兩級劇本（試用隊照這個跑）

**第一級：單人 coding agent**——待在某個程式碼資料夾裡，全程只用 `aos …`：
1. `aos agent init`（選 CPU：lmstudio／pi）→ 另一視窗 `aos run --step 0`。
2. `aos say "把 foo.cpp 裡的 parse() 改成回傳 optional"` → `aos listen` 看它讀檔、改檔、回報。
3. 追問、修正、要它跑測試、要它解釋 diff。**比較對象是直接開 pi 做同一件事**：多打了幾個指令、
   等了幾回合、哪一步看不到狀態、哪裡要自己去翻 `.aos/`。
4. 停掉、隔天再來、記憶還在不在。

**第二級：指揮與管理 agent 團隊**——一隻主 agent 派生子 agent（各住一個資料夾），透過通訊錄投遞任務、
收回報、看 `state.json` 知道誰在忙；使用者只跟主 agent 說話。比較對象是現在用 Claude Code 開隊的體驗
（[team-model](../team-model.md)、[dispatch](../dispatch/README.md)）。

## 怎麼量「順手」

不打分數，記三種東西：**多餘的動作**（本來一句話就該完成、卻要打三個指令）、**看不見的狀態**
（不知道它在幹嘛、死了沒）、**錯誤不指路**（報錯但不知道下一步）。每條附「用 pi／Claude Code 做同一件事的對照」。

## 交接

- 試用隊等 [proto-U-tools-impl](../dispatch/proto/proto-U-tools-impl.md) 落地後開；發現進 `wf/workflows/dispatch/trial/findings.csv`（`wf-table/1`）。
- 第二級要先有通訊錄（裁決 12）與子 agent 派生的最小路徑；沒有就先記「做不到」當第一條發現。
