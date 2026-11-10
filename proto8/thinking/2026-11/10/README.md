# proto8 討論紀錄：2026-11-10

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [two-machines](two-machines/README.md) | 規劃＋施工（午後方向大改）：git 或 cp 過去、`aos-exec --stack <stack> <定義>` 一行起根就接著跑，`aos-image` 作廢；路徑相對／絕對／`$env` 都收；/mnt/c 可放；kernel 不在不停；未決：專案外的 stack／定義換相對位置要 rm 再 add、真機驗證（14） |
| [aos-tools-cli](aos-tools-cli/README.md) | 規劃（fable）＋施工（opus，步 1～5 都做了，[08](aos-tools-cli/08-施工結果.md)）：甲級小修、快取搬 stack、`env_file` 只記位置、覆蓋層改 `$override`（照順序疊、後面蓋前面、null 那格不算工具）、`--replace`；lv6 受影響清單在 08 |
| [cli-sweep](cli-sweep/README.md) | 規劃報告（fable，未施工）：其餘指令照 C-85 掃一遍——每支一段白話、裝不下的、跨指令不一致與改法；使用者已答 Q1～Q6（Q1 待規劃員重擬），Q7、Q8 未答 |
| [prefix-fixes](prefix-fixes/README.md) | 使用者行程有變、要提前用現行 aos：大修問題清單 207 列分桶（直接修 61、A＋B 待裁 2、擱著 30、不用修 114），直接修切五條施工線；不動環境變數、json 格式、資料夾佈局、lib 介面 |
