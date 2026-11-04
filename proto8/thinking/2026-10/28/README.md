# proto8 討論紀錄：2026-10-28

← [2026-10](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [2026-10-28 aos-hub 下一步：常駐 aos-kernel、pause 與 stop](hub-kernel/README.md) | aos-hub 管 claude／codex／pi 之類、裡面跑常駐 aos-kernel、分 pause 與 stop（10-30 起改做 aos-eca-hub）；未決：IPC、跟通用 kernel 的關係等 |
| [2026-10-28 aos-tools：工具註冊檔](aos-tools/README.md) | 工具註冊檔 `tools.json` 與 `aos-tools add／rm／ls／get／call`，aos agent 直接吃、外部 agent 經 aos-mcp 吃；10-28 做了（`tool.json` 改名 `_tooldef.json`） |
| [2026-10-28 aos-hub 實作：say／listen 協議、適配表、副產物](hub-adapter/README.md) | aos-hub 照 10-28 決定重寫、claude／codex／pi 一張適配表；信箱放 `<資料夾>/.stack/`（「放Stack比較好。」）；10-30 起改做 aos-eca-hub |
| [2026-10-28 agent 函數的常用操作：queue、endpoint、tools、時間點、阻塞](agent-ops/README.md) | 各種單位（queue、endpoint、tools、掛勾、一輪）都要是 aos 函數、aos-exec 能跑；使用者答的題記成決定 1～15，細節設計在 agent-round |
| [2026-10-28 agent 的一輪（round）：掛勾點、單位、endpoint 介面、引用、落地](agent-round/README.md) | 一輪的掛勾點、queue、history、endpoint 介面與落地步驟（代定可翻案；文末七條「照新做法」；格全部走註冊檔 `parts.json`，使用者「全部走註冊檔好了，捷徑就是方便使用」「註冊檔案中沒寫的，那就是走固定名字」＝決定 16）；11-03 晚整條線刪掉，概念收在 proto8/archive/agent-round-concepts/ |
| [2026-10-28 介質：納入管理、loop／daemon 的手把、投遞、鎖、proc 交流、hub](medium/README.md) | 概念收線：納入管理靠介質、aos-daemon 是最基礎的標準介質，手把與窗各拆兩個、投遞與鎖要正規化，管線／檔案串流／訊號不寫進標準、hub 定薄標準（N-63）；agent 的輸入是 queue、做完自己看信箱（決定 32）；邊緣狀況待定 |
