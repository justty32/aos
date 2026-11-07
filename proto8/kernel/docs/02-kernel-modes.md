← [回入口 README.md](../README.md)｜段落：kernel 的三種模式與判官範本 daemon-judge、procs-kernel（11-05）｜上一份：[01-llm-kernel](01-llm-kernel.md)｜下一份：[03-feat-proto](03-feat-proto.md)

## kernel 的三種模式：daemon 本身、daemon-judge、procs-kernel（11-05）

使用者 11-05：「daemon是硬體……kernel和daemon，兩者其實可以合一，就是說，daemon他收請求，按照請求去掛proc到自己身上，而kernel按照定義，他是管理proc是否要執行的傢伙」「能包盡量包啦」。設計：[thinking 11-05 kernel-daemon 02 兩種模式](../../thinking/2026-11/05/kernel-daemon/02-兩種模式.md)、[02/01「唯一」與 AOS_KERNEL](../../thinking/2026-11/05/kernel-daemon/02-兩種模式/01-唯一-AOS_KERNEL-命名.md)。

**一句話：誰決定「這個 proc 掛不掛到 daemon 上」，誰就是 kernel。** 掛 proc 只有一條路——往 daemon 的 ctl 信箱（`procs_ctl_mailbox/`）寄一封 `procs_added` 信；三種模式的差別只在「寄進 ctl 信箱之前有沒有人先看一眼」。看一眼的那支程式是同一支：[`lib/aos/judge`](../../lib/aos/judge/_entry)（判官），用法與代號寫在它 `_entry` 開頭。

`daemon-judge` 範本出廠帶 `tick: true` 與 `--enable-logs`：表上 `_tick` 也是普通 running proc，會算進判官的 `max_running`；停 `_tick` 只停時間，工作照跑。

### 三種模式

| 模式 | 像什麼 | 要掛 proc 寄到哪（`AOS_KERNEL`） | 範本 |
|---|---|---|---|
| 0：daemon 本身 | 來者不拒的門房：信進來就照辦 | daemon 的 ctl 信箱（沒設 `AOS_KERNEL` 就是這個） | 任何一台 daemon |
| 1：繼承式 | daemon 自己的身體當判官：判過了才「呼叫 base」（＝轉寄進自己的 ctl 信箱） | `<daemon 的 stack>/requests` | [`kernel/daemon-judge/`](../daemon-judge) |
| 2：0 號 proc 式 | daemon 底下一個專門收請求的 proc（像 Linux 的 0 號），判過了替你寄進 daemon 的 ctl 信箱 | `<0 號 proc 的 stack>/requests` | [`kernel/procs-kernel/`](../procs-kernel) |

- **判官怎麼判**（政策檔 `judge.json`，放在定義裡）：`allowed`＝名字的白名單（`null` 或沒寫＝不限）；`max_running`＝同時最多幾個 running（數 daemon 表上 `running` 的列，`null` 或沒寫＝不限）。判 `procs_added`；`procs_started`、`procs_woken`（start／wake 讓停著、睡著的回來跑）不看 `allowed`、但照樣算進 `max_running`（11-05 edge-agent：原本照原樣轉，sleep 一隻、add 一隻、再 wake 就超過）；`procs_removed`、`procs_stopped`、`procs_slept` 照原樣轉。`{"ping": true}`（`aos-daemon-ctl ping`，11-06 [no-pid](../../thinking/2026-11/05/no-pid/README.md) P3）不判、帶原 `reply_to` 原樣轉寄，daemon 直接回給寄件人；判官不在＝沒人轉＝寄件人逾時，正好是它該知道的。不掛的每封都在判官的 stderr 印一行提醒 `judge: warning: letter <名> refused: 代號 …`（跟回信的 `code`、`msg` 同一句、英文；拒信是判官的答案、不是它的錯，照樣退 0）。
- **排隊選項**：`judge.json` 的 `queue` 預設 `false`（沒寫也一樣），格滿立刻 `SlotMissing`；寫 `true` 才把要格的 add／start／wake 留在 `requests/cur/`，**先來先掛（FIFO）**，不看 priority。stop／rm／sleep／ping 照樣立即轉寄，能騰出格的信不會被隊首擋住。排隊不算 running；整台 daemon 的總額只由判官 `max_running` 管（含 `_tick` 與模式 2 的判官自己），`agents.max_children` 只管 agents 工具自己的孩子，thought／直接 ctl 不受它限制。範本的 judge.json 不開 queue。
- **排隊窗與期限**：`$AOS_STACK/queue.json` 是先來先掛的公開進度窗：`{"queued": [{"letter", "names", "queued_at", "queued_at_ticks"?, "expires_at"?}]}`，陣列順序就是順位（已在隊的照舊；同一輪新進的照 aos-post 處理順序：有序信先、再照信名，跟不開排隊時一樣——11-07 sol 審查 #2，原本照 `sent_at`）；有 `AOS_TICK` 才記 `queued_at_ticks`。窗讀不懂（搬家、人手改壞）＝判官印一行 `judge: warning:`、當空窗，從 `requests/cur/` 照處理順序重排，不整輪退 1（11-07 sol 審查 #5）。信 body 的選填 `queue_wait_ms` 必須是非負整數，`0`＝不排、沒格就拒；正值從信封 `sent_at` 起按牆鐘算 `expires_at`，不是從判官首次看到信起算。到期不轉、回 `SlotMissing` 並收信；睡醒後連從未看過、已過期的信也拒，不能補掛。即使 `queue: false`，也先拒絕已過期的帶期限信，不會因關閉排隊而補掛。沒有期限就一直排；凍住時信與窗留在樹裡，醒來繼續。**凍住 8 小時，醒來第一輪帶期限的排隊信可能全部到期拒絕；要跨凍住排隊，用 `--on-queued ok` 不帶期限。**一封請求只有最後一封回信，排隊中不另回 queued 信。
- **判「掛」**：信原樣轉寄進 daemon 的 ctl 信箱，帶著原寄件人的 `reply_to`——daemon 套完直接回 `{"applied": true}` 給原寄件人（無序信的 `in_reply_to` 就是你寄出的那封的名字）。判官不轉手、不自己跑任何東西。
- **判「不掛」**：判官回 `{"applied": false, "error": {"code": "…", "msg": "…"}}` 給原寄件人。代號：`NameUnknown`（不在白名單）、`SlotMissing`（running 滿了）、`BodyBad`（body 或 `procs_added` 不是物件）、`ForwardFailed`（轉不進 ctl 信箱）。信沒 `reply_to`＝只收掉、只有 stderr 那行。
- **`aos-daemon-ctl --reply-to BOX`／`aos-agent ctl`**（11-05 [edge-agent 題 2](../../thinking/2026-11/05/edge-agent/README.md)，使用者選「加 --reply-to 等回信」）：`aos-daemon-ctl` 的寄信子命令收 `--reply-to`（11-07 起它一律直寄 daemon、不經判官，回信只會是 daemon 的）；`aos-agent ctl add` 等每封都帶共用回信信箱（`$AOS_STACK/daemon_reply/`，人殼＝`<daemon stack>/procs_ctl_mailbox/reply/`），判官不掛＝立刻 `AddRejected`（start／wake 被 `max_running` 擋＝`CtlRejected`）＋判官的代號與原因，不用等滿 `--timeout-s`（預設 30 秒）（[aos-agent README「等回信」](../../cmd/aos-agent/README.md)）。
- **模式 1 vs 2**：模式 1 的判官跑在 daemon 那一圈裡（阻塞），要快；要慢慢判（例：之後要問腦才能判）就用模式 2。模式 2 的 0 號自己也是表上一列 `running`，`max_running` 要把它算進去（範本寫 2）。

### `AOS_KERNEL`＝要掛 proc 往哪寄

- 值＝一個收 `procs_*` 信的信箱資料夾；信的形狀跟 daemon 的 ctl 信箱一模一樣，所以 daemon 的 ctl 信箱本身就是最基礎的那個（模式 0）。
- **沒設＝kernel 就是 daemon**：寄到 `$AOS_DAEMON` 的 ctl 信箱（不報錯）。
- **有設**：`aos-agent ctl` 的 `procs_*` 信改寄到 `$AOS_KERNEL`（**11-07 起 `aos-daemon-ctl` 不看它、一律直寄 daemon**：使用者選項框「aos-daemon-ctl 永遠直寄」，人直接敲板子＝繞過判官，[os-impl 08](../../thinking/2026-11/06/os-impl/08-aos-daemon-ctl永遠直寄實作結果.md)）。模式 1 設成 `<daemon 的 stack>/requests`、模式 2 設成 `<0 號的 stack>/requests`；可以由人設，或寫進 daemon 的 `.env` 帶給子項。
- 問腦的 llm kernel 用另一個變數 `AOS_LLM_KERNEL`（[01](01-llm-kernel.md)），跟這個各管一事。

### 「只有 kernel 能下 ctl」能做到哪（三級）

aos 不驗寄件人是誰。所以「唯一」只有三種強度：

1. **約定**：文件寫「這台走判官，掛東西寄 `$AOS_KERNEL`」。同一個帳號擋不住——daemon 的 ctl 信箱照樣寫得進去，`aos-daemon-ctl`（11-07 起一律）也照樣直達，等於繞過判官。
2. **Linux 權限**（真的擋）：daemon 與判官用帳號 A，其他 proc 用帳號 B；daemon 的 ctl 信箱 `new/`、`tmp/` 不給 B 寫（B 寄進去當場 `aos-post: error: MailboxBad …`），`requests/` 給 B 寫。不加任何程式。
3. **daemon 認寄件人白名單**：不做（要驗身分、跟「寄信的人是誰不驗」的先例相反）。

使用者 11-05 裁定：「linux權限沒設也可以(因為我知道有些人嫌麻煩，或是還處在demo狀態)，就自行承擔風險。」——第 2 級不強制；沒設權限就是第 1 級，繞過判官的風險自己承擔。

### 跑法（11-05 手跑過的指令；PATH 放 `proto8/impls/*/bin` 與 `proto8/cmd/*/bin`，或跑過 `proto8/install.sh`）

模式 1：起一台帶判官的 daemon，寄信進它的 `requests/`：

```sh
P=<repo>/proto8
mkdir -p /tmp/judge-try/m1 /tmp/judge-try/me && cd /tmp/judge-try/m1
aos-exec --stack /tmp/judge-try/m1/st $P/kernel/daemon-judge    # 一台 daemon；身體每 300 ms 跑一次 judge（另開視窗或丟背景）
aos-post init /tmp/judge-try/me/box                              # 收回信的信箱
echo "{\"procs_added\": {\"clock\": {\"exec\": \"$P/lib/base/clock\", \"interval_ms\": 1000}}}" \
  | aos-post send --reply-to /tmp/judge-try/me/box /tmp/judge-try/m1/st/requests
AOS_DAEMON=/tmp/judge-try/m1/st aos-daemon-ctl ls                # clock  running
cat /tmp/judge-try/me/box/new/*/letter.json                      # body {"applied": true}（daemon 回的）
```

白名單外的（`evil`）回 `{"applied": false, "error": {"code": "NameUnknown", "msg": "evil not in allowed"}}`；範本 `max_running` 是 4（11-05 午從 1 改成 4、`allowed` 多了 `fsm1`、`kid`、`kid1`～`kid4`，給 [03](03-feat-proto.md) 件 4 的 agent 生 agent 劇本用），所以 clock 在跑時再寄 `clock2` 也放行；要看 `SlotMissing` 就照 03 件 4 跑，或把 `judge.json` 的 `max_running` 改成 2（含 `_tick`；判官每圈重讀）再寄 `clock2`——這時 `{"procs_stopped": ["clock"]}` 原樣轉、回 `applied: true`，之後 `clock2` 就放行。收工：在 daemon 的視窗 Ctrl-C。

模式 2：一台普通 daemon（這個固定兩格的示例刻意不開 tick；若加 `"tick": true`，把自己的判官設定 `max_running` 加一，預留 `_tick` 那格），把 procs-kernel 掛上去當 0 號，寄信進它的 `requests/`：

```sh
mkdir -p /tmp/judge-try/m2/st && cd /tmp/judge-try/m2
echo '{"interval_ms": 200}' > daemon.json
AOS_STACK=/tmp/judge-try/m2/st/ aos-daemon daemon.json            # 另開視窗或丟背景
export AOS_DAEMON=/tmp/judge-try/m2/st
aos-daemon-ctl add $P/kernel/procs-kernel                        # 表上多一列 procs-kernel  running
aos-post init /tmp/judge-try/me/box2
echo "{\"procs_added\": {\"clock\": {\"exec\": \"$P/lib/base/clock\", \"interval_ms\": 1000}}}" \
  | aos-post send --reply-to /tmp/judge-try/me/box2 $AOS_DAEMON/procs/procs-kernel/requests
aos-daemon-ctl ls                                                # procs-kernel、clock 兩列 running；回信 {"applied": true}
```

範本 `max_running` 是 2（含 procs-kernel 自己），這時再寄 `clock2` 回 `SlotMissing`；`evil` 回 `NameUnknown`。

### 改成自己的

複製範本資料夾、改 `judge.json`。範本裡判官的路徑寫相對的 `../../lib/aos/judge`，搬到 repo 外要改成絕對路徑；`judge.json` 用 `{"$env": "AOS_CD", "$path": "judge.json"}` 指定義資料夾裡那份（aos-exec 會 cd 進判官自己的資料夾，相對路徑會算錯）。

### 已知限制

- 模式 2 的判官跟 daemon 各自打拍子：轉了、daemon 還沒套的不算 running，連著很快寄好幾封時可能多放幾個。模式 1 沒這個問題（判官跑在 daemon 那一圈裡，下一圈之前 daemon 已套完）。
- **模式 2 的 0 號睡著或停著**：信照 `AOS_KERNEL` 寄、不認誰是 kernel、不預判收件者有沒有在跑；沒有回信就等寄件人期限。判官睡著＝這是設計系統的人要管的風險（使用者 11-07），手動叫醒：`aos-daemon-ctl wake NAME`（停著用 `start`；這支一律直寄 daemon、不看 `AOS_KERNEL`）。程式不自動辨識、不自動叫醒、不自動繞過。逾時撤信與已轉寄後撤不回的競態見 [aos-agent 已知限制](../../cmd/aos-agent/docs/02-已知限制.md)。
- 判官自己的錯（`judge.json` 壞、沒 `AOS_DAEMON`、daemon 沒開 ctl 信箱）退 1：模式 1 daemon 不停——stderr 一行 `aos-daemon: body … failed (code N), retrying next round`（碼變了才印，好了印 ok again）、`state.json` 記 `body_code`、下一圈再跑（11-05 使用者裁「記一行、下一圈再跑 (Recommended)」，N-28 ⑥）；那段時間判官沒跑、`requests/` 的信沒人判；模式 2 那個 proc 出錯結束、表上留 `stopped`＋`reason`，修好 `start`（P-20）。
