# WAIT_USER — 等待使用者的事

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

需要**使用者親自做 / 驗證 / 拍板**才能繼續的事——例如：實機/實環境測試、外部服務登入、環境變數設定、權限操作、需要帳號的下載、**催/開/fork 另一個 agent 處理急件**（見 [inbox](workflows/inbox/README.md)：寄了信但很急、對方可能沒開）。Claude 能做結構性驗證＋打包到極限；跨不過去的那一關記這裡等使用者。

**設計裁決也算**——照 [AGENTS 鐵律 5](../AGENTS.md)「大方向是使用者的」，需要你一句話才動得了工的，
對我來說跟「沒有帳號密碼」是同一種卡住。**本檔只留一行 ＋ 連結**，脈絡在各自的原始文件裡，不在這裡重講。

**只列還沒做的**——做完即移除（不留已完成清單，歷史看 git log）。

> **膨脹就拆**：待使用者項堆多了，就開 **`wait-user/`** 資料夾按類別拆檔，本檔退回只留一張 `| 類別 | open | 清單 |` 導航表（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

## 待使用者項

- 親手試 procs 與 ctl 指令（11-03 實作，[procs 步驟 12](../proto8/thinking/2026-11-03-procs.md#實作步驟表不實作給隊長)、[ctl-commands](../proto8/thinking/2026-11-03-ctl-commands.md)）：試驗場重建時 `daemons/main/daemon.json` 用 `procs`（字串＝跑一次、要一直跑的寫 loop 的 key 如 `interval_ms`）、`"procs_ctl_mailbox": "procs_ctl_mailbox"`；`ls` 沒有種類欄（常駐 bob 11-03 晚使用者「封存吧」，不用再改）；舊的 `<D>/loops/<名>/` eca 小格要搬到 `procs/<名>/` 或 `aos-eca add --stack <舊小格>` 重掛（先寫 `{"cmd": "stop"}` 讓舊 daemon 收工）。試：`add --stack /tmp/x --name c ../agents/clock`、`where --stack c`、`stop c`（`ls` 是 stopped、`/tmp/x/ctl.json` 是 `{"cmd": "stop", …}`）、`kill -9` daemon 再起它沒被起、`start c`、`pause c`／`resume c`、對 exec 型做 `stop`＝`CtlMissing`；**注意**：eca 自己出錯結束的現在會從 daemon 表與 `aos-eca ls` 消失（要用就同名再 add），見 procs「實作時代定」
- 親手試 daemon 的新窗與 log（11-02，state 窗那輪；拷貝裡頂層實跑過）：`cd ~/code/playground && source env.sh && cd ws`，視窗一 `aos-exec ../daemons/main`（`_entry.json` 已帶 `--enable-logs`，log 直接印在這）；視窗二（`env.sh` 已設好 `AOS_DAEMON_STACK`）`watch -n1 ls -l --time-style=full-iso $AOS_DAEMON_STACK/`：睡著時 `state.json`、`procs_state.json` 的時間不動，`aos-daemon-ctl add ../agents/bob -- "題"` 後 procs_state 動一次、bob 做完就從 `aos-daemon-ctl ls` 消失、同名可直接再 add；步驟照試驗場 `~/code/playground/README.md` 第 1、3 節（11-03 照 procs 重建）。代定與要你看的通則差異 → [state 窗 § 實作結論](../proto8/thinking/2026-11-02-state-window.md#實作結論11-02)
- 公司那台 WSL 的 aos clone 下次 pull 會撞歷史（11-01 晚使用者要求把 thinking 裡幾句情緒話連 git 歷史一起抹掉，main 自 80786461 之後五個 commit 改寫、強制推上 origin）：回公司時在那份 clone 裡 `git fetch origin && git reset --hard origin/main`（先確認沒有未 commit 的本機改動）即可 → [02 § 使用者裁定](../proto8/thinking/2026-11-01-playground-bob/02-環境變數要使用者裁的問題.md)
- 公司那台（WSL／Windows）桌面的六份說明頁 HTML 還是舊版（10-31 早六份 artifact 已照 10-30 晚改動回寫、11-01 又照 parts 瘦身回寫，都同網址）：回公司時從各網址重存一次即可，網址見 [HANDOFF](HANDOFF.md) 第 4 點 → [10-31 校對表](session_logs/2026-10/2026-10-31-artifact-回寫.md)、[11-01 校對表](session_logs/2026-11/2026-11-01-artifact-回寫.md)
- 回信改走 `reply_to` 之後，沙箱跨帳號用 kernel 要多一格權限（10-30 晚，不急；沒用過 `setup.sh --mailbox` 就不用管）：之前照 `sudo sh proto8/extras/sandbox/root/setup.sh --mailbox <信箱> --apply` 設過的信箱，要再跑一次同一行，讓它多建 `<信箱>/reply/` 三格與權限。過關＝它印的「驗」那行 `sudo -n …s6-setuidgid aos-run env AOS_KERNEL=<信箱> …/aos-llm-send 單子.json` 拿到回信、結束碼 0 → [medium-plan 實作時代定 14](../proto8/thinking/2026-10-29-medium-plan.md#實作時代定10-29隊長與工人照原則定的細節可翻案)
- 親手試 aos-tools 與新的 aos-mcp（10-28，不急；代定清單在 [thinking 10-28 aos-tools § 結論](../proto8/thinking/2026-10-28-aos-tools.md#結論10-28-實作照原則代定可翻案)）：WSL 裡 `R=~/repo/aos-tools/proto8; export PATH=$R/bin:$R/impls/aos-exec/bin:$R/impls/aos-json/bin:$PATH; cd ~/code/try/aos-tools/agent && aos-tools ls`，再 `cd ../cws && claude --mcp-config ../mcp.json` 叫它用 clock／echo／add（11-02 起 aos-mcp 改收登記檔：那份 mcp.json 的 args 最後一個要從 `…/agent` 改成 `…/agent/tools.json`；它寫死用 `~/repo/aos-tools` 那份 clone，那份沒 pull 新版前照舊能跑）
- 腦的工具呼叫做完後要你看的兩題（都不擋、已照推薦做）：agent 當腦的工具時題目怎麼交（範本只定 stdin 進 stdout 出；10-24 agent-eve 叫 pyfix 照這條做出一個實例：轉接寫在工具自己的 `_entry`、`tool.json` 不加 `input`，見 [thinking 10-24 agent-as-tool](../proto8/thinking/2026-10-24-agent-as-tool.md)；那份另有選項要你看：記憶、子 agent 換強模型；「失敗回給腦」「轉接共用一支」10-24 下午照推薦做了，真跑排在 [真腦實測交接](session_logs/2026-10/2026-10-24-真腦實測/README.md)）、對話太長（10-24 有一個可用做法：agent-kai 按意圖組 context，見 [thinking 10-24 intent-context](../proto8/thinking/2026-10-24-intent-context.md)） → [thinking 10-23 tool-calls](../proto8/thinking/2026-10-23-tool-calls.md) 文末
- 要 root 跑一次沙箱的身分層（10-24，[thinking](../proto8/thinking/2026-10-24-sandbox.md)）：先 `sh proto8/extras/sandbox/root/setup.sh` 乾跑看要做什麼，沒問題再 `sudo sh proto8/extras/sandbox/root/setup.sh --apply`（s6 四支進 /usr/local/bin、建系統帳號 aos-run、開 /srv/aos-run、sudoers 只准換成 aos-run）；驗：`sudo -n /usr/local/bin/s6-setuidgid aos-run id`；要讓 aos-run 用某個 kernel 信箱再跑 `sudo sh proto8/extras/sandbox/root/setup.sh --mailbox /srv/aos-run/mailbox --apply`，kernel 開著時 `sudo -n /usr/local/bin/s6-setuidgid aos-run env AOS_KERNEL=/srv/aos-run/mailbox /絕對/aos-llm-send 單子.json` 拿得到回信、`chmod 700` 信箱後同一行 `MkdirFailed`（乾跑會印這幾行）。不跑也行：bwrap 那層（看不到判準、斷網）與 s6-softlimit 上限現在就能用。
> 2026-10-12 使用者清帳：「舊帳可以清掉」「proto6 已經是老黃曆了，不管」——A 區 71 題、B 區 proto6 帳號真 root 驗收、C 區「先不決定」各項全部結案不再追。原 `wait-user/` 分類檔已封存（見 common/archive 索引），編號不回收。
