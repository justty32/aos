今天設了 `AOS_KERNEL` 時，哪些請求改寄 kernel 站、站拿到後能做什麼、沒設時走哪（讀程式＋暫存樹實測）。

← [README](README.md)｜下一份：[02-逐項地圖](02-逐項地圖.md)

## 先講結論

- **kernel 今天只攔得到兩種信**：一是起停掛拆的信（`procs_added`、`procs_removed`、`procs_stopped`、`procs_started`、`procs_slept`、`procs_woken`），二是「表在哪」的查詢信（`{"procs_state_path": true}`）。其他存取 kernel 都看不到。
- **兩種信都只有「走規矩的」才會寄來**：寄不寄給 kernel，看寄件人自己的環境有沒有 `AOS_KERNEL`。
- **查詢信攔到的只是「給我表的位置」這一句**：kernel 回一個路徑，問的人自己去讀那個檔；之後讀什麼、拿那列的 stack 去改什麼，kernel 看不到。

## 誰把信寄給 kernel（程式位置）

- 判斷走不走 kernel：`py/aos/daemon_ctl/state_path.py` 的 `via_kernel`：設了 `AOS_KERNEL`、而且這次沒明給 `--daemon` 才走。`aos-agent` 包一層在 `py/aos/apps/agent/common.py` 的 `via_kernel`／`table_ref`。
- 起停信：`py/aos/apps/agent/ctl/shared.py` 的 `ctl_wait`／`send_only` → `daemon_ctl/post.py` 的 `mailbox_of`：走 kernel＝寄 `AOS_KERNEL` 那個信箱；不走＝寄 daemon 表上的 `procs_requests`。回信箱：有 `AOS_STACK`＝`$AOS_STACK/daemon_reply/`，人的殼＝`$AOS_KERNEL/reply/`。
- 查詢信：`state_path.py` 的 `state_path`／`_ask_kernel`。等 3 秒（`--timeout-s` 可改），沒回＝`KernelFailed`，**不退回去讀 `AOS_DAEMON`**；被拒＝`KernelFailed` 帶 kernel 的代號；回的路徑必須是絕對路徑。一次執行只問一次、記在行程裡、不落檔。
- 不走 kernel 的固定例外：`aos-daemon-ctl` 一律直寄（11-07 使用者定）；`aos-agent --daemon D` 明給就直寄 D。
- daemon 那頭（`cpp/aos-daemon/src/daemon/mailbox.cpp`）收信只認 `ping`、`procs_state_path` 和上面六種名單，**沒有 pause、resume、shutdown 的信**；pause／resume 是寫對方的 `ctl.json`，shutdown 是寫 daemon 自己的 `ctl.json`。

## 站拿到信後能做什麼

站程式 `py/tools/aos/kernel/`（`round.py` 一輪、`hooks.py` 三個點、`procs_rules.py` 掛 proc 那一包）。範本有三種站：`templates/kernel/daemon-kernel/`（daemon 的身體就是站）、`procs-kernel/`（站是一列 proc；`start-api/perm/` 就是它的抄本，出廠沒掛）、agent 自己當站的 `kernel_gate` 工具。

| 能做的 | 怎麼做 | 對哪種信 |
|---|---|---|
| 放行 | 轉給下一站：`kernel.json` 的 `next` ＞ 站自己環境的 `AOS_KERNEL`（指自己就跳過）＞ `AOS_DAEMON` 表上的 `procs_requests` | 全部 |
| 拒絕 | 內建規則：`allowed`（名字白名單）、`max_running`、期限 `queue_wait_ms`；hook 退 10 | 內建規則只看 `procs_added`／`procs_started`／`procs_woken`；hook 看得到全部 |
| 改寫 | `before_verdict` 改 body；`limits`／`users` 表替 `procs_added` 填份額與身分 | 全部（limits／users 只對 add） |
| 排隊 | `queue: true` 滿格留隊 | 要一格的信 |
| 留著等人 | `after_verdict` 回 `hold`，人寫 `decisions/<信名>.json`；`kernel_gate` 就是這樣 | 全部；但 `kernel_gate` 的預設 hold 放過只問表的信 |
| 分流 | `after_verdict` 回 `next` 替這一封指定下一站 | 全部 |
| 改回信 | `reply_via_me: true` 時 `before_reply` 改代回的 body | 全部（所以能換掉查詢信回的路徑） |
| 記帳 | hook 的 `event.json` 留最後一次；要完整紀錄得自己寫 hook | — |

hook 點宣告在每個站夾的 `kernel_hooks.json`（11-21 定：宣告只是參考，程式不讀）；被勾清單在 `kernel_hookeds.json`，由 `interfaces.json` 最外層 `hookeds` 指。

## 沒設 `AOS_KERNEL` 時

全部直寄、直讀：起停信寄 daemon 的 `procs_requests`；表從 `--daemon` ＞ `AOS_DAEMON` 找（aos-agent 另有 cwd 往上兩層的退路，`common.cwd_daemon`），直接讀 `procs_state.json`；寄信前還會直讀 daemon 的 `state.json` 核它活不活（`shared.daemon_up`）。人的殼經 `env.sh` 一定是這條（它清掉所有 `AOS_*`，只留 `AOS_HOME`）。

## 誰會帶著 `AOS_KERNEL`

- 範本只有一處：`start-api/agents/ann/.env` 一行註解 `# AOS_KERNEL=${AOS_DAEMON}/procs/perm/requests`；打開後 ann 的身體與它叫的每支工具都帶著（實測：ann 行程的環境有 `AOS_KERNEL=…/.stack//procs/perm/requests`）。
- 站自己（perm）的環境沒有 `AOS_KERNEL`（實測），所以它放行的信轉給根的 ctl 信箱。
- 根的 `.env` 明寫不要在根設：llm kernel 會繼承，連它掛腦的工作都繞去站。

## 實測摘要（細節在 [06](06-實測紀錄.md)）

在 perm 站掛一個 `before_verdict` hook 把每封信記下來，再用 ann 的身分跑工具：

- `subagent add／stop／rm`：站看到 `procs_added`（含整份 exec 與 envs）、`procs_stopped`、`procs_removed`，前面各跟 2～3 封查詢信。
- `agents_ctl pause／resume llm`、`subagent say`、`self_tools`、`goal set`、`self_hook`、`self_history`、`clock_register add`、`mailbox_send`：站**只**看到查詢信（1～3 封）；pause 本身、塞進 queue、改 stack 裡的檔、寫時鐘登記都看不到。
- `self_state` 一次寄了 10 封查詢信（每支下層 `aos-agent` 各問一次）。
