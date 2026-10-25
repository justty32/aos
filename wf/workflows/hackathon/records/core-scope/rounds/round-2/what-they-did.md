# 第 2 輪紀錄 — 各人這輪改了什麼

← [本輪索引](README.md)｜[書記每輪紀錄](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：← R1](../round-1/what-they-did.md)｜[R3 →](../round-3/what-they-did.md)

## 1. 各人這輪改了什麼

- **Carmack persona**：私有 `publish.py`＋薄 `deliver.sh`＋記錄 unknown 的 `effect.sh`＋把每種事故收成一條具名 action 的 `recover.sh`。
- **Armstrong persona**：Publish 加 stable key、immutable intent／payload／receipt、file／directory fsync、`renameat2(RENAME_NOREPLACE)`；Effect 改成 `pending → done | unknown`，恢復只接受 `adopt | retry | abandon`；測同 target 雙 producer。
- **Cantrill persona**：修 SIGINT harness、統一 crash matrix 欄位；Publish v2 改用 `renameat2`；Deliver v2 自己產生合法 `<key>.json`、先驗 key／JSON／schema／world；雙 producer 各 1,000 份。
- **Thompson persona**：撤回第 1 輪「三行 shell 已反證 Deliver」；no-aos 鏈承受同樣三刀、只准重跑同一命令；雙 producer 各 1,000 件；hard link 窄 no-replace 原型。
