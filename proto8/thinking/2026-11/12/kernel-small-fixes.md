# kernel 討論的兩件小修：daemon 壞信也回信、fork／subagent 不再自己讀 AOS_DAEMON（11-12，已施工）

← [2026-11-12](README.md)｜[thinking](../../README.md)｜前情：[11-11 kernel](../11/kernel/README.md)（裁定「改成會回」、結論 2「一律寄 `AOS_KERNEL`」）、[kernel 03 日後清單](../11/kernel/03-過時清單與日後清單.md)

## 使用者原話

頂層把 kernel 日後清單分三堆，其中「小而獨立，今天就能做」三件（① 兩個變數都沒設就報錯、不再猜 `./.stack`；② daemon 壞信也回信；③ `fork`、`subagent` 只設 `AOS_KERNEL` 時報 `DaemonMissing`）。使用者 11-12：

> kernel那邊，小而獨立的可以做，只是猜.stack感覺可以留著?。

→ 做 ②、③；**① 不做**，猜 `./.stack` 原樣留著。（同日稍後使用者在 kernel 兩題裁定答「1.留。」，kernel 03 第 4 項已標「留，不做」，見 [kernel-norms](kernel-norms.md)；這份 rebase 時照那邊的寫法，沒再加「未定案」註。）

## ② daemon 收到壞信也回信

- **哪些會回**：信封讀得懂、有 `reply_to`、**body 壞**的——body 不是物件、`ping` 不是 `true`、名單類欄位型別錯或項不合格（`check_lists`，例：`procs_removed` 給字串、名字帶 `/`）、指示詞解不開。回 `{"applied": false, "error": {"code": "BodyBad", "msg": "<原因>"}}`，形狀同判官拒信；`msg` 跟 `state_flux.json` 的 `mailbox_warning` 冒號後那段同一句（英文）。`mailbox_warning` 照舊記。
- **不回的**：沒寫 `reply_to`（沒地方回）；信封壞（`aos::post::see` 不過，讀不到 `reply_to`）——兩種都照舊只記 `mailbox_warning`。回信寄不出去照舊不管（決定 27）。
- **程式**：`impls/aos-daemon/src/daemon/mailbox.cpp`（`Letters` 改帶壞信原因、`done_letters` 好壞都交給 `aos::post::reply`，它自己判「沒 reply_to／信封壞＝不回」）、`daemon.hpp`。
- **寄件端**：
  - aos-agent ctl：本來就認 `applied: false`（判官拒信那條），daemon 的拒信一到就 `AddRejected`／`CtlRejected`、帶 `BodyBad` 與原因，rm／stop 等也不再等到逾時。沒改程式。
  - 判官轉寄：一般信原樣帶原 `reply_to` 轉，daemon 直接回原寄件人；`keep_ordered` 代回也是原樣轉 body。沒改程式。
  - **aos-daemon-ctl**（改了）：原本沒給 `--reply-to` 只看信有沒有被領走、根本收不到回信；現在帶共用回信信箱寄（同 aos-agent：`$AOS_STACK/daemon_reply/`，沒有＝`<ctl 信箱>/reply/`），領走後在 `--timeout-s` 內（至少再 1 秒）看回信，拒了＝`aos-daemon-ctl: error: BodyBad the daemon refused letter <名>: <原因>`、退 1。給了 `--reply-to` 照舊只寄不等。
- `test_daemon_down` 2 支（既有紅）跟 ② 無關：daemon 沒在跑、沒有回信可言；它們等 `DaemonMissing`，實際拿到 `DaemonFailed … letter withdrawn`（寄前的「daemon 活著沒」那關沒擋下）。

## ③ fork、subagent 不再自己讀 AOS_DAEMON

- **為什麼原本只看 `AOS_DAEMON`**：兩支開頭自己讀 `$AOS_DAEMON`、沒設就 `DaemonMissing`；daemon 路徑拿來 ① 叫 `aos-agent --daemon`（fork）、② 放分身 stack（`<daemon>/procs/<分身>/`）與帳上 stack 的相對基準（fork 的 details、subagent 的 `subagents.json`）。**寄信本來就經 aos-agent → `py/daemon_ctl` 的 `mailbox_of`，有 `AOS_KERNEL` 就寄那裡**，不是問題所在。
- **改法**：lib 不能 import `py/`（單向分層），共用的找法就是 aos-agent 自己那套（`--daemon` ＞ `$AOS_DAEMON` ＞ `./.stack`，`py/daemon_ctl/table.py` 的 `find_daemon`）。`aos-agent ctl who --json` 多回一欄 `daemon`（這次讀的是哪台的表）；fork、subagent 先 `ctl who --json`，用回來的 `daemon` 當基準（fork 之後的 aos-agent 呼叫照舊帶 `--daemon` 那台）。找不到 daemon＝aos-agent 的 `DaemonMissing` 原樣接成自己的（C-52 例外 ⑤）。環境檢查順序因此變成 `StackMissing`／`WsMissing` 先、`DaemonMissing` 後。
- **結果**：設了 `AOS_KERNEL`（不管有沒有 `AOS_DAEMON`）＝掛子、停、收的信都寄 `AOS_KERNEL`；**只設 `AOS_KERNEL`、沒有 `AOS_DAEMON`（cwd 也沒 `./.stack`）照舊 `DaemonMissing`**——因為讀表與放 stack 一定要知道那台 daemon，而「kernel 給狀態位址」那套還沒做（照昨天裁定今天不做）。錯誤說明寫清楚了（fork `--help`：`AOS_KERNEL alone is not enough`）。
- **盤點同類工具**：`do_task`（11-11 起 save／load，不碰 daemon）、`agents_ctl`、`self_*`、`goal`、`clock_register`、`mailbox_send`（`mailbox_call`）都只叫 aos-agent／aos-mailbox、自己不讀 `AOS_DAEMON`，不用改；`ctl who --json` 多一欄對它們無影響。

### 因 ③ 發現仍需要 `AOS_DAEMON`（或 `./.stack`）的地方（之後框架「先問再讀」那步的事，這次不動）

| 位置 | 用 daemon 做什麼 |
|---|---|
| `cmd/aos-agent`（`common.py` 的 `daemon_path`／`need_table`／`table`、`daemon_up`；`ctl who`／`ls`／`state`／`where`、`phase_body`） | 直接讀 daemon 的表 `procs_state.json`、state 窗核活著沒 |
| `py/daemon_ctl/post.py` 的 `reply_box` | 沒有 `$AOS_STACK` 時回信信箱放 `<ctl 信箱>/reply/` |
| `lib/agent/fork/_entry` | 分身 stack 放 `<daemon>/procs/<分身>/`、details 與失敗分身的路徑相對 daemon |
| `lib/agent/subagent/_entry` | 帳上 stack 存相對 daemon 的路徑 |
| `lib/agent/hooks.py`（clock 名字解析） | 讀 `$AOS_DAEMON/procs_state.json` 找那列的 clock（kernel 03 第 3 項本來就列了） |
| `lib/aos/promote/swap.py`（idle 判斷） | 沒給 `daemons` 時對 `$AOS_DAEMON` 跑 `aos-daemon-ctl ls --json` |
| `templates/agent-fsm/wait.py` | 相對的 `$AOS_LLM_KERNEL` 從 `$AOS_DAEMON` 算（路徑基準，不是請求） |
| `lib/aos/judge/_entry` | 下一站＝`$AOS_DAEMON` 的 ctl 信箱、數 running 讀它的表（判官本身是 kernel，kernel 03 第 1 項） |
| `py/aos_sweep_proc.py` | 清道夫認行程身分比對 `/proc/<pid>/environ` 的 `AOS_DAEMON` |

## 代定（可翻案）

1. 拒信代號一律 `BodyBad`（照判官 body 壞的代號），不按原因細分。
2. aos-daemon-ctl 沒給 `--reply-to` 時改成讀回信：只在被領走之後多看最多 1 秒（期限內）；套了或沒等到回信都照舊退 0，拒了退 1。
3. ③ 的共用找法＝aos-agent 那套（`ctl who --json` 加 `daemon` 欄），不另寫一份給 lib；fork 的 who 從自己的 cwd 找 `./.stack`、subagent 從 `$AOS_WS`（各自原本叫 aos-agent 的 cwd，沒去統一）。
4. 條文 N-28 第 51 行「壞信…不回信」、附錄 4 `on_bad` 跟 ② 不符，照指示不改條文，只在 kernel 03 第 2 項記一句。

## 驗證

- 新測試：`impls/aos-daemon/tests/test_bad_letter.py`（三種壞 body 都回 `BodyBad`、好信 `applied: true`；沒 `reply_to` 與信封壞不回、daemon 照跑；aos-daemon-ctl `add --name a/b`＝`BodyBad`）——換回舊 daemon 跑會紅（3 處失敗）。fork、subagent 各加「只設 `AOS_KERNEL`＝`DaemonMissing`、kernel 信箱沒收到信」；subagent 真 daemon 加「兩個都設＝掛子信寄到 `AOS_KERNEL`」。
- 假腦整棵（`/tmp/line-kernel-e2e`，`/tmp/line-kernel-e2e.py`）：daemon 的身體是判官、`AOS_KERNEL`＝它的 `requests/`，llm kernel＋`llm_fake`：壞 body 經判官轉寄、daemon 回 `BodyBad` 給原寄件人；aos-daemon-ctl `BodyBad`；判官只許 `pat` 時 pat 叫 fork＝`AddRejected … NameUnknown f-pat-…`（證明 fork 的掛信走了 `AOS_KERNEL`）；放開後 sam 叫 fork 拿回暗號、分身收掉。8/8 過。
- 順帶看到（既有設計、沒改）：aos-llm-kernel 掛腦行程的信也寄 `AOS_KERNEL`；搭樹時 llm kernel 若繼承了給一般 proc 的那個 `AOS_KERNEL`，腦行程名字（`llm_…`）會被那台判官的白名單擋——e2e 第一次就卡在這，llm kernel 不給 `AOS_KERNEL` 後就過。
