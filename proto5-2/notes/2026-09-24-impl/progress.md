# proto5-2 實作進度（2026-09-24）

← [實作總報告](README.md)｜決定：[decisions.md](decisions.md)

接手的人：照下表看到哪；每段做完隊長在這裡改狀態、寫 commit。
測試：`cd proto5-2/lib && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s test`。

| 段 | 內容 | 狀態 |
|---|---|---|
| 1 | 複製 lib／cli、測試在 proto5-2 下全綠 | **完成**：1153 條全綠（65 秒），只改路徑沒改行為 |
| 2 | kernel 家與帳本第 2 版、`init --config`、`ls` 按池 | 進行中（kernel 隊） |
| 3 | daemon：pool.json、reconcile、boot 拉回、halt、ls／scale／kill | 進行中（daemon 隊） |
| 4 | 協定、`cpu add／rm／ls`、notify、boot 交接、halt 縮 0 | 進行中（kernel 隊＋cpu 隊） |
| 5 | aos-agent 線跟著動的幾句 | 未開始 |
| 6 | 測試（搬遷＋新加＋崩潰窗口） | 未開始 |
| 7 | 真跑一條龍 | 未開始 |
| 8 | 文件 | 未開始 |
| 9 | astra 唯讀審查與必修 | 未開始 |
| 10 | 總報告 | 未開始 |
