# proto8 討論紀錄：2026-11-11

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [clock-hook](clock-hook/README.md) | 已施工：aos-loop 加 `on_start`／`on_stop`，hook 加 `after_start`／`after_stop`／`on_clock`（hook 格裡寫每 N 格或每 N 毫秒，格開頭判、到了才跑，handler 不進 history）；範本預設 `timer` 每 5 分鐘什麼都不做。先定的「時鐘登記＋專用信箱＋mail_arrived」被使用者改向取代、記錄不做；時鐘寄信那組原樣留著。第二輪使用者裁：事件名 `on_clock`（先代定 `clock_due`）、起來就先觸發一次、範本預設掛著、純每拍事件先不做 |
| [subagent-rename](subagent-rename.md) | 已施工：工具 `agents_children` 改名 `subagent`（夾、登記名、knowledge 節點、記帳檔位置跟著），舊名不留；包名 `children`、`children.json`、`max_children`、`Child*` 代號、`agents_ctl`／`agent_def` 沒動，待使用者裁（稍後使用者裁「一起改吧」：周邊全改成 subagent 系，`agents_ctl`／`agent_def` 不動，同檔下一節） |
| [playground](playground/README.md) | 公司試驗場 `~/code/playground` 照今天的 main 刷新（備份 `.bak-1111-1024`）：fsm_ann 假腦、eca_bob claude haiku、新加 eca_cody codex gpt-6-luna（沒畫面），三隻各驗一輪、停著乾淨；怎麼玩一頁、公司版刷新腳本與驗收在 [01](playground/01-公司刷新與驗收.md) |
| [self-system](self-system/README.md) | 已施工：agent 改自己的 system 文字——人用 `aos-agent system get／set／reset`、腦用 `self_system`（self 包，兩範本 35 支）；定義宣告 `system`、stack 那份在就整份用它；fsm 取代（下一格生效）、eca 附加（claude 下一輪、codex 下一段新對話）；codex 底下 aos-mcp 明寫帶 `AOS_*`、只對 aos 這個 server 免核准（使用者裁「修」「aos 工具免核准」），codex 改了 system 只提醒、不自動開新對話 |
| [knowledge-fix](knowledge-fix/README.md) | 已施工（線 C）：knowledge_write 不給預設庫、收呼叫參數 `root`（都沒有＝KnowledgeMissing），knowledge_read 照舊指出廠庫；thought 進 gadgets（36 支）；每支工具（`aos/tools/`）、每支 `aos-*` 指令（`aos/cli/`、`cli/parts/`）都有節點；必修 7 項與雜訊修完、長檔拆開；新檢查 `knowledge_check` 出廠庫 0 錯誤；大小改推薦值（一檔約 8 KB、一段約 1 KB）。代號結尾等六題待裁 |
