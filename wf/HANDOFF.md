# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [SESSION-LOG](SESSION-LOG.md) 的「最新進度」段。

## 2026-11-17 收工 公司 Windows 機

- **授權與做法**：頂層只當調度者；普通工作 opus、雜活 sonnet、規劃 fable；各線不 commit，頂層分件交。要使用者裁的一律跳選項（「有需要我裁，都跳選項」）；題多就做成桌面網頁。push 要先問。這台改檔在 Windows repo，測試在 WSL 暫存複本；生成器用 `wsl` 在 `/mnt/c/...` 跑 `python3 wf/tools/index_gen.py --apply`。每日日誌停寫。
- **proto8 現在的樣子**：頂層 `cpp cmd lib templates knowledge docs thinking archive frontend`＋`README.md`、`env.sh`、`install.py`。路徑規則一「只認一個家」：全靠 `AOS_HOME`，`source proto8/env.sh`。
- **cpp／py 改名與「Linux 標準安裝包」形狀（施工到一半）**：規劃與 15 題裁定在 [cpp-py-改名](../proto8/thinking/2026-11/17/cpp-py-改名.md)（施工單 `07`、裁定在 `08` 文末）；外部依賴 6 題裁定在 [外部依賴](../proto8/thinking/2026-11/17/外部依賴.md)（`06` 文末）。
  - **做完 S1、S2**（`2ba0546f6`）：`impls`→`cpp`；一份頂層 `cpp/Makefile`；nlohmann `json.hpp` 收進 `cpp/third_party/nlohmann/`；CMake 與 vcpkg 檔全刪；`proto8/install.py`（編 C++、成品進 `proto8/bin/`、`proto8/include/`，兩夾不進 git）；`env.sh` 把 `$AOS_HOME/bin` 放上 PATH。**新流程：clone → `python3 proto8/install.py` → `source proto8/env.sh`。** 驗證是施工線在 WSL 快照跑的（全部測試不比基準紅、假腦起樹走通），頂層沒重跑、家機沒驗。
  - **還沒做 S3～S7**：`lib`→`py` 換手（現在 `lib/` 仍是原始碼、還沒有 `py/`，`cmd/*/bin` 的 Python 入口也還沒進 `bin/`）、樹裡 `env.sh` 轉去 `source "$AOS_HOME/env.sh"`（L-7 C）、起手範本（L-10 A）等。施工線的分步紀錄在公司 WSL `~/.aos/scratch/build-1117/groups.md`（repo 外）。
  - **傍晚補問四題已答**（逐字在 [08-要裁的題](../proto8/thinking/2026-11/17/cpp-py-改名/08-要裁的題.md) 文末）：code map 依賴表變空「先放著」；`docs/zh/*.html` 舊安裝法「先不動」；公司機 `proto8/cpp/*/{bin,build,lib}` 舊編譯產物已刪；`install.py`「完全不管」前端。下班前再問兩題也已答、已做：條文裡 `impls/` 的路徑只改路徑成 `cpp`；aos-teams/06 硬規則第 5、6 條的指令換成 `install.py`。
  - **條文裡還留著的**：句子裡單獨的「impls」字樣沒動（條文先放著）。
- **aos-view → aos-frontend**（`5c951ee8e`）：改名、整夾搬到 `proto8/frontend/`，是選配的網頁外掛；舊前端 `web/`、`ui/v1/` 已刪（`934c7482e`）。`AOS_VIEW_HOME`、`~/.aos/view` 沒改名；`API.md` 還講 v1；使用者說之後會整個大修。小助手 hook 的新路徑沒被測試跑到。
- **今天其他做完的**：八夾、路徑規則、重建樹的[步驟單](../proto8/thinking/2026-11/17/重建步驟單.md)（已改成 `install.py` 新流程，第 1～12 步在乾淨 clone＋暫存樹用假腦實跑過；已知偶紅：aos-daemon `test_bad_letter` 一支在整夾一起跑時紅過一次、單獨跑 3 次都過）、條文 33 題落完（使用者：「條文這東西以後我會大修，現在不用這麼急」）、wf 整理（規矩卡 `wf/workflows/common/rules-card.md`）。使用者答的題全文：[待裁網頁-答案](../proto8/thinking/2026-11/17/待裁網頁-答案.md)。
- **在跑的線**：沒有。
- **桌面成品（repo 外）**：`aos-待裁-1117.html`、`aos-待裁-1117-改名.html`（都已答完）、`aos-全景-1117\index.html`（畫的是改名前的八夾）。
- **還沒做的舊尾巴**：`wf/WAIT_USER.md`＋`wait-user/` 退場；進度檔轉 `wf/progress.json`；`common/gotchas.md` 指標頁；沙箱只唯讀綁 `<家>/lib`；`install.sh` 的舊 `.pth` 提醒、兩支 helper 的 `read_json`；wf 裡幾處還寫 `~/aos-home/knowledge`；`aos-user` 不在 repo；公司 WSL 的 `~/repo/aos` 還停在早上的版本、`~/aos-home` 停著等重建。
