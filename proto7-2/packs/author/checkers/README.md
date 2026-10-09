**這是什麼**：驗候選，過三關才建一條讓人合併的分支。
**一行跑起來**：`proto7-2/packs/author/bin/aos7-gates check proto7-2/packs/author/examples/aos-tool-usage/request.json proto7-2/packs/author/examples/aos-tool-usage/valid.json --ref 3c18d378064e39b9fdcc8f4b14be2aa9a47b1fe7`
**看到什麼**：`{"ok": true, ...}`，三關都過。

## 第一次跑

在 repo 根目錄照抄；範例已加入目前版本，用加入前的基準驗新增工具。

```sh
proto7-2/packs/author/bin/aos7-gates check proto7-2/packs/author/examples/aos-tool-usage/request.json proto7-2/packs/author/examples/aos-tool-usage/valid.json --ref 3c18d378064e39b9fdcc8f4b14be2aa9a47b1fe7
```

實跑輸出：

```json
{"ok": true, "rid": "usage1", "name": "usage", "job": "usage1_9ebf9840", "candidate_sha": "9ebf98401f87e860c4f71e0c495b9b4d550ec34dfdcbdc54cd078c56cc28ee8f", "failed_gate": null, "gates": {"1": {"ok": true, "issues": []}, "2": {"ok": true, "issues": []}, "3": {"ok": true, "issues": []}}}
```

發布要用 `--repo` 說清楚分支建在哪；練習時建在臨時 clone，不碰你的 repo：

```sh
DEMO_REPO=$(mktemp -d)/repo
git clone -q --shared --no-checkout . "$DEMO_REPO"
proto7-2/packs/author/bin/aos7-gates publish proto7-2/packs/author/examples/aos-tool-usage/request.json proto7-2/packs/author/examples/aos-tool-usage/valid.json --ref 3c18d378064e39b9fdcc8f4b14be2aa9a47b1fe7 --repo "$DEMO_REPO"
```

clone 沒有輸出，publish 實跑輸出：

```json
{"ok": true, "rid": "usage1", "name": "usage", "job": "usage1_9ebf9840", "candidate_sha": "9ebf98401f87e860c4f71e0c495b9b4d550ec34dfdcbdc54cd078c56cc28ee8f", "failed_gate": null, "gates": {"1": {"ok": true, "issues": []}, "2": {"ok": true, "issues": []}, "3": {"ok": true, "issues": []}}, "branch": "apprentice/usage1_9ebf9840", "commit": "9f3a615a1a485c16905e7d5d6567564fde7ed410", "dup": false}
```

**第一次用，到這裡就完成了。** 進階、契約卡、規則 → [三關 aos7-gates](../ADVANCED.md#三關-aos7-gates)（給維護者，不用讀）
