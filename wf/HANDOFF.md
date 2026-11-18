# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-18 傍晚 公司 Windows 機

- **授權與做法**：頂層只當調度者；普通工作 opus、簡單工作與雜活 sonnet、規劃 fable；派出去的 agent（雜活除外）先讀規矩卡；各線不 commit，頂層分件交。要使用者裁的一律跳選項。push：使用者 11-18 開工說「下班前一次推。」、下午說「可以推」，今天的都已推；新 session 要重問。這台改檔在 Windows repo，測試在 WSL 暫存複本；生成器用 `wsl` 在 `/mnt/c/...` 跑 `python3 wf/tools/index_gen.py --apply`。
- **cpp／py 改名與安裝包形狀：S1～S7 全做完、已推**（S3 `fc7430adf`、S4 `521036a64`、S5 `269cca6bf`、S6＋S7 `96b3e2e8c`）。proto8 頂層進 git 的：`cpp py templates knowledge docs thinking archive frontend`＋`README.md`、`env.sh`、`install.py`；安裝產物（不進 git）：`bin lib include`。
  - 原始碼：C++ 在 `cpp/`；Python 在 `py/`（套件 `py/aos/`、`py/aos/agentlib/`、各指令本體 `py/aos/apps/<名>/main.py`、工具 `py/tools/{base,aos,agent}/`、測試 `py/tests/` 與 `py/tests/apps/<名>/`，後者要逐夾跑）。`cmd/` 整夾收掉了。
  - `python3 proto8/install.py`：編 C++、把 `py/` 抄成 `lib/`、照 `py/entries.json` 在 `bin/` 生入口（共 30 支）。**改了 `py/`、`cpp/` 要重跑 install.py 才生效**（「改 repo＝改活樹」不成立了）。
  - `env.sh` 不再自己設 `AOS_HOME`，沒設報一行 `EnvBad`；`~/.bashrc` 要先寫好 `AOS_HOME`。PATH 是 `bin/`＋`frontend/bin`（使用者 11-18：「照留，等前端大修 (Recommended)」）。
  - 起手範本 `templates/start-api`、`start-eca`（逐字抄本，`templates/tests/test_start.py` 守同步）。
  - [重建步驟單](../proto8/thinking/2026-11/17/重建步驟單.md)＝第 0 步＋安裝六步＋更新五步。獨立驗證線（verify-1118）在 HEAD `96b3e2e8c` 的乾淨 clone＋假 HOME＋假腦逐字走過，每步對得上；全部測試紅的都在已知清單（清單在 `8514d5e3b` 的 commit 訊息）。沒驗：第 0 步、start-eca、真模型、家機。
  - 裁定逐字：[08-要裁的題](../proto8/thinking/2026-11/17/cpp-py-改名/08-要裁的題.md) 文末「11-18 施工當天的題」（含施工線代定、可翻案的三點）。
- **wf 整理今天做完的**：`WAIT_USER.md`、`wait-user/`、`gotchas.md` 退場（`3256c6cae`），三軸變兩軸（信、進度）；進度檔 `SESSION-LOG.md` 轉成 [`wf/progress.json`](progress.json)（`d1a0dbb8d`；交件工具的 op 改叫 `progress_upsert`／`progress_delete`）；出廠範本 `proto8/knowledge/wf` 跟著改成兩軸。逐字在 [wf-整理規劃/05](../proto8/thinking/2026-11/17/wf-整理規劃/05-要裁的題.md) 文末。
- **等使用者自己做**（使用者 11-18：「你自己照步驟單做 (Recommended)」，agent 不碰）：公司 WSL 的第 0 步（移走舊 `aos-proto8.pth`、刪 `~/.local/bin` 舊 `aos-*` 連結、`~/.bashrc` 加 `AOS_HOME`）、`~/repo/aos` 拉新版後跑 `install.py`、重建 `~/aos-home`。家機同理，`git pull` 後舊的 `proto8/impls/`、`proto8/cmd/` 殘留夾可整夾刪。
- **在跑的線**：沒有。
- **還留著的尾巴**（細節在 progress.json）：`proto8/docs` 條文句子裡的舊字樣約 67 處與 `docs/zh/*.html` 舊安裝法（已裁先不動）；約 37 個檔還寫 `source proto8/env.sh`（`AOS_HOME` 有設就能用）；code map 專案依賴表是空的（先放著）；前端測試 `test_slash` 把暫存夾寫死（跑法寫在 testing.md，前端等大修）；`STRUCTURE.md` 超過 8 KB；`aos-user` 不在 repo；`wf-整理規劃.md` 主檔標題還寫「還沒裁」。
- **暫存（repo 外，沒刪）**：WSL `~/.aos/scratch/{s3,s4,s5,s67,verify,tail2,progress-json}-1118/`；桌面 `aos-全景-1117\index.html` 畫的是改名前的樣子。
