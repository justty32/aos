**這是什麼**：讓 AI 學徒寫新工具：學徒交的候選先過三關（檢查、跑測試、審查），過了才變成一條等人合併的分支。
**一行跑起來**：`proto7-2/packs/author/bin/aos7-gates check proto7-2/packs/author/examples/aos-tool-usage/request.json proto7-2/packs/author/examples/aos-tool-usage/valid.json --ref 3c18d378064e39b9fdcc8f4b14be2aa9a47b1fe7`
**看到什麼**：`{"ok": true, ...}`，三關的 `ok` 都是 true。

## 第一次跑

在 repo 根目錄照抄。範例工具已加入目前版本，所以用加入前的基準來練習。

```sh
proto7-2/packs/author/bin/aos7-gates check proto7-2/packs/author/examples/aos-tool-usage/request.json proto7-2/packs/author/examples/aos-tool-usage/valid.json --ref 3c18d378064e39b9fdcc8f4b14be2aa9a47b1fe7
```

實跑輸出：

```json
{"ok": true, "rid": "usage1", "name": "usage", "job": "usage1_9ebf9840", "candidate_sha": "9ebf98401f87e860c4f71e0c495b9b4d550ec34dfdcbdc54cd078c56cc28ee8f", "failed_gate": null, "gates": {"1": {"ok": true, "issues": []}, "2": {"ok": true, "issues": []}, "3": {"ok": true, "issues": []}}}
```

想讓真的 AI 來寫：`aos7-author propose … --llm 模型名`（例如 `gpt-6-luna`，要先有 aos7-up 起好的 node） 會花錢，一次最多先扣 100 萬 token 的額度（用 `--reserve` 改小）。

想再試「過了就建一條分支」：照 [checkers/README.md](checkers/README.md) 的發布練習（建在臨時 clone，不碰你的 repo）。

**第一次用，到這裡就完成了。** 進階、契約卡、規則 → [ADVANCED.md](ADVANCED.md)（給維護者，不用讀）
