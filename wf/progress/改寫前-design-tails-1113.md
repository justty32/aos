# design-tails-1113 改寫前的逐字（11-13 前開的設計尾巴），11-22 整理時大半關掉、codex 身併進 eca-rest

← [progress.json](../progress.json)｜[progress 整理-1122](../../proto8/thinking/2026-11/22/progress整理-1122/README.md)

## design-tails-1113：11-13 前開的設計尾巴

（open，since 2026-11-17）

**what**：外部 MCP：CLI 自己接的 server 起來後才壞 aos 看不到（P3）、三項 11-18 晚驗過（verify-night-1118，真 claude haiku＋假 server）：`except`→`--disallowedTools` 有效（那支整支不在清單）、CLI 自接的一起來就退＝stack `stderr.txt` 一行 warning、回合照走，中途死＝腦拿到 `Connection closed`、claude 自己重起 server、aos 看不到，經 aos 的卡住不回＝60 秒收掉行程群、腦照走下一步；P1 `--envs` 改成指 env 檔沒做（文件那半已寫在 `aos-agent ctl add --help`）；ops-agent：yes/no 時由 hook 接住寄信（使用者說之後再做）；index 三題（同一節點多處 index 聽誰的、過時、專屬工具長怎樣；`index_view` 已有）等使用者；eca 子 agent codex 身（使用者 11-13「以後再想辦法處理，不急。」）；team-model 跟 skyrim 那份同步，核不到：要家機的 `~/repo/moddings`；compact_reload 補驗，核不到：要真 Claude Code compact 一次（驗完才補 user/02 那句）（11-18 晚作廢：Codex 兩隻 `gpt-price`／`gpt-soap` 跟盤點對不對得上、ops-agent 索引檢查出廠工具，原本都要公司活樹核，那棵已清掉）
