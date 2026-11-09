← [回入口 附錄3-舊名對照.md](../附錄3-舊名對照.md)｜段落：舊名 → 現名（續）：JSON 的 key；10-25 計數、時間點、上限

### JSON 的 key

| 舊名 | 現名 | 何時與出處 |
|---|---|---|
| 「要跑什麼」：loop／daemon 的 `run`（10-23 統合一度改 `val`、10-23 晚改回）；fsm 格的 `val` | `exec`（`val` 只留給 C-55 的雙形） | 10-23 晚、深夜（原話在[命名](../命名.md)） |
| `children`（10-23 `loops`）、`execs`（10-30）；小格 `loops/<名字>/`；子項的 `kind` | `procs`；`procs/<名字>/`；`kind` 拿掉（看寫法決定怎麼起） | 10-23；11-03 [procs](../../../thinking/2026-11/03/procs/README.md)，使用者「連名單也合一」「2.kind這東西沒用吧，刪掉」（N-28） |
| `loops_ctl`／`loops_state`；`loops_mailbox`（11-02 晚 `loops_ctl_mailbox`）；ctl 的 `loops_added`／`loops_removed`、`execs_added`／`execs_removed` | `procs_ctl`／`procs_state`；`procs_ctl_mailbox`；`procs_added`／`procs_removed` | 11-02 晚使用者「loops_mailbox改名為loops_ctl_mailbox」；11-03 procs（N-28、N-54） |
| loop 的 ctl 兩個布林 `paused`／`stopped` | 一道指令 `cmd`＝`pause`／`resume`／`stop` | 11-03，[ctl-commands](../../../thinking/2026-11/03/ctl-commands/README.md)（N-06、N-07） |
| state 窗的 `state` 欄；子項 `exited` | `phase`；`done`／`stopped` | 10-23（N-17、N-32） |
| ctl 的 `stop`；state 窗的 `last_warning`；`start_ticks` | `cmd`＝`stop`（10-23 晚曾叫 `stopped`，11-03 改成指令，見上）；`ctl_warning`；`started_at_ticks` | 10-23 晚，[naming-method](../../../thinking/2026-10/23/naming-method/README.md)，使用者「寫進去吧」 |
| state 的 `lap`（10-23 `beats`、10-23 晚 `runs`）；11-09 前 state 的 `counter_runs` | `counter_runs`；11-09 起搬出 state、開 `--enable-counters` 才寫 `counter_runs.txt` | 10-23、10-25（原話在[命名](../命名.md)）；11-09 [clock-and-hot-writes](../../../thinking/2026-11/09/clock-and-hot-writes/README.md)（N-09 的 11-09 補） |
| loop／daemon state.json 的 `at`（10-25 `recorded_at`）；`kind` | 拿掉；時間欄改成最後一欄 `updated_at` | 10-25 使用者「state.json中，runs改counter，at改成recorded_at」；11-02 [state-window](../../../thinking/2026-11/02/state-window/01-使用者原文-11-02-逐字.md#決定11-02使用者)，使用者「kind沒人在用，那就拿掉」、方向題 3「收掉」（N-09、N-32） |
| `letter_warning`（aos agent 的 `letter_warning.txt`） | `mailbox_warning`（`mailbox_warning.txt`） | 11-02 晚，使用者「letter_warning改成mailbox_warning」（N-16、N-28） |
| loop／daemon `state.json` 的 `responded_at`、`ctl_seq`、`ctl_warning`；daemon `procs_state.json` 的 `responded_at`、`mailbox_warning` | 搬到同資料夾 `state_flux.json` 的 `responded_at`、`ctl_seq`、`ctl_warning`、`mailbox_warning`（名字不變；`responded_at` 只放這一處） | 11-09，使用者裁 state_flux，[clock-and-hot-writes 05](../../../thinking/2026-11/09/clock-and-hot-writes/05-state拆分規劃.md)（N-09、N-32、N-33） |
| daemon `procs_state.json` 的 `ctl_seq`（`procs_ctl.json` 的回音）、`ctl_warning`（壞 `procs_ctl`） | `state_flux.json` 的 `procs_ctl_seq`、`procs_ctl_warning` | 11-09，同上（N-28、N-54） |
| 指示詞位置的修飾詞 `$at` | 拿掉，位置只認 `檔#/指標` | 10-23（N-45） |
| trace 的 `ms`、`at` | `elapsed_ms`、`started_at`；trace.jsonl 11-03 整個拿掉（[trace](../../../thinking/2026-11/03/trace.md)） | 10-23、10-25 |
| `interfaces.json` 的 `"llm": "llm"`（指子介面入口資料夾 `llm/`） | `"llm": "llm.json"`（定義裡的腦設定檔，跟 `"tools": "tools.json"` 同形；值不是檔＝`LlmBad`） | 11-04 晚，[think-as-function](../../../thinking/2026-11/04/think-as-function/README.md)（P-43（續）） |
| aos-llm-kernel：kernel.json `accept`；信頂層的 `inst`／`env`／`priority`；排序依據 `_metainfo.time_ms`／`llm_tokens` | 拿掉（信裡沒單子）；信 body `{"endpoint"?, "request", "priority"?}`（舊信＝`LetterBad`）；kernel.json 新鍵 `exec`、`endpoints`、`endpoint`、`timeout_ms` | 11-04 晚，[think-as-function](../../../thinking/2026-11/04/think-as-function/README.md)（N-42 (1)、N-16） |
| daemon.json 的 `tick`（`true` 或 `{file, interval_ms, name}`）；`*_ticks`（`timeout_ticks`、`stuck_after_ticks`、`lease_ticks`、`acquired_at_ticks`、`seen_at_ticks`、`aging_ticks`…） | `clock`（形狀不變）；`*_cycles`（`timeout_cycles`、`stuck_after_cycles`…；Linux 的 `started_at_ticks` 不改） | 11-09，[clock-and-hot-writes](../../../thinking/2026-11/09/clock-and-hot-writes/README.md)，使用者裁時鐘叫 clock、單位叫 cycle（N-28、N-65） |

### 10-25 計數、時間點、上限（規則與原話在[命名](../命名.md)）

| 舊名 | 現名 |
|---|---|
| aos-llm-kernel：queue.json `runs`（11-09 前 queue.json 的 `counter_runs`）；used.json `calls`／`tokens`／`all_calls`／`all_tokens`；served.jsonl `tokens`／`waited_runs`、`at`（served.jsonl 11-05 整個不寫了；11-06 排隊帳改為 queue.json 的 `seen_at_ms`／選填 `seen_at_cycles`，aging 用 `aging_cycles`，見 [現行用法](../../../impls/aos-llm-kernel/docs/01-用法.md)）；kernel.json `budget.calls`／`budget.tokens` | `counter_runs`（11-09 起搬出 queue.json、開 `--enable-counters` 才寫 `$AOS_STACK/counter_kernel_runs.txt`）；`counter_calls`／`counter_tokens`／`counter_all_calls`／`counter_all_tokens`；`counter_tokens`／`counter_waited_runs`、`served_at`；`max_calls`／`max_tokens`（舊名＝`CfgBad`） |
| 信（send_message，已封存）的 `at`、`hops`；claude／codex 互動畫面 turns.jsonl 的 `at` | `sent_at`、`counter_hops`（現行信封沒有這欄）；`answered_at` |
| lib 工具輸出的計數（ls、stat、view、json_read、json_edit、copy）；參數 `limit` | `counter_*`；`max_lines`（read）／`max_items`（ls）／`max_results`（memory，已封存） |
