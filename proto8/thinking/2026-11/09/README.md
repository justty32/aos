# proto8 討論紀錄：2026-11-09

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [clock-and-hot-writes](clock-and-hot-writes/README.md) | 使用者兩個想法：`_tick` 改名（裁大改；名字待在 clock／turn 二選一，推薦 clock＋單位 cycle）、熱寫檔拉出 json 改 .txt＋旗標（實測閒置每秒約 25 次整份重寫，元兇是 `responded_at` 與表的 `tick` 欄，不是 runs；5 題待裁）；只盤點未改 |
