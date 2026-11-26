# proto8 討論紀錄：2026-11-26

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 份 | 一句話 |
|---|---|
| [aospl循址與元介面-1126](aospl循址與元介面-1126.md) | 使用者退到介面之前更根本的概念：通用循址字串 `xxx/yyy/zzz`、參考 Lua 的 table 與鴨子型別設計 aoslua；存在＝存取得到、元表 `xxx/__meta`、基本操作八個、其餘全靠介面宣告；介面宣告＝能存取到 `xxx/__meta/__interfaces/<介面名>`；共同介面 `aos/utilpath`、`aos/name`、`aos/description`、`aos/rename`；exec／before／after 做法 |
| [daemon職責-1126](daemon職責-1126.md) | 做完減法後 daemon 只提供資訊與工具、判斷與使用交給 kernel；用 `/proc/<daemon PID>/cwd/xxx` 存取，daemon 自己住進只有資訊與工具的小世界；只開給一個地位像 Linux kernel 的 kernel，其他 proc 用 Landlock 擋（訊號之後要求較新 Linux）；未決：工具長什麼樣、aoslua 怎麼描、那個 kernel 怎麼產生 |
