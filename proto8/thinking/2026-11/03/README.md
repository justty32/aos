# proto8 討論紀錄：2026-11-03

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [2026-11-03 execs／loops 統稱 procs：名單合一、看寫法決定怎麼起、每項可指定 stack、四態與名詞表](procs/README.md) | daemon 的 `loops`＋`execs` 合成一份 `procs`、沒有 `kind`（看寫法決定怎麼起）、每項可指定 `stack`；名詞表 add／rm／start／stop／pause／resume → running／paused／stopped，窗 `procs_ctl.json`／`procs_state.json`；已實作（使用者「可以，派人做」）；§ 8：收工時還在跑的 loop 型留 `sleeping`、再開自動 wake，sleep／wake 不開放成指令 |
| [2026-11-03 aos-agent：通用的 agent 介面](aos-agent.md) | say／listen、aos_ws、aos-ai 以後併進 `aos-agent` 通用介面；11-04 定：先做 loop／fsm agent 再綜合 eca，找 agent＝`AOS_DAEMON_STACK` → daemon 表上的名字 → 那支 proc 的 stack，佔資料夾用選用的 `.aos/agent.json`；介面細節未規劃（11-04 已改：已規劃並實作，`AOS_DAEMON`、`.aos/agent.json` 不做，見 [11-04 aos-agent](../04/aos-agent/README.md)） |
| [2026-11-03 trace.jsonl 整個拿掉](trace.md) | trace.jsonl 整個拿掉（fsm、aos-eca-turn 不寫，listen／chat／aos-ai／nvim 的 trace 功能拿掉）；靠 trace 量的 topdown 使用者「封存 topdown」（11-04 再整個刪）；已實作 |
| [2026-11-03 loop 的 ctl.json 改成下指令](ctl-commands/README.md) | loop 的 ctl.json 改成一道指令 `{"cmd": pause／resume／stop, …}`，不用信箱、誰能寫誰就能控制，起來第一次讀的當基準線不執行；暫停記在 state.json 的 `paused`；已實作（使用者「可以，派人做」） |
| [2026-11-03 stack 不放工作區：拿掉 `.stack` 捷徑、`where --stack`、`aos-exec --stack`](stack-where.md) | 不再建 `<WS>/.stack` 捷徑、`aos-daemon-ctl where --stack 名字` 印子項的 stack、`aos-exec --stack S`（預設仍在工作區、自動建、沿用外面的）；已實作；11-04 aos-say／aos-eca 併進 aos-agent |
| [2026-11-03 eca 接 aos 工具：`cli.json` 指登記檔、cli_session 自己接 aos-mcp](eca-tools/README.md) | eca 資料夾放 aos-tools 登記檔（`cli.json` 沒指定就找預設 `tools.json`；11-04 起 stack 副本優先），cli_session 每次起 CLI 前產 `mcp.json` 接 aos-mcp；已實作 |
| [2026-11-03 aos-post 重新定位：IPC 的語法糖、改名、有序無序同箱](aos-post/README.md) | aos-post＝IPC 語法糖：信箱＝有 `tmp/`、`new/` 且可寫的資料夾，子命令改名 take／take-all／see／done／regret（`done/`→`archive/`），有序無序同箱；衝突與方向題使用者「aos-post這塊都按照建議。」、已實作 |
