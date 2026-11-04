# proto8 討論紀錄：2026-10-30

← [2026-10](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [2026-10-30 agent 的 queue、外部 coding agent 的生命週期、session 檔接管](agent-lifecycle/README.md) | fable 規劃（使用者「都照建議」，決定 36）：queue＝N-16 有序投遞、放 `$AOS_STACK/queue/`，aos-say＝`aos-post send --ordered`；外部 coding agent 掛 daemon（`max: 1` 或原生 `execs`）；hub pause 改 `close`、session 檔 symlink 進小格 |
| [2026-10-30 使用者看現況地圖後的想法（九點）](map-review/README.md) | 已定：round 化作 aos-round 薄殼、外部 agent 跟 aos agent 平級（eca）、通用層就是 aos-daemon（現有 aos-hub 改名 aos-eca-hub）、改名 aos-llm-kernel／aos-llm-send；開著：plan 9 式檔案串流、aos-post／aos-lock 補指令 |
| [2026-10-30 eca：外部 coding agent 跟 aos agent 平級——兩塊比較、通用介面、aos-eca-hub 怎麼切](eca/README.md) | fable 規劃（使用者「都照建議」、九步做完）：外部 coding agent＝跟 aos agent 範本同形的資料夾程式（aos-loop 包 turn），aos-eca-hub＝daemon＋畫面＋resume＋session symlink、沒有自己的 kernel；之後的改口在 10～21（改名 aos-eca、一次只管一隻、交出去就收、開場白 `--prompt FILE`） |
| [2026-10-30 aos-round：round 化作 aos-loop／fsm 上的薄殼、fsm 的 `next` 照結束碼分岔](aos-round/README.md) | fsm 的 `next` 照結束碼分岔（N-36 改口）、round 化作 aos-round 薄殼（使用者「都照建議」、已實作）；11-01 晚 aos-round 刪了，11-03 晚整條 round 線刪掉 |
