# WAIT_USER — 等待使用者的事

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

需要**使用者親自做 / 驗證 / 拍板**才能繼續的事——例如：實機/實環境測試、外部服務登入、環境變數設定、權限操作、需要帳號的下載、**催/開/fork 另一個 agent 處理急件**（見 [inbox](workflows/inbox/README.md)：寄了信但很急、對方可能沒開）。Claude 能做結構性驗證＋打包到極限；跨不過去的那一關記這裡等使用者。

**設計裁決也算**——照 [AGENTS 鐵律 5](../AGENTS.md)「大方向是使用者的」，需要你一句話才動得了工的，
對我來說跟「沒有帳號密碼」是同一種卡住。**本檔只留一行 ＋ 連結**，脈絡在各自的原始文件裡，不在這裡重講。

**只列還沒做的**——做完即移除（不留已完成清單，歷史看 git log）。

> **膨脹就拆**：待使用者項堆多了，就開 **`wait-user/`** 資料夾按類別拆檔，本檔退回只留一張 `| 類別 | open | 清單 |` 導航表（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

## 待使用者項

- **no-pid P8**：公司 WSL 試驗場改三層並親驗；家機在可連 user bus 的殼驗 scope 的 `memory.max`（本次沙箱擋住） → [18-P8實作結果](../proto8/thinking/2026-11/05/no-pid/18-P8實作結果.md)

- **真 Claude Code 讀不讀 aos-mcp 的 instructions**（11-05 夜邊緣測試留的，要你實跑；同批另五題 11-05 夜已裁「剩下都照推薦」，排在大重構之後做，見 SESSION-LOG）→ [small-thought](../proto8/thinking/2026-11/05/small-thought/README.md)
- **試驗場（家機 11-06 晚 P8 改成根→總機／領班→agent 三層，舊的在 `~/code/playground.old-11-04`）**：假腦、真腦（家機 `stupid-fast` 代號改指 `google/gemma-4-e4b`，只改試驗場那份）、eca_bob 真 claude 都照教學（`~/Desktop/aos-試驗場教學.html`、試驗場 `README.md`）跑過；**剩要你親手試**：`aos-agent open --target eca_bob` 的畫面、根（視窗一）Ctrl-C 後重開（自動驗證已過，仍可親手試）
- 親手試 procs 與 ctl 指令（11-03 實作，[procs 步驟 12](../proto8/thinking/2026-11/03/procs/09-實作步驟表-不實作-給隊長.md#實作步驟表不實作給隊長)、[ctl-commands](../proto8/thinking/2026-11/03/ctl-commands/README.md)）：試驗場的 `daemon/daemon.json` 11-04 夜已照 procs 寫好（`procs` 裡帶 `llm`、`procs_ctl_mailbox`），照桌面 html 起 daemon 後在視窗二試（aos-daemon-ctl 指令；`ls` 沒有種類欄）。試：`aos-daemon-ctl add --stack /tmp/x --name c $R/lib/base/clock`（`$R`＝env.sh 設的 proto8）、`where --stack c`、`stop c`（`ls` 是 stopped、`/tmp/x/ctl.json` 是 `{"cmd": "stop", …}`）、`kill -9` daemon 再起它沒被起、`start c`、`pause c`／`resume c`、對 exec 型做 `stop`＝`CtlMissing`；（11-05 晚起：自己出錯結束的 loop 型留在表上 `stopped`＋英文 `reason`，修好 `aos-agent llm reset`／`tools reset` 再 `aos-agent ctl start`，見 [edge-agent 裁定落實](../proto8/thinking/2026-11/05/edge-agent/README.md#裁定落實11-05-晚隊長)）
- 親手試 daemon 的新窗與 log（11-02，state 窗那輪；拷貝裡頂層實跑過）：照桌面 html 第 1、2 步起 daemon（`daemon/_entry.json` 已帶 `--enable-logs`，log 直接印在視窗一）；視窗二 `watch -n1 ls -l --time-style=full-iso $AOS_DAEMON/`：睡著時 `state.json`、`procs_state.json` 的時間不動，`aos-agent add` 一隻後 procs_state 動一次。代定與要你看的通則差異 → [state 窗 § 實作結論](../proto8/thinking/2026-11/02/state-window/06-實作結論-11-02.md#實作結論11-02)
- 公司那台桌面的說明頁（11-06 大重構 S5 後）：`aos-試驗場教學.html`、`aos-三扇門與結束碼.html` 已照新路徑改好（改前備份在桌面 `aos-舊版備份-1106\`，確認沒問題可整夾刪）；`aos指令與格式參考`、`aos現況地圖`、`aos親手試指南` 三份是 10 月底的舊版、內容早已過時，不再更新，要不要刪由你決定（刪檔你自己動手）。現行說明看 claude.ai 的「新功能說明」「aos-agent 用法」「工具箱與腦設定參考」三頁（網址不變，11-06 已換新路徑）
- 回信改走 `reply_to` 之後，沙箱跨帳號用 kernel 要多一格權限（10-30 晚，不急；沒用過 `setup.sh --mailbox` 就不用管）：之前照 `sudo sh proto8/cmd/aos-sandbox/root/setup.sh --mailbox <信箱> --apply` 設過的信箱，要再跑一次同一行，讓它多建 `<信箱>/reply/` 三格與權限。過關＝它印的「驗」那行 `echo '{"request":{"messages":[{"role":"user","content":"hi"}]}}' | sudo -n …s6-setuidgid aos-run env AOS_LLM_KERNEL=<信箱的上一層＝kernel 的 stack> …/aos-llm ask` 拿到回信、結束碼 0（11-04 晚 aos-llm-send 改名 aos-llm，見 setup.sh 印的「驗」那行） → [medium-plan 實作時代定 14](../proto8/thinking/2026-10/29/medium-plan/README.md#實作時代定10-29隊長與工人照原則定的細節可翻案)
- 親手試 aos-tools 與新的 aos-mcp（10-28，不急；代定清單在 [thinking 10-28 aos-tools § 結論](../proto8/thinking/2026-10/28/aos-tools/README.md#結論10-28-實作照原則代定可翻案)）：WSL 裡 `R=~/repo/aos-tools/proto8; export PATH=$R/bin:$R/impls/aos-exec/bin:$R/impls/aos-json/bin:$PATH; cd ~/code/try/aos-tools/agent && aos-tools ls`，再 `cd ../cws && claude --mcp-config ../mcp.json` 叫它用 clock／echo／add（11-02 起 aos-mcp 改收登記檔：那份 mcp.json 的 args 最後一個要從 `…/agent` 改成 `…/agent/tools.json`；它寫死用 `~/repo/aos-tools` 那份 clone，那份沒 pull 新版前照舊能跑）
- 腦的工具呼叫做完後要你看的兩題（都不擋、已照推薦做）：agent 當腦的工具時題目怎麼交（範本只定 stdin 進 stdout 出；10-24 agent-eve 叫 pyfix 照這條做出一個實例〔兩者都不在了：agent-eve 11-04 刪、pyfix 11-06 封存〕：轉接寫在工具自己的 `_entry`、`tool.json` 不加 `input`，見 [thinking 10-24 agent-as-tool](../proto8/thinking/2026-10/24/agent-as-tool.md)；那份另有選項要你看：記憶、子 agent 換強模型；「失敗回給腦」「轉接共用一支」10-24 下午照推薦做了，真跑排在 [真腦實測交接](session_logs/2026-10/2026-10-24-真腦實測/README.md)）、對話太長（10-24 有一個可用做法：agent-kai 按意圖組 context，見 [thinking 10-24 intent-context](../proto8/thinking/2026-10/24/intent-context/README.md)） → [thinking 10-23 tool-calls](../proto8/thinking/2026-10/23/tool-calls/README.md) 文末
- 要 root 跑一次沙箱的身分層（10-24，[thinking](../proto8/thinking/2026-10/24/sandbox/README.md)）：先 `sh proto8/cmd/aos-sandbox/root/setup.sh` 乾跑看要做什麼，沒問題再 `sudo sh proto8/cmd/aos-sandbox/root/setup.sh --apply`（s6 四支進 /usr/local/bin、建系統帳號 aos-run、開 /srv/aos-run、sudoers 只准換成 aos-run）；驗：`sudo -n /usr/local/bin/s6-setuidgid aos-run id`；要讓 aos-run 用某個 kernel 信箱再跑 `sudo sh proto8/cmd/aos-sandbox/root/setup.sh --mailbox /srv/aos-run/mailbox --apply`，kernel 開著時 `echo '{"request":{"messages":[{"role":"user","content":"hi"}]}}' | sudo -n /usr/local/bin/s6-setuidgid aos-run env AOS_LLM_KERNEL=/srv/aos-run /絕對/aos-llm ask` 拿得到回信（11-04 晚 aos-llm-send 改名 aos-llm）、`chmod 700` 信箱後同一行 `MkdirFailed`（乾跑會印這幾行）。不跑也行：bwrap 那層（看不到判準、斷網）與 s6-softlimit 上限現在就能用。
> 2026-10-12 使用者清帳：「舊帳可以清掉」「proto6 已經是老黃曆了，不管」——A 區 71 題、B 區 proto6 帳號真 root 驗收、C 區「先不決定」各項全部結案不再追。原 `wait-user/` 分類檔已封存（見 common/archive 索引），編號不回收。
