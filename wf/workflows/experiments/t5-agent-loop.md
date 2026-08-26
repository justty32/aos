# T5 agent loop 實測
← [experiments](README.md)

2026-08-25 驗 roadmap T5 agent loop 的實測紀錄。內容已拆進 [`t5-agent-loop/`](t5-agent-loop/README.md)。

| 檔案 | 裡面有什麼 | 什麼時候會想看 |
|---|---|---|
| [record](t5-agent-loop/record.md) | 結論、七段實測現場（基線、假模型 golden slice、投遞、Ctrl-C／`.runi`、空 `inst.json`、真 agent CLI、reliability 補充）、哪幾題被實驗回答了、哪幾題反而更不確定、規格與實作對不上的地方、最後驗證 | 要查某個現場的原始指令與輸出，或這次實測對 OPEN 問題與規格缺口的結論 |
| [subcommand-specs](t5-agent-loop/subcommand-specs.md) | 這次實測導出的五支子命令需求：`aos deliver`、`aos recover`、`aos status --json`、`aos agent step`、`aos agent emit-context` | 要直接引用這五支子命令該做到什麼時 |
