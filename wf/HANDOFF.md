# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-11-17 下午 公司 Windows 機（收工前）

- **授權與做法**：頂層只當調度者；普通工作 opus、雜活 sonnet、規劃 fable；各線不 commit，頂層分件交。要使用者裁的一律跳選項（「有需要我裁，都跳選項」）；題多就做成桌面網頁。push 要先問（使用者「我今天五點下班，下班前再統一push」）。這台改檔在 Windows repo，測試在 WSL 暫存複本；生成器用 `wsl` 在 `/mnt/c/...` 跑 `python3 wf/tools/index_gen.py --apply`。
- **今天做完的大事**（都已 commit）：
  - proto8 頂層收成八夾 `impls cmd lib templates knowledge docs thinking archive`＋`README.md`、`env.sh`（`ad98142b2`、`3976babff`）；路徑規則一「只認一個家」：全靠 `AOS_HOME`，`source proto8/env.sh`；`py` 併進 `lib`、`kernel` 進 `templates/kernel`、`extras` 解散、aos-view 進 `cmd`。
  - 重建樹的步驟單：[重建步驟單](../proto8/thinking/2026-11/17/重建步驟單.md)（暫存樹用假腦實跑過第 1～12 步）。使用者要自己重建 `~/aos-home`。
  - 條文：三份入口純條文、分檔拆到約 8 KB、33 題裁定落完（`bb06c0607`、`94f173920`、`cf19fc43f`）。使用者：「條文這東西以後我會大修，現在不用這麼急」——新冒出的 17 題、N-63 `AOS_HOME` 那格、條文裡 `py/`／`kernel/` 舊路徑字樣都先放著。
  - wf 整理：坑併進 `wf/public`、規矩卡 `wf/workflows/common/rules-card.md`（被派的 agent 改讀它）、每日日誌停寫凍結、新報告寫 thinking、死入口與三個 archive 夾已刪、`wf/INDEX*` 已刪。
  - 程式小件：aide-def 只放差異、dist 不進 git、BookOld 拿掉、hook 收進 tool_io、`llm.hpp` 改名等（`164a9664b`～`402149650`）。
  - 使用者答的題全文：[待裁網頁-答案](../proto8/thinking/2026-11/17/待裁網頁-答案.md)。
- **在跑的線**：`viewbin-1117`（aos-view 執行檔搬進 `cmd/aos-view/bin/`，使用者選「搬進 bin/」）。回來後核對、交、重跑生成器。
- **桌面成品（repo 外）**：`aos-待裁-1117.html`（已答完）、`aos-全景-1117\index.html`（aos 全景，使用者要的「兩者的架構」＝他的七塊對現在八夾；做的線沒親眼看過畫面）。
- **還沒做**：`wf/WAIT_USER.md`＋`wait-user/` 退場（剩的條目要寄進專區）；進度檔轉 `wf/progress.json`（今天不轉）；`common/gotchas.md` 的兩行指標頁等 `dev-env.md` 第 56 行改連結後收；沙箱只唯讀綁 `<家>/lib`（規劃是整個家）；`install.sh` 的舊 `.pth` 提醒、兩支 helper 的 `read_json` 要不要收；aos-teams/06 硬規則第 5 條被小工改成「要編 C++ 先回報調度者」待使用者確認；wf 裡幾處還寫 `~/aos-home/knowledge`；公司 WSL 的 `~/repo/aos` 還停在早上的版本、`~/aos-home` 停著等重建。
