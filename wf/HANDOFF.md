# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-18 下午（收尾中）公司 Windows 機

**授權**：頂層只調度（普通工作 opus、雜活 sonnet、規劃 fable），agent 開工前讀 AGENTS.md、規矩卡、`proto8/knowledge/aos/_description.json`。push 要再問——使用者早上說「下班前一次推」，`16558491a` 以前已推；**未推 9 筆**（`b05e59368`…`2114a5171`）。前端先不動（等大修）。

**今天下半場已交**：`43a07ea85`（proto8 五條線合交：env.sh 字樣、letters 拆 forwarding、沙箱帶整個家且家先認 `AOS_HOME`、aos-tools 拆五支、set-def 新做法與 `ctl stop` 延後關）、`b5ccbd6e1`（code map 依賴表、STRUCTURE 拆檔）、`e83c78d47`（litellm 說明兩份）、`2114a5171`（收尾線：測試 PATH 拿掉 `~/.local/bin`、`agent_files.py` 拿掉、hook_run 用 directive_value、swap 搬 `py/aos/`、兩支舊版對照測試修好、步驟單補六處、進度檔刪兩條改八條）。裁定逐字在 `proto8/thinking/2026-11/17/cpp-py-改名/08-要裁的題.md` 文末。工作樹乾淨，沒有線在跑。

**卡在使用者**：公司 WSL 的 litellm proxy 已裝好（`~/litellm-proxy/`，1.109.1，`127.0.0.1:4000`，說明見 `proto8/thinking/2026-11/18/litellm-proxy-接gpt帳號.md`），要他親手 `cd ~/litellm-proxy && ./login.sh` 走 ChatGPT 裝置碼登入。登完後要做（使用者原話「真沙箱隔離這塊等API真模型端點好了就來試試看。…重建試跑記錄也可以接真API」）：
1. 真模型試跑：`./start.sh`、llm kernel 視窗 `export LITELLM_KEY="$(cat ~/litellm-proxy/master.key)"`（不印值）、`llm set model=luna`，問一句；再試工具呼叫、terra／sol。
2. 真沙箱隔離完整檢查（box_check 那套；目前只真開過一次確認家可見、唯讀）。
3. `proto8/thinking/2026-11/18/公司WSL-重建試跑紀錄.md` 補真 API 一節。
4. 做完更新 `wf/progress.json` 的 `rebuild-aos-home`、`path-rules-tail`。

**等使用者裁（還沒問成選項框的）**：
- `set-def --restart` 已照 fx-1 拿掉（B 包字面說留）；他沒反對就照現在。
- 沙箱兩個代定細節：沒列 aos 命令時不檢查 `AOS_HOME`；命令來自另一個家時以 `AOS_HOME` 為準、只警告。
- litellm：版本要不要退到 `1.106.x`；proxy 要不要長駐（systemd user service）；端點出錯時 `aos-agent listen` 只說 `AnswerMissing` 不帶理由，要不要開線補。
- hook_run 現在把 aos-directive 的錯誤行照轉 stderr，要不要改回吞掉。
- `cpp/aos-daemon/examples/root/` 的 s6 與 service 範例還寫 `~/.local/bin`，改不改。
- `wf/workflows/testing.md` 要不要補「跑測試前先 source env.sh」。

**其他**：WSL `~/.aos/scratch/` 舊暫存與舊樹備份已清（使用者授權）；現在留 `agent2-1118`、`sandbox-home-1118`、`litellm-1118`、`wrap-1118`、`wsl-rebuild-1118`（只剩小 log）。公司 WSL 沒有 aos（等使用者另開 session 照教學本重建）。桌面 `aos-全景-1118` 還沒人眼看過。家機重建沒做。
