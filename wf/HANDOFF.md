# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-18 晚（compact 前）公司 Windows 機

- **授權與做法**：頂層只當調度者；普通工作 opus、簡單工作與雜活 sonnet、規劃 fable；派出去的 agent（雜活除外）先讀規矩卡；各線不 commit，頂層分件交（`git commit --only -- <路徑>`，因為工作樹同時有好幾條線的改動）。要使用者裁的一律跳選項。push：使用者下午說「可以推」，已推到 `16558491a`；之後的 commit **還沒推、要再問**。這台改檔在 Windows repo，測試在 WSL 暫存複本；生成器用 `wsl -e bash -c 'cd /mnt/c/code/mine/simple_tools/aos && python3 wf/tools/index_gen.py --apply'`（頂層交件前跑）。
- **今天上半場（都已推）**：cpp／py 改名與安裝包形狀 S1～S7 全做完；`WAIT_USER`、`gotchas.md` 退場；進度檔改成 [`wf/progress.json`](progress.json)；出廠範本跟著改兩軸；獨立驗證線照步驟單走通。proto8 頂層進 git：`cpp py templates knowledge docs thinking archive frontend`＋`README.md env.sh install.py`；產物 `bin lib include`。原始碼 `py/aos/`、`py/aos/agentlib/`、`py/aos/apps/<名>/`、`py/tools/{base,aos,agent}/`、測試 `py/tests/`、`py/tests/apps/<名>/`（逐夾跑）。改了 `py/`、`cpp/` 要重跑 `python3 proto8/install.py` 才生效；`AOS_HOME` 要自己先設（沒設 `env.sh` 報 `EnvBad`）。裁定逐字在 [cpp-py-改名/08](../proto8/thinking/2026-11/17/cpp-py-改名/08-要裁的題.md) 文末與 [wf-整理規劃/05](../proto8/thinking/2026-11/17/wf-整理規劃/05-要裁的題.md) 文末。
- **下半場，使用者的話（逐字）**：「好，就如你所說。然後code map也可以開始重建。前端相關先不動。公司WSL的東西整個清掉，重建，然後你幫我試跑，跑完之後再整個清掉，並留下相關紀錄，我之後單開一個session對著這份紀錄，一步一步教我。桌面那份全景網頁看要不要也更新一下。」「能做的先做，七件都做。」
- **下半場已交、還沒推**：`b05e59368` 公司 WSL 清掉→重建→試跑→再清掉，教學本 [公司WSL-重建試跑紀錄](../proto8/thinking/2026-11/18/公司WSL-重建試跑紀錄.md)（WSL 現在沒有 aos；舊樹備份在 WSL `~/.aos/scratch/wsl-rebuild-1118/old-aos-home-backup.tgz`；start-eca 用真 claude 問一句有回）；`5ca59952e` 進度檔 20 條舊線核對現況；`96ae93b81` 三件小的（two_machines 孤兒修好、kernel 範本 README 寫明只能當最後一站、StateBad 補測試）；加上本檔這次的 commit。
- **已回報、改動在工作樹、還沒交**（工作樹混著四條線的改動，交之前先分清各線的檔；等還在跑的兩條回來再一起跑生成器、分件交）：
  - `doc-tail-1118`：37 檔 40 處 `source proto8/env.sh` 改成 `source "$AOS_HOME/env.sh"`（含根 `README.md`、約 20 支程式的錯誤字串／註解、`test_defs.py`、`test_todo.py`）；`wf/STRUCTURE.md` 拆成主檔＋`wf/STRUCTURE/` 四份；`wf-整理規劃.md` 標題；`index_gen_desc.json` 加 `wf/STRUCTURE` 鍵。
  - `codemap-1118`：新檔 `wf/tools/codemap_deps.py`、`tests/test_codemap_deps.py`；改 `codemap_lib.py`、`index_gen.py`、`index_gen.json`、`wf/knowledge/code-map.json`（手寫主檔）、`tests/test_codemap_json.py`、`index_gen_desc.json` 20 個鍵、`py/aos/apps/daemon_ctl/main.py` 檔頭一句。生成器跑完會多 `wf/knowledge/code-map/deps/{cpp,py,bin}.json`。
  - `mid2-1118`（兩件分開交）：件 A `py/tools/aos/kernel/` 新檔 `forwarding.py`、改 `letters.py`、`procs_rules.py`、`README.md`（同夾 `runner.py`、`tests/test_runner.py` 是別條線的）；件 B `py/aos/apps/sandbox/` 的 `main.py`、README、`examples/` 六個檔、`py/tests/apps/sandbox/test_sandbox.py`。B 把沙箱改成「aos 命令帶進整個家唯讀、預設放行 `AOS_HOME`」，只驗了 dry-run 與單元測試，真隔離沒驗。
  - `code-tidy-1118`（已回報）：**件 A 不用動檔**——5 題已在 11-14 落地（`a7eb5ee52`、`2109a6306`）或被 S4 取代，`code-tidy-5` 那條可刪（刪條目要先問使用者）。**件 B 46 檔（40 改 6 新增）**，清單在 scratchpad `ct/b-files.txt`（重開機可能不在；大致是 `py/aos/apps/tools/{main,common,helps,registry,tooldef}.py`、`py/aos/tool_io.py`、`py/tools/aos/kernel/{runner.py,tests/test_runner.py}`、`py/tools/agent/kernel_gate/{_entry,gate_lib.py,tick}`、`py/tools/agent/hook_fire/_entry`、`cpp/aos-daemon/src/{child,daemon}/` 五個檔（只刪舊名註解 7 處）、`py/tests/apps/agent/` 17 檔＋`env_helper.py`、`py/tests/apps/tools/` 10 檔＋`env_helper.py`）。`kernel_gate/_entry`、`gate_lib.py` 跟 doc-tail 的 env.sh 字樣改在同一檔。驗證：80 夾，基準 36 個失敗名、改後 37，多的一支 agent-fsm 計時測試重跑 3 次都綠（偶發），假腦起樹通。它列了 7 題待裁（listen／ask 舊身體退路留不留、run_tool 共用、測試起真 daemon、測試 PATH 拿掉 `~/.local/bin`〔它推薦拿掉〕、`hook_run` 改用 directive_value、swap 搬共用、`agentlib/agent_files.py` 轉接口拿不拿），細節在它的回報、compact 後看不到——要問使用者時先派人照這七個標題重新整理選項。
- **還在跑的線（compact 後等通知，不輪詢）**：
  - `agent2-1118`（opus）：件 A set-def 新做法（讓 `test_set_def.py` 兩支 expectedFailure 轉綠）；件 B `ctl stop` 延後關、`set-def --restart`、`test_stop_linger`；會改行為，回報要有「以前怎樣、現在怎樣」；分開交。
  - 工作樹裡 `proto8/cpp/aos-daemon/src/{child,daemon}/…` 的 C++ 也有改動，是這兩條其中一條的（看回報確認是哪條、有沒有授權範圍內）。
- **各線回來後頂層要做的**：分件交、交件前跑生成器；然後派一條收尾線：(1) 修 `test_aos_ws_reply_match…test_pre_change_aos_ws_reads_the_same`（只在帶 `.git` 的 clone 才跑到，`ImportError: cannot import name 'ws' from 'aos'`）；(2) 步驟單補漏（再起時視窗 B 的 `cd llms` 會失敗、關樹那行根已停時第二句不跑、`~/aos-home` 已存在時 `cp -r` 會抄到裡面、`.pth` 可直接 rm、耗時改「約 1～1.5 分鐘」、跑測試前要 `source $AOS_HOME/env.sh`；詳見教學本文末）；(3) `wf/workflows/common/conventions/02-導航index維護鏈.md` 補 code map 依賴表四句；(4) 幾處不準的字：`py/docs/01-分層等/02` 第 9 條「source env.sh 讓 sys.path 找得到」、`templates/tests/image-move-check/README.md` 還寫 `~/.local/bin`、`proto8/docs/NORMS/附錄4-持久檔.json` 第 335 行 evidence 的 `letters.py` 該是 `forwarding.py`（只改路徑）、`py/aos/tool_io.py` 第 8 行註解講沙箱 ro；(5) `wf/progress.json` 照各線回報更新（`wrapup-1115`、`kernel-limits`、`old-lines-1112`、`path-rules-tail`、`code-tidy-5`、`refactor-tidy-inventory`、`set-def-fx1`、`cpp-py-rename`、`rebuild-aos-home`；各線建議的字在它們的回報裡，compact 後看不到就照 commit 訊息與本檔重寫）。最後更新本檔、問使用者推不推。
- **要問使用者的（還沒問，跳選項）**：
  1. 進度檔 `company-w6-w8` 跟 `codex-trust-company` 是同一件，刪前者？
  2. kernel 範本要不要能直接當中間站（要他定 `count_daemon` 指哪台；現在只寫說明、不補）。
  3. 沙箱的家怎麼認：甲 看命令的真位置（現在的做法，`commands` 沒列 aos 命令就不綁家）；乙 只要 `AOS_HOME` 有設就一律綁（較寬）。
  4. 沙箱看得到整個家（含 `thinking/`、`docs/`、`py/`、`cpp/`）接不接受：甲 接受、照規劃；乙 只綁 `bin lib include templates knowledge`（偏離「綁一個夾」）。
  5. 之後兩條線回報裡新列的題。
- **桌面成品（repo 外）**：桌面 `aos-全景-1118/index.html`（六頁新版，沒人眼看過；產生腳本在同夾 `_build/`）；舊的 `aos-全景-1117` 原樣留著。
- **還留著的尾巴**（細節在 progress.json）：`proto8/docs` 條文舊字樣、`docs/zh`（已裁先不動）；前端全部（等大修）；家機沒驗；真模型（API 端點）沒驗；kernel 骨架三處不順（修了會改行為，原文「等有需要再動」）；等活樹、等家機、等使用者裁的各批見進度檔。
- **暫存（repo 外，沒刪）**：WSL `~/.aos/scratch/*-1118/`。
