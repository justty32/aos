# SESSION-LOG — 進度（hub）

← [AGENTS.md](../AGENTS.md)

**只放「還沒完成」的活狀態，完成即刪**（每日日誌 11-17 起停寫；哪天做了什麼看 thinking 的日索引）；待使用者親自驗、做的另見 [WAIT_USER.md](WAIT_USER.md)。每條一行 open 狀態＋細節連結。11-17 瘦身前的全文在[留底](../proto8/thinking/2026-11/17/session-log-瘦身留底.md)（下面「留底 N」＝其中第 N 條）。

## 最新進度

- **open｜重建 `~/aos-home`**：使用者自己照步驟單重建（程式只有 repo 一份、`source proto8/env.sh`）；以前「換樹時帶／換樹後驗」的尾巴都等重建後再驗；公司 WSL 的樹停著、`~/repo/aos` 還沒拉 → [重建步驟單](../proto8/thinking/2026-11/17/重建步驟單.md)、[留底](../proto8/thinking/2026-11/17/session-log-瘦身留底/07-第49到54條與重建.md#rebuild)
- **open｜路徑規則與八夾的尾巴**：八夾與規則一已進 main；剩 aos-view 執行檔搬 `bin/`（viewbin-1117 在做）、沙箱只綁 `<家>/lib`（規劃是整個家）、`install.sh` 舊 `.pth` 提醒要不要拿、aos-teams/06 硬規則第 5 條新說法待使用者確認、wf 幾處還寫 `~/aos-home/knowledge` → [待裁網頁-答案](../proto8/thinking/2026-11/17/待裁網頁-答案.md)、[路徑規則](../proto8/thinking/2026-11/17/路徑規則.md)
- **open｜重構與 tidy 盤點剩的**：九題與追加三題都已交；剩拆 aos-view／aos-tools 大檔、測試共用 helper、thinking 11-13 起先提取再精簡（Q1）、舊退路清理、兩支 helper 自寫的 `read_json` → [盤點](workflows/tidy/reports/2026-11-17-重構與tidy盤點.md)
- **等使用者｜條文**：分檔已拆到約 8 KB、33 題裁定已落；使用者 11-17「條文這東西以後我會大修，現在不用這麼急」——新冒出 17 題、N-63 `AOS_HOME` 那格、條文裡 `py/`／`kernel/` 舊路徑字樣、三處沒精簡的內文都放著 → [新的待裁](workflows/tidy/reports/2026-11-17-分檔精簡與裁定落實/02-新的待裁.md)
- **open｜wf/ 整理剩的**：12 題照各題 a 已落（坑併 public、規矩卡、日誌停寫、死入口與 INDEX 已刪）；剩 `WAIT_USER`＋`wait-user/` 退場（條目寄專區）、進度檔轉 `wf/progress.json`（同一個 commit 改 `commit_queue.py`、`compact_reload.sh`）、`common/gotchas.md` 指標頁收掉、STRUCTURE 超過 8 KB（等段 9） → [wf-整理規劃](../proto8/thinking/2026-11/17/wf-整理規劃.md)
- **open｜kernel 框架與限資源**：11-14 批 5～14、限資源 B1～B7 多已進；剩 C′ B 包、11-13 留的雜項（`letters.py`、tests 偶紅、骨架三處、`max_running`）（狀態沒核到） → [留底 16](../proto8/thinking/2026-11/17/session-log-瘦身留底/02-第12到20條.md#t16)、[留底 2](../proto8/thinking/2026-11/17/session-log-瘦身留底/01-第1到11條.md#t2)
- **open｜set-def 新做法（fx-1）與改名兩步（em-Q4）**：沒進 main（`test_set_def` 仍兩支 expectedFailure），照施工圖重做 → [misc-1114](../proto8/thinking/2026-11/14/misc-1114.md#1-fx-1set-def-改成停拔同一個-stack-掛回)
- **open｜11-15 收尾剩的**：guard 仍「審查中」、接線前實測四件；回答配對待決五點；`test_two_machines` 留孤兒 `body_a.py` → [留底 37](../proto8/thinking/2026-11/17/session-log-瘦身留底/04-第35到38條.md#t37)
- **open｜全景頁剩的**：地圖方向鍵、Ctrl+K、P5 文字、按鈕字「（排隊中）」要重建前端（狀態沒核到）；沒驗 /context 真畫面、Firefox、手機單欄等；改名時改讀設定 → [留底 41](../proto8/thinking/2026-11/17/session-log-瘦身留底/05-第39到42條.md#t41)、[43](../proto8/thinking/2026-11/17/session-log-瘦身留底/06-第43到48條.md#t43)
- **open｜eca 剩的**：a2a 的 codex 身與三項實測；live_mail 還沒看到回合中併信、codex 身研究沒開；fsm「先更新交接檔再壓」待定；`config.window`；daemon 子行程增減沒查 → [留底 19](../proto8/thinking/2026-11/17/session-log-瘦身留底/02-第12到20條.md#t19)、[52](../proto8/thinking/2026-11/17/session-log-瘦身留底/07-第49到54條與重建.md#t52)、[53](../proto8/thinking/2026-11/17/session-log-瘦身留底/07-第49到54條與重建.md#t53)
- **等使用者｜11-15 意見裡「之後再說」的**：stack 遷移、aos-view 改名（含 aos-user-tick）、systemd 規則、aos-view 為何常掛 → [留底 39](../proto8/thinking/2026-11/17/session-log-瘦身留底/05-第39到42條.md#t39)、[40](../proto8/thinking/2026-11/17/session-log-瘦身留底/05-第39到42條.md#t40)
- **等使用者｜pi coding agent**：範圍待確認 → [留底 47](../proto8/thinking/2026-11/17/session-log-瘦身留底/06-第43到48條.md#t47)
- **等使用者｜其他小題**：Pages 正式發佈（拿 noindex、LICENSE）、eca-claude Read 權限、A② gate、compact_hook 開不開、aos-teams/06 第 5 條、fsm 角色說明補知識庫 → [留底 49](../proto8/thinking/2026-11/17/session-log-瘦身留底/07-第49到54條與重建.md#t49)、[35](../proto8/thinking/2026-11/17/session-log-瘦身留底/04-第35到38條.md#t35)
- **open｜家目錄清理（家機）**：scratch 用完收規則、`~/.claude/projects` 1.8G、`~/.cache/aos-*`、`~/.stack` 舊信箱；兩個常駐服務使用者自己處理 → [留底 38](../proto8/thinking/2026-11/17/session-log-瘦身留底/04-第35到38條.md#t38)
- **open｜公司機 W6、W8**：Codex 設定檔 1 處沒查；測試對話紀錄見 [wait-user/04](wait-user/04-雜事.md) → [留底 4](../proto8/thinking/2026-11/17/session-log-瘦身留底/01-第1到11條.md#t4)
- **open｜11-13 前開的設計尾巴**：外部 MCP（CLI 自接 server 壞了看不到、沒驗三項、P1）、ops-agent（yes/no hook、索引檢查）、index 三題、eca 子 agent codex 身、Codex 兩隻待核、team-model 沒同步、compact_reload 補驗 → [留底 12](../proto8/thinking/2026-11/17/session-log-瘦身留底/02-第12到20條.md#t12)、[留底 01](../proto8/thinking/2026-11/17/session-log-瘦身留底/01-第1到11條.md)、[03](../proto8/thinking/2026-11/17/session-log-瘦身留底/03-第21到34條.md#t21)
- **open｜11-12 前的舊線**：two-machines、大修材料 56 列、node-pool、special-cases K-1、apply-ideas、LLM kernel 第二步、11-10／11-11 補驗；小尾巴（eca_tidy SUMMARY、repo index、11-12 tidy、11-13 文件沒對齊、`StateBad` 沒測試格） → [留底 03](../proto8/thinking/2026-11/17/session-log-瘦身留底/03-第21到34條.md)
- **暫停｜arcagi**：等 aos 大修完 → [留底 33](../proto8/thinking/2026-11/17/session-log-瘦身留底/03-第21到34條.md#t33)
- **凍結｜arknights-kb**：到至少 2026-12-14，`~/code/playground-ak5` 不刪 → [user](workflows/common/user.md)
- 導覽：[thinking](../proto8/thinking/README.md)、[CONCEPTS](../proto8/docs/CONCEPTS.md)、[NORMS](../proto8/docs/NORMS.md)；停在半路的見 [restart](../proto8/thinking/2026-10/11/restart/README.md) §4

## 各工作流 session-log

> 某工作流長出自己的 `session-log.md` 後，在這裡加一列。（目前沒有）

## 不屬任何工作流的進度

- （無）
