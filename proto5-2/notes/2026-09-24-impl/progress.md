# proto5-2 實作進度（2026-09-24）

← [實作總報告](README.md)｜決定：[decisions.md](decisions.md)

接手的人：照下表看到哪；每段做完隊長在這裡改狀態、寫 commit。
測試：`cd proto5-2/lib && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s test`。

| 段 | 內容 | 狀態 |
|---|---|---|
| 1 | 複製 lib／cli、測試在 proto5-2 下全綠 | **完成**：1153 條全綠（65 秒），只改路徑沒改行為 |
| 2 | kernel 家與帳本第 2 版、`init --config`、`ls` 按池 | **完成** |
| 3 | daemon：pool.json、reconcile、boot 拉回、halt、ls／scale／kill | **完成** |
| 4 | 協定、`cpu add／rm／ls`、notify、boot 交接、halt 縮 0 | **完成** |
| 5 | aos-agent 線跟著動的幾句 | **完成** |
| 6 | 測試（搬遷＋新加＋崩潰窗口） | **完成**：1247 條全綠（連跑兩次，約 76 秒） |
| 7 | 真跑一條龍 | **完成**：十步全過，見 [run.md](run.md) |
| 8 | 文件 | **完成**：README 狀態＋十分鐘上手、lib/README、notes/README |
| 9 | astra 唯讀審查與必修 | **完成**：7 必修全修＋P9；1277 條連跑兩次全綠 |
| 10 | 總報告 | **完成**：[README.md](README.md) |
