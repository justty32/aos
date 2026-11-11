# proto8 討論紀錄：2026-11-11

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [subagent-rename](subagent-rename.md) | 已施工：工具 `agents_children` 改名 `subagent`（夾、登記名、knowledge 節點、記帳檔位置跟著），舊名不留；包名 `children`、`children.json`、`max_children`、`Child*` 代號、`agents_ctl`／`agent_def` 沒動，待使用者裁 |
| [self-system](self-system/README.md) | 已施工：agent 改自己的 system 文字——人用 `aos-agent system get／set／reset`、腦用 `self_system`（self 包，兩範本 35 支）；定義宣告 `system`、stack 那份在就整份用它；fsm 取代（下一格生效）、eca 附加（claude 下一輪、codex 下一段新對話）；codex 底下 aos-mcp 明寫帶 `AOS_*`、只對 aos 這個 server 免核准（使用者裁「修」「aos 工具免核准」），codex 改了 system 只提醒、不自動開新對話 |
