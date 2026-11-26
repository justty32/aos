# proto8 討論紀錄：2026-11-26

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 份 | 一句話 |
|---|---|
| [aospl循址與元介面-1126](aospl循址與元介面-1126.md) | 使用者退到介面之前更根本的概念：通用循址字串 `xxx/yyy/zzz`、參考 Lua 的 table 與鴨子型別設計 aoslua；存在＝存取得到、元表 `xxx/__meta`、基本操作八個、其餘全靠介面宣告；介面宣告＝能存取到 `xxx/__meta/__interfaces/<介面名>`；共同介面 `aos/utilpath`、`aos/name`、`aos/description`、`aos/rename`；exec／before／after 做法 |
| [daemon職責-1126](daemon職責-1126.md) | 做完減法後 daemon 只提供資訊與工具、判斷與使用交給 kernel；用 `/proc/<daemon PID>/cwd/xxx` 存取，daemon 住進只有資訊與工具的小世界；只開給起動參數指定的主 kernel，其他 proc 用 Landlock 擋；工具是一個可寫檔（start、kill、mount、umount、forget），cgroup 資料夾直接當開關；主 kernel 死了照參數 restart（有上限）或 exit；未決：aoslua 怎麼描、主 kernel 正式名字 |
| [kernel-1126](kernel-1126.md) | daemon 收窄後談 kernel：init 做最小的（照設定起第一批、轉交「請起一隻」、記誰起了誰），登記表／准不准／重起規則做成可不裝的其他 kernel；跟 init 說話走 ctl 介面宣告（__meta/__interfaces/ctl/ 底下寫怎麼講）；未決：ctl 宣告細節、登記表、按需起、llm kernel 搬家、就緒與事件 |
