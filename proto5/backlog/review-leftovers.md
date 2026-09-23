# fable 重審留下的（2026-09-22）

來源：[proto5.1/notes/review-fable.md](../../proto5.1/notes/review-fable.md)。R1～R3、R5～R9、R14～R27 在 proto5.1 第 5 段做掉；以下是使用者決定先不做的。
2026-09-23 重架構後 R10、R12、R13 已解掉、刪了（見 [backlog-cleanup](../notes/2026-09-23-rearch/backlog-cleanup.md)）。

- **R4** 原本是「aos-run 被 KILL 但子程式活著，kernel 重建 runner 會與孤兒重疊」。新架構的同一個洞：cpu 主人被 KILL、子程式還活著，daemon 重拉那顆 cpu 後可能又派到同一行程，跟孤兒重疊。新規範仍寫明在保證外（[cpu §5.3](../spec/cpu.md)、[kernel §7](../spec/kernel.md)）。真要擋再想怎麼記子程式 pid。
- **R11**（不確定，待人判）原本是「工作 cpu 與 kernel tick 的 interval 分開」：新架構已分開（cpu `poll_ms`、kernel `tick_ms`），`last_target` 也拿掉了。剩下的是 `once` 工作要等 kernel 一格派、下一格收，一次問答的延遲仍綁在 `tick_ms`（[kernel §3](../spec/kernel.md)）。
