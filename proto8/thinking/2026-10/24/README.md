# proto8 討論紀錄：2026-10-24

← [2026-10](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [2026-10-24 fsm 格的 exec 能不能相對於這格](exec-relative/README.md) | 拼不出「相對於這格」；loop／fsm／daemon 的 `exec` 可直接放內嵌單子、行程內跑，demo 全改內嵌 |
| [2026-10-24 agent 當工具給 agent 叫](agent-as-tool.md) | agent-eve 經工具 pyfix 叫子 agent（代定可翻案）；未決：子 agent 要不要接著聊、要不要用更強的模型 |
| [2026-10-24 給人用的 say／listen](say-listen/README.md) | `aos-say`／`aos-listen`／`aos-chat` 對工作區說話、連問接同一段 history，`aos-say "..." && aos-listen` 是正規用法；未決：只用假腦跑過 |
| [2026-10-24 仿 pi coding agent 的基本工具組](pi-tools/README.md) | 照 pi 只做 read／bash／edit／write 四個工具，另做 file-tools（輸出 JSON、刪除＝搬進 .trash）；現收進 lib/base |
| [2026-10-24 claude／codex CLI 當工具、人可以接進去](cli-tools/README.md) | claude、codex 當工具共用一段對話、人可 `attach` 接進去；demo agent-fay 11-03 晚刪了（工具形留給 eca）；未決：改走 CLI 自家的背景 session |
| [2026-10-24 `_metainfo`：函數的特性](metainfo/README.md) | `_metainfo` 三處同名、通用 key 全選填、`time_ms` 是宣告、`timeout_ms` 才強制（照建議、可翻案）；條文待落 |
| [2026-10-24 給 AI 用的 aos 工具集](ai-tools/README.md) | `aos-ai` 命令列、Claude Code skill、spawn／ask_agent 等工具；未決：MCP server 等選項 |
| [2026-10-24 記憶庫：在記憶庫裡存放各類東西](memory.md) | agent-meg 的記憶庫＝`$AOS_HEAP`、六類各一份索引＋一筆一 md、一個工具 `memory`（照建議、可翻案） |
| [2026-10-24 agent 之間寄信](agent-talk/README.md) | agent 之間寄信、team 用 aos-daemon 跑、`max_hops`／`max_sends` 擋迴圈；未決：自動寄回還是模型自己寄、信箱跟 LLM kernel 統一等 |
| [2026-10-24 函數成長：太大或特性到了就長成資料夾](fn-grow/README.md) | 函數六級、第 2 級起呼叫方只寫名字、長大不改呼叫方；原型 aos-grow；條文待落 |
| [2026-10-24 小念頭：先規劃 steps、每步 fork、只帶結論](thoughts/README.md) | agent-gus 先規劃 steps、每步 fork、只帶結論接回 history |
| [2026-10-24 Janet 編成 aos](janet-compile.md) | `aos-janet` 把 Janet 原始檔編成資料夾＋JSON＋短腳本（照建議、可翻案）；未決：反編譯、組合子改用 fsm 等 |
| [2026-10-24 改 JSON 的工具集（aos-json）](aos-json.md) | aos-json 改 JSON 的工具集與給腦的 `tools/json`、`tools/json_edit`（代定可翻案） |
| [2026-10-24 Lua 寫 aos、接進 nvim](lua-nvim/README.md) | langs/lua 與 nvim 外掛（nvim 11-03 封存）；未決：Fennel、aos-lua 要不要進 aos-exec 的入口 |
| [2026-10-24 按意圖組 context（agent-kai）](intent-context/README.md) | agent-kai 問腦時另組工作 context、不做摘要；未決：其他組法的選項 |
| [2026-10-24 自我改進流程](self-improve/README.md) | run → judge → improve 三格、改進者看不到判準、每版拍在 `versions/`（demo 11-03 封存）；未決：只用假腦跑過 |
| [2026-10-24 LLM kernel 第一版](llm-kernel/README.md) | aos-gate＋aos-kernel-llm 第一版（排隊、`slots`、額度認次數與 token）；未決：`llm_tokens` 要擋時拿 `val` 還是 `max` |
| [2026-10-24 工具＝函式庫](tool-lib/README.md) | 工具＝函式庫：三層 `lib/base` → `lib/aos` → `lib/agent`、一個工具＝`_entry`＋`tool.json`＋`_metainfo`、引用＝一條相對捷徑 |
| [2026-10-24 土法 compact（agent-hal）](compact/README.md) | agent-hal 的土法 compact（超過門檻才壓、新 history＝摘要＋最近 2 題）；未決：跟 P-41「只附加」的衝突（現用輪替） |
| [2026-10-24 Linux 權限與沙箱（aos-sandbox）](sandbox/README.md) | `aos-sandbox 設定檔 prog...` 接在 argv 最前面、存取控制純靠 Linux（S17）；未決：kernel 照信跑單子會跳出沙箱（S18），三條路待選 |
