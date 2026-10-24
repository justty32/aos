# WAIT_USER — 等待使用者的事

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

需要**使用者親自做 / 驗證 / 拍板**才能繼續的事——例如：實機/實環境測試、外部服務登入、環境變數設定、權限操作、需要帳號的下載、**催/開/fork 另一個 agent 處理急件**（見 [inbox](workflows/inbox/README.md)：寄了信但很急、對方可能沒開）。Claude 能做結構性驗證＋打包到極限；跨不過去的那一關記這裡等使用者。

**設計裁決也算**——照 [AGENTS 鐵律 5](../AGENTS.md)「大方向是使用者的」，需要你一句話才動得了工的，
對我來說跟「沒有帳號密碼」是同一種卡住。**本檔只留一行 ＋ 連結**，脈絡在各自的原始文件裡，不在這裡重講。

**只列還沒做的**——做完即移除（不留已完成清單，歷史看 git log）。

> **膨脹就拆**：待使用者項堆多了，就開 **`wait-user/`** 資料夾按類別拆檔，本檔退回只留一張 `| 類別 | open | 清單 |` 導航表（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

## 待使用者項

- 還沒確認的：tasks、通用 kernel 兩個方向題 → [plan § 1.2](../proto8/thinking/2026-10-21-plan.md)（LLM kernel 那題 10-24 使用者定了要做、第一版已做，[thinking](../proto8/thinking/2026-10-24-llm-kernel.md)；它的 token 回報照推薦開 `AOS_KERNEL_REPORT`，排在 SESSION-LOG）
- 腦的工具呼叫做完後要你看的兩題（都不擋、已照推薦做）：agent 當腦的工具時題目怎麼交（範本只定 stdin 進 stdout 出；10-24 agent-eve 叫 pyfix 照這條做出一個實例：轉接寫在工具自己的 `_entry`、`tool.json` 不加 `input`，見 [thinking 10-24 agent-as-tool](../proto8/thinking/2026-10-24-agent-as-tool.md)；那份另有選項要你看：記憶、子 agent 換強模型；「失敗回給腦」「轉接共用一支」10-24 下午照推薦做了，真跑排在 [真腦實測交接](session_logs/2026-10/2026-10-24-真腦實測/README.md)）、對話太長（10-24 有一個可用做法：agent-kai 按意圖組 context，見 [thinking 10-24 intent-context](../proto8/thinking/2026-10-24-intent-context.md)） → [thinking 10-23 tool-calls](../proto8/thinking/2026-10-23-tool-calls.md) 文末
- 親手試給人用的 say／listen（LiteLLM 開著時，[human/README](../proto8/human/README.md)「怎麼用」）：① `R=~/repo/simple_tools/aos/proto8; export PATH=$R/impls/aos-exec/bin:$R/impls/aos-loop/bin:$R/impls/aos-fsm/bin:$R/human/bin:$PATH` ② `cd ~/code/try/say-listen/ws; export AOS_BRAIN_URL=http://localhost:4000/v1` ③ `aos-chat --trace $R/demo/agent-dan`，打兩三句、`/status`、Ctrl-D ④ 分開試：`N=$(aos-say 17乘23是多少)`、`aos-exec --ws . $R/demo/agent-dan`、`aos-listen "$N"`、`aos-listen --last 3`——看順不順手（10-24 只用假腦跑過，[thinking](../proto8/thinking/2026-10-24-say-listen.md)）
- 親手試 claude／codex 當工具、人接進去（[thinking](../proto8/thinking/2026-10-24-cli-tools.md)、[demo README](../proto8/demo/README.md) agent-fay 一節）：① `cd ~/code/try/cli-tools && . ./env.sh && cd ws`（env.sh 放 PATH、拿掉 Claude Code 的環境變數）② `$FAY/attach` 看兩個工具的狀態 ③ `$FAY/attach claude` 進 Claude Code 畫面（會接上 agent 問過的那段），打一句話，按 **Ctrl-\\** 跳出 ④ 跳出後讓 agent 叫它：`printf '再問一題\n' > new/q2.txt && aos-exec "$FAY"`（畫面開著就從畫面送字，`cat out/q2.txt` 看回答；LiteLLM 開著可加 `AOS_BRAIN_URL=http://localhost:4000/v1` 用真腦）⑤ `$FAY/attach codex` 同樣試一次 ⑥ 在畫面裡 `/exit`（claude）或 `/quit`（codex）關掉——看跳出鍵、權限（目前唯讀）順不順手
- 親手在 nvim 試 Lua 寫 aos 與 aos 外掛（[thinking](../proto8/thinking/2026-10-24-lua-nvim.md)、[editors/nvim/README](../proto8/editors/nvim/README.md)）：① `cd ~/code/try/lua-aos && python3 try.py`（編出 build/、假腦跑一遍）② `AOS_WS=$PWD/ws-nvim nvim --clean -u ~/repo/simple_tools/aos/proto8/editors/nvim/init_min.lua build/agent_dan/fsm.json`（不碰你的 LazyVim）③ 裡面打 `:AosSay! 17*23 是多少？`、`:AosTrace`、游標在 `"idle"` 上按 `,ag`、開 `proto8/langs/lua/examples/agent_dan.lua` 按 `,ap` ④ 喜歡就照 README 加一個 `lua/plugins/aos.lua`；LiteLLM 開著時先 `export AOS_BRAIN_URL=http://localhost:4000/v1` 就是真腦
- 要 root 跑一次沙箱的身分層（10-24，[thinking](../proto8/thinking/2026-10-24-sandbox.md)）：先 `sh proto8/sandbox/root/setup.sh` 乾跑看要做什麼，沒問題再 `sudo sh proto8/sandbox/root/setup.sh --apply`（s6 四支進 /usr/local/bin、建系統帳號 aos-run、開 /srv/aos-run、sudoers 只准換成 aos-run）；驗：`sudo -n /usr/local/bin/s6-setuidgid aos-run id`。不跑也行：bwrap 那層（看不到判準、斷網）與 s6-softlimit 上限現在就能用。
> 2026-10-12 使用者清帳：「舊帳可以清掉」「proto6 已經是老黃曆了，不管」——A 區 71 題、B 區 proto6 帳號真 root 驗收、C 區「先不決定」各項全部結案不再追。原 `wait-user/` 分類檔已封存（見 common/archive 索引），編號不回收。
