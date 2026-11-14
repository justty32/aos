# 站台小卡：隊長派 kit 隊員時的流程（2026-11-14，維護者 repo-aos）

← [kits](README.md)｜只給隊長看，隊員不讀。規矩改了就改這張卡和日期；隊員要守的禁令在 `site.txt`，不放這裡。

1. **做定義**：`agent_def {"op":"new","template":"agent-fsm","path":"defs/gather"}`，再把 `wf/workflows/dispatch/kits/gather/` 裡的 `system.txt`、`tools.json`、`llm.json`、`.env` 蓋過去，然後跑 `agent_def check`。同一條線的隊員共用這一份定義。
2. **掛隊員**：
   - `subagent add`，name 用 `<你的名字>-<角色>-<編號>`，ws 用 `<線夾>/<agent 名>`。
   - limits 帶 `{"mem_mb":1024,"files":256}`，`procs` 別設。
   - envs 可以帶 `AOS_NOTIFY_BOX`；不帶就是你的信箱。
3. **任務書**：開頭寫唯一目標、可讀可寫的路徑、交付物（`out/answer.md`）、完成條件（讓它抄進 goal）。蒐集員不用附必讀清單（使用者 11-14 裁定，按角色分）。
4. **等人**：`say` 之後結束這一輪，用 `clock_register` 叫醒自己再看。`subagent listen` 不要等超過 60 秒。也可以直接等它寄來的信。
5. **驗收**：讀 `out/`，逐條對證據，不重跑。
6. **投稿**：隊員的 `out/submit/` 有稿，就搬到線夾的 `public-submit/` 或 `aos-advice/`，再寄任務書指定的對象（11-14 起是各部部長），title 開頭 `[public-submit]` 或 `[aos-advice]`（規矩見 wf/public、wf/advices 的 README）。
7. **往上報**：寄任務書指定的對象（11-14 起是各部部長）。標題寫判斷、寫要什麼（status）；卡住的信先寫已排除的。**要使用者拍板的題目**用 `aos-user send --kind decide` 寄進使用者專區，題目會出現在全景頁上（做法照 wf/public/user-zone-mail.md）；寄出後再寄一封 NEEDS-USER 或 PROGRESS 給同一個對象備查（使用者 11-14 午）。
8. **commit**：用 `commit-request claim`／`submit`。隊員不 commit。
9. **收隊**：`subagent rm`（stack 留著）；核對自己記下的 pid 都不在了。
