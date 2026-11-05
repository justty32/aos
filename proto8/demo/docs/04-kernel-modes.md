← [回入口 README.md](../README.md)｜段落：kernel 的三種模式與判官範本 daemon-judge、procs-kernel（11-05）｜上一份：[03-llm-kernel](03-llm-kernel.md)｜下一份：[05-feat-proto](05-feat-proto.md)

## kernel 的三種模式：daemon 本身、daemon-judge、procs-kernel（11-05）

使用者 11-05：「daemon是硬體……kernel和daemon，兩者其實可以合一，就是說，daemon他收請求，按照請求去掛proc到自己身上，而kernel按照定義，他是管理proc是否要執行的傢伙」「能包盡量包啦」。設計：[thinking 11-05 kernel-daemon 02 兩種模式](../../thinking/2026-11/05/kernel-daemon/02-兩種模式.md)、[02/01「唯一」與 AOS_KERNEL](../../thinking/2026-11/05/kernel-daemon/02-兩種模式/01-唯一-AOS_KERNEL-命名.md)。

**一句話：誰決定「這個 proc 掛不掛到 daemon 上」，誰就是 kernel。** 掛 proc 只有一條路——往 daemon 的 ctl 信箱（`procs_ctl_mailbox/`）寄一封 `procs_added` 信；三種模式的差別只在「寄進 ctl 信箱之前有沒有人先看一眼」。看一眼的那支程式是同一支：[`lib/base/judge`](../../lib/base/judge/_entry)（判官），用法與代號寫在它 `_entry` 開頭。

### 三種模式

| 模式 | 像什麼 | 要掛 proc 寄到哪（`AOS_KERNEL`） | 範本 |
|---|---|---|---|
| 0：daemon 本身 | 來者不拒的門房：信進來就照辦 | daemon 的 ctl 信箱（沒設 `AOS_KERNEL` 就是這個） | 任何一台 daemon |
| 1：繼承式 | daemon 自己的身體當判官：判過了才「呼叫 base」（＝轉寄進自己的 ctl 信箱） | `<daemon 的 stack>/requests` | [`demo/daemon-judge/`](../daemon-judge/) |
| 2：0 號 proc 式 | daemon 底下一個專門收請求的 proc（像 Linux 的 0 號），判過了替你寄進 daemon 的 ctl 信箱 | `<0 號 proc 的 stack>/requests` | [`demo/procs-kernel/`](../procs-kernel/) |

- **判官怎麼判**（政策檔 `judge.json`，放在定義裡）：`allowed`＝名字的白名單（`null` 或沒寫＝不限）；`max_running`＝同時最多幾個 running（數 daemon 表上 `running` 的列，`null` 或沒寫＝不限）。判 `procs_added`；`procs_started`、`procs_woken`（start／wake 讓停著、睡著的回來跑）不看 `allowed`、但照樣算進 `max_running`（11-05 edge-agent：原本照原樣轉，sleep 一隻、add 一隻、再 wake 就超過）；`procs_removed`、`procs_stopped`、`procs_slept` 照原樣轉。不掛的每封都在判官的 stderr 印一行 `judge: 代號 letter <名> refused: …`（跟回信的 `msg` 同一句、英文）。
- **判「掛」**：信原樣轉寄進 daemon 的 ctl 信箱，帶著原寄件人的 `reply_to`——daemon 套完直接回 `{"applied": true}` 給原寄件人（無序信的 `in_reply_to` 就是你寄出的那封的名字）。判官不轉手、不自己跑任何東西。
- **判「不掛」**：判官回 `{"applied": false, "error": {"code": "…", "msg": "…"}}` 給原寄件人。代號：`NameUnknown`（不在白名單）、`SlotMissing`（running 滿了）、`BodyBad`（body 或 `procs_added` 不是物件）、`ForwardFailed`（轉不進 ctl 信箱）。信沒 `reply_to`＝只收掉、只有 stderr 那行。
- **`aos-daemon-ctl --reply-to BOX`／`aos-agent ctl`**（11-05 [edge-agent 題 2](../../thinking/2026-11/05/edge-agent/README.md)，使用者選「加 --reply-to 等回信」）：`aos-daemon-ctl` 的寄信子命令收 `--reply-to`；`aos-agent ctl add` 等每封都開一個暫時信箱帶過去，判官不掛＝立刻 `AddRejected`（start／wake 被 `max_running` 擋＝`CtlRejected`）＋判官的代號與原因，不用等 30 秒（[extras/agent README「等回信」](../../extras/agent/README.md)）。
- **模式 1 vs 2**：模式 1 的判官跑在 daemon 那一圈裡（阻塞），要快；要慢慢判（例：之後要問腦才能判）就用模式 2。模式 2 的 0 號自己也是表上一列 `running`，`max_running` 要把它算進去（範本寫 2）。

### `AOS_KERNEL`＝要掛 proc 往哪寄

- 值＝一個收 `procs_*` 信的信箱資料夾；信的形狀跟 daemon 的 ctl 信箱一模一樣，所以 daemon 的 ctl 信箱本身就是最基礎的那個（模式 0）。
- **沒設＝kernel 就是 daemon**：寄到 `$AOS_DAEMON` 的 ctl 信箱（不報錯）。
- **有設**：`aos-daemon-ctl`（`aos-agent` 經它）的 `procs_*` 信改寄到 `$AOS_KERNEL`。模式 1 設成 `<daemon 的 stack>/requests`、模式 2 設成 `<0 號的 stack>/requests`；可以由人設，或寫進 daemon 的 `.env` 帶給子項。
- 問腦的 llm kernel 用另一個變數 `AOS_LLM_KERNEL`（[03](03-llm-kernel.md)），跟這個各管一事。

### 「只有 kernel 能下 ctl」能做到哪（三級）

aos 不驗寄件人是誰。所以「唯一」只有三種強度：

1. **約定**：文件寫「這台走判官，掛東西寄 `$AOS_KERNEL`」。同一個帳號擋不住——daemon 的 ctl 信箱照樣寫得進去，`aos-daemon-ctl`（沒設 `AOS_KERNEL` 時）也照樣直達，等於繞過判官。
2. **Linux 權限**（真的擋）：daemon 與判官用帳號 A，其他 proc 用帳號 B；daemon 的 ctl 信箱 `new/`、`tmp/` 不給 B 寫（B 寄進去當場 `aos-post: MailboxBad`），`requests/` 給 B 寫。不加任何程式。
3. **daemon 認寄件人白名單**：不做（要驗身分、跟「寄信的人是誰不驗」的先例相反）。

使用者 11-05 裁定：「linux權限沒設也可以(因為我知道有些人嫌麻煩，或是還處在demo狀態)，就自行承擔風險。」——第 2 級不強制；沒設權限就是第 1 級，繞過判官的風險自己承擔。

### 跑法（11-05 手跑過的指令；PATH 放 `proto8/impls/*/bin` 與 `proto8/bin`，或跑過 `proto8/install.sh`）

模式 1：起一台帶判官的 daemon，寄信進它的 `requests/`：

```sh
P=<repo>/proto8
mkdir -p /tmp/judge-try/m1 /tmp/judge-try/me && cd /tmp/judge-try/m1
aos-exec --stack /tmp/judge-try/m1/st $P/demo/daemon-judge      # 一台 daemon；身體每 300 ms 跑一次 judge（另開視窗或丟背景）
aos-post init /tmp/judge-try/me/box                              # 收回信的信箱
echo "{\"procs_added\": {\"clock\": {\"exec\": \"$P/lib/base/clock\", \"interval_ms\": 1000}}}" \
  | aos-post send --reply-to /tmp/judge-try/me/box /tmp/judge-try/m1/st/requests
AOS_DAEMON=/tmp/judge-try/m1/st aos-daemon-ctl ls                # clock  running
cat /tmp/judge-try/me/box/new/*/letter.json                      # body {"applied": true}（daemon 回的）
```

白名單外的（`evil`）回 `{"applied": false, "error": {"code": "NameUnknown", "msg": "evil not in allowed"}}`；範本 `max_running` 是 4（11-05 午從 1 改成 4、`allowed` 多了 `fsm1`、`kid`、`kid1`～`kid4`，給 [05](05-feat-proto.md) 件 4 的 agent 生 agent 劇本用），所以 clock 在跑時再寄 `clock2` 也放行；要看 `SlotMissing` 就照 05 件 4 跑，或把 `judge.json` 的 `max_running` 改回 1（判官每圈重讀）再寄 `clock2`——這時 `{"procs_stopped": ["clock"]}` 原樣轉、回 `applied: true`，之後 `clock2` 就放行。收工：在 daemon 的視窗 Ctrl-C。

模式 2：一台普通 daemon，把 procs-kernel 掛上去當 0 號，寄信進它的 `requests/`：

```sh
mkdir -p /tmp/judge-try/m2/st && cd /tmp/judge-try/m2
echo '{"interval_ms": 200}' > daemon.json
AOS_STACK=/tmp/judge-try/m2/st/ aos-daemon daemon.json            # 另開視窗或丟背景
export AOS_DAEMON=/tmp/judge-try/m2/st
aos-daemon-ctl add $P/demo/procs-kernel                          # 表上多一列 procs-kernel  running
aos-post init /tmp/judge-try/me/box2
echo "{\"procs_added\": {\"clock\": {\"exec\": \"$P/lib/base/clock\", \"interval_ms\": 1000}}}" \
  | aos-post send --reply-to /tmp/judge-try/me/box2 $AOS_DAEMON/procs/procs-kernel/requests
aos-daemon-ctl ls                                                # procs-kernel、clock 兩列 running；回信 {"applied": true}
```

範本 `max_running` 是 2（含 procs-kernel 自己），這時再寄 `clock2` 回 `SlotMissing`；`evil` 回 `NameUnknown`。

### 改成自己的

複製範本資料夾、改 `judge.json`。範本裡判官的路徑寫相對的 `../../lib/base/judge`，搬到 repo 外要改成絕對路徑；`judge.json` 用 `{"$env": "AOS_CD", "$path": "judge.json"}` 指定義資料夾裡那份（aos-exec 會 cd 進判官自己的資料夾，相對路徑會算錯）。

### 已知限制

- 模式 2 的判官跟 daemon 各自打拍子：轉了、daemon 還沒套的不算 running，連著很快寄好幾封時可能多放幾個。模式 1 沒這個問題（判官跑在 daemon 那一圈裡，下一圈之前 daemon 已套完）。
- **模式 2 的 0 號睡著或停著**：寄給它的信排在它的 `requests/` 等它回來。所以 kernel 本身的 wake／start 不能寄給它自己——`aos-agent ctl wake --target procs-kernel` 會認出「對象就是 `AOS_KERNEL` 那個」、直接寄 daemon；直接打 `aos-daemon-ctl` 的要先 `unset AOS_KERNEL`（或 `AOS_KERNEL= aos-daemon-ctl wake procs-kernel`）。`aos-agent ctl add` 等這種情形會立刻 `WaitFailed` 說 kernel 睡著（11-05 edge-agent）；那封留在 0 號的 `requests/`、醒來才判，回信寄到已刪的暫時信箱＝判官 stderr 一行 `ReplyFailed`、照樣收掉。
- 判官自己的錯（`judge.json` 壞、沒 `AOS_DAEMON`、daemon 沒開 ctl 信箱）退 1：模式 1 daemon 不停——stderr 一行 `aos-daemon: body … failed (code N), retrying next round`（碼變了才印，好了印 ok again）、`state.json` 記 `body_code`、下一圈再跑（11-05 使用者裁「記一行、下一圈再跑 (Recommended)」，N-28 ⑥）；那段時間判官沒跑、`requests/` 的信沒人判；模式 2 那個 proc 出錯結束、表上留 `stopped`＋`reason`，修好 `start`（P-20）。
