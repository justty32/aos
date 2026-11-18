# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-18 21:50（家機）——五條被打斷的線全交完；今晚各線都收了，沒有在跑的

**授權**：頂層只調度（普通 opus、雜活 sonnet），agent 開工前讀 wf/ 規矩與 `proto8/knowledge/aos/_description.json`。push：使用者「睡前十一點一次性push。」——23:00 推一次（session 內排程），之後的 commit **不自動推、要再問**。在家。

**今晚做完的**（細節 `git log --since="2026-11-18 20:00"`）：家機同步（本機舊 commit 備份成 tag `home-local-abed65ecd-1118`、改寫成 progress `pages-trial-1116`）；修 main 裝不起來（`dc4218e8a`）；五條線：rm-treestart、cooldown、kit-merge（`62940fb7c`）、eca-pi 乙丙（`ce2e875eb`，真 pi 實跑成）、教學 13～19（`fbce69eae`）；家機 litellm 真模型試跑成（紀錄在 `~/.aos/scratch/realmodel-home-1118/realmodel-home-1118.md`，**還沒收進 repo**，可補進重建試跑紀錄「真 API 一節」）；前端跟上新流程（`8e0cf5caa`）；沙箱落差（`sbx-fix-1118.md`；使用者裁「先不修，只寫 README」「沙箱這個基本上是使用者要自己承擔的風險吧」）；hook_run 吞回 stderr；T7 1～7 步（`790ca0359`）；只驗包（`97dcef448`）；set-def 名額滿帶期限＋cooldown 兩小改＋tools ls 提醒（`20ee2dc56`、`2ac96ed8a`）；progress 清帳（`dd5981dc7`）。

**三份調查（只調查沒動程式），使用者的回應**：
- 預設 stack `thinking/2026-11/18/default-stack-1118/`：暫定丁（daemon 寫路標＋乙）、「說不定我之後會改主意，改成往上層資料夾找，先留着」→ **下次 compact 完再討論**。
- Linux 當硬體 `linux-as-hw-1118/`：權限「先做防呆就好，先考慮單人使用，模型可信」；子帳號那一哩「明天在公司再說」。
- Python 編譯成 aos 夾 `aos-compile-1118/`（07 有裁定）：初期做庚（agent 版 tool_spec：一支 agent.py 宣告、agent_def check 重生 json）、後期做己（濃縮總覽）、除錯以 loop 為主 →「明天再正式開始」。

**compact 完要做的**：① 跟使用者討論預設 stack（丁或往上層找）；② 開始重建家機 `~/aos-home`（使用者「也順便開始重建家機aos-home」；照重建步驟單安裝六步；重建後才刪 `proto8/impls/`——使用者裁「刪掉」，617 檔 58 MB 未進 git，progress `impls-old-builds`）；③ 11-19 開工 aos-compile（庚）。

**先拖著／之後再說**：thinking 11-13／11-14 精簡範圍、eca-claude 範本預設權限；aos-llm 丁案「順延」；pi context 壓縮；guard「先擱著」；codex 身剩項「先留著」；家機 proxy 不加 key；litellm 版本明天在公司實測 1.109.1 再定；公司 litellm「等一下再說」；`~/.aos/scratch`（9 GB+）先不清；前端三小毛病先留著；自動記憶「我們管不着」。

**坑**：家機 `~/.tmux.conf` 開新伺服器會自動復原使用者存的 session——私人 tmux 一律 `-f /dev/null`。家機 pi 預設是 deepseek（沒登入），範本要寫明 `openai-codex/gpt-6.1-sol`。工作樹剩兩個未追蹤：`proto8/impls/`（等重建後刪）、`proto8/templates/tests/kits/_index.json`（使用者放的，origin 沒有、生成器不收，照留）。
