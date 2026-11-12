← [回入口 README.md](../README.md)｜段落：kernel 的三個範例擺法與判官範本 daemon-judge、procs-kernel｜上一份：[01-llm-kernel](01-llm-kernel.md)｜下一份：[03-feat-proto](03-feat-proto.md)

## kernel 的三個範例擺法：daemon 本身、daemon-judge、procs-kernel

使用者 11-05：「daemon是硬體……kernel和daemon，兩者其實可以合一，就是說，daemon他收請求，按照請求去掛proc到自己身上」「能包盡量包啦」；11-11：「我覺得kernel定義要改一下，回歸初始，變成"資源管理+排程"。」（[CONCEPTS C-47](../../docs/CONCEPTS/04-kernel.md)、[thinking 11-11 kernel](../../thinking/2026-11/11/kernel/README.md)）。擺法的設計：[thinking 11-05 kernel-daemon 02 兩種模式](../../thinking/2026-11/05/kernel-daemon/02-兩種模式.md)、[02/01「唯一」與 AOS_KERNEL](../../thinking/2026-11/05/kernel-daemon/02-兩種模式/01-唯一-AOS_KERNEL-命名.md)。

**一句話：請求寄到哪，那裡對寄件人就是 kernel**（資源管理＋排程；要不要處理、什麼時候執行由收件那邊說了算，啥都不管也是一種管理）。一般 proc 只寄 `$AOS_KERNEL`、不管背後信會去哪；收件的 proc 不必知道自己是 kernel。下面三個是現有的**範例擺法**，不是只有這三種——自己寫一個收請求、決定要不要轉的 proc 也算 kernel（怎麼寫見下面「改成自己的」）。三個擺法裡，掛 proc 最後都是一封 `procs_added` 信進 daemon 的 ctl 信箱（`procs_requests/`），差別只在「寄進 ctl 信箱之前有沒有人先看一眼」。看一眼的那支程式是同一支：[`lib/aos/judge`](../../lib/aos/judge/_entry)（判官），用法與代號寫在它 `_entry` 開頭；判官以後收進通用 kernel 框架（方向已定、未實作，[N-42 (2)](../../docs/NORMS/09-kernel.md)）。

`daemon-judge` 範本出廠帶 `--enable-logs`、不帶鐘列（鐘只放在根，聽外層的 `AOS_CLOCK`），鐘列不佔格。**`max_running` 數的是這台表上所有 running 的列**，範本帶的清道夫 `_sweeper` 也佔一格，所以預設 5＝4 隻工作 proc（agent）＋清道夫；不掛清道夫的（從 daemon.json 刪掉那列）自己把 `judge.json` 的 `max_running` 調回 4。`max_running` 是可選的：寫非負整數＝上限，寫 `null` 或不寫＝不限（使用者 11-10「上限應該是可選的，默認的值就隨意，改5吧。」）。自己加了鐘列的話，它也是普通 running proc、會算進 `max_running`，同樣再加一。

### 三個範例擺法

| 擺法 | 像什麼 | 要掛 proc 寄到哪（`AOS_KERNEL`） | 範本 |
|---|---|---|---|
| 0：daemon 本身 | 來者不拒的門房：信進來就照辦 | daemon 的 ctl 信箱（沒設 `AOS_KERNEL` 就是這個） | 任何一台 daemon |
| 1：繼承式 | daemon 自己的身體當判官：判過了才「呼叫 base」（＝轉寄進自己的 ctl 信箱） | `<daemon 的 stack>/requests` | [`kernel/daemon-judge/`](../daemon-judge) |
| 2：0 號 proc 式 | daemon 底下一個專門收請求的 proc（像 Linux 的 0 號），判過了替你寄進 daemon 的 ctl 信箱 | `<0 號 proc 的 stack>/requests` | [`kernel/procs-kernel/`](../procs-kernel) |

- **判官怎麼判**（政策檔 `judge.json`，放在定義裡）：`allowed`＝名字的白名單（`null` 或沒寫＝不限）；`max_running`＝同時最多幾個 running（數 daemon 表上 `running` 的列，`null` 或沒寫＝不限）。判 `procs_added`；`procs_started`、`procs_woken`（start／wake 讓停著、睡著的回來跑）不看 `allowed`、但照樣算進 `max_running`（edge-agent：不算的話 sleep 一隻、add 一隻、再 wake 就超過）；`procs_removed`、`procs_stopped`、`procs_slept` 照原樣轉。`{"ping": true}`（`aos-daemon-ctl ping`，[no-pid](../../thinking/2026-11/05/no-pid/README.md) P3）不判、帶原 `reply_to` 原樣轉寄，daemon 直接回給寄件人；判官不在＝沒人轉＝寄件人逾時，正好是它該知道的。不掛的每封都在判官的 stderr 印一行提醒 `judge: warning: letter <名> refused: 代號 …`（跟回信的 `code`、`msg` 同一句、英文；拒信是判官的答案、不是它的錯，照樣退 0）。
- **排隊選項**：`judge.json` 的 `queue` 預設 `false`（沒寫也一樣），格滿立刻 `SlotMissing`；寫 `true` 才把要格的 add／start／wake 留在 `requests/cur/`，**先來先掛（FIFO）**，不看 priority。stop／rm／sleep／ping 照樣立即轉寄，能騰出格的信不會被隊首擋住。排隊不算 running；整台 daemon 的總額只由判官 `max_running` 管（含 `_clock` 與模式 2 的判官自己），`subagents.json` 的 `max_subagents` 只管 subagent 自己生的子 agent，agents_ctl／直接 ctl 不受它限制。程式預設關；`daemon-judge/judge.json` 範本開 `queue: true`。（使用者裁定 sol 審查 #1）
- **排隊窗與期限**：`$AOS_STACK/queue.json` 是先來先掛的公開進度窗：`{"queued": [{"letter", "names", "queued_at", "queued_at_cycles"?, "expires_at"?}]}`，陣列順序就是順位（已在隊的保持原順位；同一輪新進的照 aos-post 處理順序：有序信先、再照信名，跟不開排隊時一樣，sol 審查 #2）；有 `AOS_CLOCK` 才記 `queued_at_cycles`。窗讀不懂（搬家、人手改壞）＝判官印一行 `judge: warning:`、當空窗，從 `requests/cur/` 照處理順序重排，不整輪退 1（sol 審查 #5）。信 body 的選填 `queue_wait_ms` 必須是非負整數，`0`＝不排、沒格就拒；正值從信封 `sent_at` 起按牆鐘算 `expires_at`，不是從判官首次看到信起算。到期不轉、回 `SlotMissing` 並收信；睡醒後連從未看過、已過期的信也拒，不能補掛。即使 `queue: false`，也先拒絕已過期的帶期限信，不會因關閉排隊而補掛。沒有期限就一直排；凍住時信與窗留在樹裡，醒來繼續。**期限維持牆鐘；凍住期間牆鐘照走，醒來第一輪已過期的排隊信一起拒絕；要跨凍住排隊，用 `--on-queued ok`。**（使用者裁定 sol 審查 #6）`--on-queued ok` 不帶期限，表示信可能永遠排著。（使用者裁定 sol 審查 #4）一封請求只有最後一封回信，排隊中不另回 queued 信。
- **判「掛」與有序選項**：`judge.json` 的 `keep_ordered` 選填布林，沒寫或 `null` 都是 `false`（使用者裁定 sol 審查 #3），其餘非布林值報 `CfgBad`；關時有序信用 `name.split('.', 1)[1]` 的尾名當一般信轉寄，保留原 `reply_to`，防重看 ctl 信箱 `new/` 的尾名；**經判官不保有序，daemon 回信的 `in_reply_to` 是尾名，要對上請寄一般信**。（代定、可翻案；晚審裁定 5 選推薦「維持現況、標成落實代定」：目前只有人手寄有序信才會撞到，[晚審 04](../../../wf/workflows/refactor/reports/2026-11-07-晚審/04-要使用者裁定.md)）開時用 `--ordered` 轉寄，有原 `reply_to` 才改指 `$AOS_STACK/judge_replies/`，將 stdout 新名記進 `$AOS_STACK/judge_ordered.json`：`{新名: {"letter": 原名, "reply_to": 原回信箱絕對路徑或 null}}`，暫存檔 rename 寫入；防重查表內 `letter` 原名。（代定、可翻案）每輪先領回信，以 `in_reply_to` 查表，用原名代回原回信箱；成功才刪列、收信，查無對照則 warning 並收信；原信無 `reply_to` 不帶回信箱、不記表。（代定、可翻案）一般信原樣轉寄，daemon 套完直接回 `{"applied": true}` 給原寄件人；判官只判斷、轉寄與代回，不自己跑任何東西。（代定、可翻案）
- **判「不掛」**：判官回 `{"applied": false, "error": {"code": "…", "msg": "…"}}` 給原寄件人。代號：`NameUnknown`（不在白名單）、`SlotMissing`（running 滿了）、`BodyBad`（body 或 `procs_added` 不是物件）、`ForwardFailed`（轉不進 ctl 信箱）。信沒 `reply_to`＝只收掉、只有 stderr 那行。
- **`aos-daemon-ctl --reply-to BOX`／`aos-agent ctl`**（[edge-agent 題 2](../../thinking/2026-11/05/edge-agent/README.md)，使用者選「加 --reply-to 等回信」）：`aos-daemon-ctl` 的寄信子命令收 `--reply-to`（它一律直寄 daemon、不經判官，回信只會是 daemon 的）；`aos-agent ctl add` 等每封都帶共用回信信箱（`$AOS_STACK/daemon_reply/`，人殼＝`<daemon stack>/procs_requests/reply/`），判官不掛＝立刻 `AddRejected`（start／wake 被 `max_running` 擋＝`CtlRejected`）＋判官的代號與原因，不用等滿 `--timeout-s`（預設 30 秒）（[aos-agent README「等回信」](../../cmd/aos-agent/README.md)）。
- **模式 1 vs 2**：模式 1 的判官跑在 daemon 那一圈裡（阻塞），要快；要慢慢判（例：之後要問腦才能判）就用模式 2。模式 2 的 0 號自己也是表上一列 `running`，`max_running` 要把它算進去（範本寫 2）。

### `AOS_KERNEL`＝一般 proc 寄請求的地方

- 值＝一般 proc 送 syscall 請求的信箱資料夾（C-47「一律寄 `AOS_KERNEL`」）；現在收的是 `procs_*` 信，形狀跟 daemon 的 ctl 信箱一模一樣，所以 daemon 的 ctl 信箱本身就是最基礎的那個（模式 0）。
- **沒設＝kernel 就是 daemon**：寄到 `$AOS_DAEMON` 的 ctl 信箱（不報錯）。`AOS_DAEMON` 也沒設時，再找 cwd 的 `./.stack`，也不是資料夾才 `DaemonMissing`（[N-63「`AOS_DAEMON` 沒設＝找 cwd 的 `./.stack`」](../../docs/NORMS/10-基礎設施-定義與工作區/07-hub-型環境變數與父子交代/02-N-63-實例-AOS_DAEMON與沒有AOS_HUB.md)）。
- **有設**：`aos-agent ctl` 的 `procs_*` 信改寄到 `$AOS_KERNEL`（**`aos-daemon-ctl` 不看它、一律直寄 daemon**：使用者 11-07 選項框「aos-daemon-ctl 永遠直寄」，[os-impl 08](../../thinking/2026-11/06/os-impl/08-aos-daemon-ctl永遠直寄實作結果.md)；它是「指名 daemon」的工具，直寄＝繞過判官，有 Linux 權限就能用）。模式 1 設成 `<daemon 的 stack>/requests`、模式 2 設成 `<0 號的 stack>/requests`；可以由人設，或寫進 daemon 的 `.env` 帶給子項。
- 問腦的 llm kernel 用另一個變數 `AOS_LLM_KERNEL`（[01](01-llm-kernel.md)），跟這個各管一事。

### 誰能繞過 kernel：靠 Linux 權限

aos 不驗寄件人是誰，安全的保底是 Linux 本身（使用者、權限；[C-47](../../docs/CONCEPTS/04-kernel.md)「安全的保底是 Linux 本身」）。

- **要真的擋**：daemon 與判官用帳號 A，其他 proc 用帳號 B；daemon 的 ctl 信箱 `new/`、`tmp/` 不給 B 寫（B 寄進去當場 `aos-post: error: MailboxBad …`），`requests/` 給 B 寫。不加任何程式。
- **沒設權限也可以**：同一個帳號擋不住——daemon 的 ctl 信箱照樣寫得進去，`aos-daemon-ctl` 也照樣直達，等於繞過判官，風險自己承擔。使用者 11-05：「linux權限沒設也可以(因為我知道有些人嫌麻煩，或是還處在demo狀態)，就自行承擔風險。」
- daemon 不認寄件人白名單（要驗身分，跟「寄信的人是誰不驗」的先例相反）。

### 跑法（PATH 放 `proto8/impls/*/bin` 與 `proto8/cmd/*/bin`，或跑過 `proto8/install.sh`）

模式 1：起一台帶判官的 daemon，寄信進它的 `requests/`：

```sh
P=<repo>/proto8
mkdir -p /tmp/judge-try/m1 /tmp/judge-try/me && cd /tmp/judge-try/m1
aos-exec --stack /tmp/judge-try/m1/st $P/kernel/daemon-judge    # 一台 daemon；身體每 300 ms 跑一次 judge（另開視窗或丟背景）
aos-post init /tmp/judge-try/me/box                              # 收回信的信箱
echo "{\"procs_added\": {\"peek_now_time\": {\"exec\": \"$P/lib/base/peek_now_time\", \"interval_ms\": 1000}}}" \
  | aos-post send --reply-to /tmp/judge-try/me/box /tmp/judge-try/m1/st/requests
AOS_DAEMON=/tmp/judge-try/m1/st aos-daemon-ctl ls                # peek_now_time  running
cat /tmp/judge-try/me/box/new/*/letter.json                      # body {"applied": true}（daemon 回的）
```

白名單外的（`evil`）回 `{"applied": false, "error": {"code": "NameUnknown", "msg": "evil not in allowed"}}`；範本 `max_running` 是 5（清道夫＋4 格；`allowed` 有 `fsm1`、`kid`、`kid1`～`kid4`，給 [03](03-feat-proto.md) 件 4 的 agent 生 agent 劇本用），所以 peek_now_time 在跑時再寄 `peek_now_time2` 也放行；要看 `SlotMissing` 就照 03 件 4 跑，或把 `judge.json` 的 `max_running` 改成 2（判官每圈重讀；清道夫佔一格、peek_now_time 一格）再寄 `peek_now_time2`——這時 `{"procs_stopped": ["peek_now_time"]}` 原樣轉、回 `applied: true`，之後 `peek_now_time2` 就放行。收工：在 daemon 的視窗 Ctrl-C。

模式 2：一台普通 daemon（這個固定兩格的示例不帶鐘列；若自己加了鐘列，把判官設定 `max_running` 加一，預留那格），把 procs-kernel 掛上去當 0 號，寄信進它的 `requests/`：

```sh
mkdir -p /tmp/judge-try/m2/st && cd /tmp/judge-try/m2
echo '{"interval_ms": 200}' > daemon.json
AOS_STACK=/tmp/judge-try/m2/st/ aos-daemon daemon.json            # 另開視窗或丟背景
export AOS_DAEMON=/tmp/judge-try/m2/st
aos-daemon-ctl add $P/kernel/procs-kernel                        # 表上多一列 procs-kernel  running
aos-post init /tmp/judge-try/me/box2
echo "{\"procs_added\": {\"peek_now_time\": {\"exec\": \"$P/lib/base/peek_now_time\", \"interval_ms\": 1000}}}" \
  | aos-post send --reply-to /tmp/judge-try/me/box2 $AOS_DAEMON/procs/procs-kernel/requests
aos-daemon-ctl ls                                                # procs-kernel、peek_now_time 兩列 running；回信 {"applied": true}
```

範本 `max_running` 是 2（含 procs-kernel 自己），這時再寄 `peek_now_time2` 回 `SlotMissing`；`evil` 回 `NameUnknown`。

### 改成自己的

複製範本資料夾、改 `judge.json`。範本裡判官的路徑寫相對的 `../../lib/aos/judge`，搬到 repo 外要改成絕對路徑；`judge.json` 用 `{"$env": "AOS_CD", "$path": "judge.json"}` 指定義資料夾裡那份（aos-exec 會 cd 進判官自己的資料夾，相對路徑會算錯）。

### 已知限制

- 無序轉寄的防重依據只留在 ctl 信箱的 `new/` 或 `cur/`，若 daemon 已做完並移除轉寄信、判官才重啟，仍無法辨識原信已轉寄。
- 模式 2 的判官跟 daemon 各自打拍子：轉了、daemon 還沒套的不算 running，連著很快寄好幾封時可能多放幾個。模式 1 沒這個問題（判官跑在 daemon 那一圈裡，下一圈之前 daemon 已套完）。
- **模式 2 的 0 號睡著或停著**：信照 `AOS_KERNEL` 寄、不認誰是 kernel、不預判收件者有沒有在跑；沒有回信就等寄件人期限。判官睡著＝這是設計系統的人要管的風險（使用者 11-07），手動叫醒：`aos-daemon-ctl wake NAME`（停著用 `start`；這支是指名 daemon 的工具，一律直寄 daemon、不看 `AOS_KERNEL`）。程式不自動辨識、不自動叫醒、不自動繞過。逾時撤信與已轉寄後撤不回的競態見 [aos-agent 已知限制](../../cmd/aos-agent/docs/02-已知限制.md)。
- 判官自己的錯（`judge.json` 壞、沒 `AOS_DAEMON`、daemon 沒開 ctl 信箱）退 1：模式 1 daemon 不停——stderr 一行 `aos-daemon: warning: body … failed (code N), retrying next round`（碼變了才印，好了印 ok again）、`state.json` 記 `body_code`、下一圈再跑（使用者裁「記一行、下一圈再跑 (Recommended)」，N-28「daemon 的身體失敗」）；那段時間判官沒跑、`requests/` 的信沒人判；模式 2 那個 proc 出錯結束、表上留 `stopped`＋`reason`，修好 `start`（P-20）。
