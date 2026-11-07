11-07 sol 審查 G 隊：tick（aos 自己數的回合時鐘）在 C++、daemon、Python 三處的讀法與期限行為，用小實驗逐項比對。

# 07 tick 一致性實驗（G 隊）

## 這區白話總結

三份「讀時鐘」的程式行為幾乎完全一樣。C++ 的 aos-util、Python 的 `tool_io` 與 `aos_ws` 三份讀法，我拿十三種時鐘檔狀態和七種 `AOS_TICK_INTERVAL` 值逐一實跑，結果一字不差：沒設＝沒時鐘、改看牆上時鐘；檔不在或空＝第 0 格；壞內容＝`TickBad` 退 1。使用者裁的「時鐘停就不到期」也都做到了：C++ 的 aos-exec、真 daemon 把 `_tick` 暫停、Python 的 ask 都實測過。兩層 daemon 都寫 `tick: true` 時，子看到的是近的那個時鐘，「近的贏」成立。

真正的不一致在兩處邊上。第一，**寫時鐘的 `aos-tick` 不認空檔**：讀的人照使用者裁定把空檔當第 0 格，`aos-tick` 卻報錯不寫。結果 daemon 的時鐘一遇到空檔就停在 0，整棵樹的 tick 期限永遠不到期。第二，**`tick.interval_ms` 明寫 1000 時不往下傳**，子樹拿到的是上一層的間隔，跟自己時鐘真正的步調對不上。此外，`null` 在 inst 單子裡算「沒給」，在 thought／agents 裡卻算「給了」，腦送 `null` 就會被擋。

## 最該先處理的 3 條

1. 錯誤行為（實測）：`aos-tick` 遇空檔報 `ClockBad`，daemon 的 `_tick` 重起 3 次後停掉，時鐘卡在 0（[02-發現 第 1 條](07-tick一致性實驗/02-發現.md#f1)）。
2. 錯誤行為（實測）：中層寫 `tick: {interval_ms: 1000}`、上層是 300 時，中層時鐘每秒一格，子卻看到 `AOS_TICK_INTERVAL=300`（[第 2 條](07-tick一致性實驗/02-發現.md#f2)）。
3. 錯誤行為（實測）：`timeout_s: null` 加 `timeout_ticks: 2` 在 thought／agents 會報 `ArgumentsBad`，在 inst 單子卻照常跑（[第 3 條](07-tick一致性實驗/02-發現.md#f3)）。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../../../STRUCTURE.md) 按 `##` 拆開。實驗腳本與原始輸出在 scratchpad：`/tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/edec8a47-e380-4be4-9152-c1fe0c9a7d41/scratchpad/teamG/`（`out-*.txt`）。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-對照表與實驗](07-tick一致性實驗/01-對照表與實驗.md) | 行為對照表（三份實作＋寫時鐘的 aos-tick）、實驗指令與輸出摘要、哪些是實測哪些是讀碼 |
| [02-發現](07-tick一致性實驗/02-發現.md) | 逐條發現 1～3（錯誤行為：aos-tick 空檔、interval 1000 不傳、null 意思不同） |
| [03-發現-續](07-tick一致性實驗/03-發現-續.md) | 逐條發現 4～6（品質：Python 兩份、起 daemon 必印 warning、沒人用的參數與食譜說法） |
| [04-已核對沒問題的](07-tick一致性實驗/04-已核對沒問題的.md) | 查過一致、沒事的項目 |
