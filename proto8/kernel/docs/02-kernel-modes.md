← [回入口 README.md](../README.md)｜段落：kernel 是什麼、框架站怎麼判、三種擺法與手跑、鏈與 hook 的例子｜上一份：[01-llm-kernel](01-llm-kernel.md)｜下一份：[03-feat-proto](03-feat-proto.md)

## kernel 與框架站：三種擺法（daemon 的身體、loop proc、鏈的中間站）

使用者 11-05：「daemon是硬體……kernel和daemon，兩者其實可以合一，就是說，daemon他收請求，按照請求去掛proc到自己身上」「能包盡量包啦」；11-11：「我覺得kernel定義要改一下，回歸初始，變成"資源管理+排程"。」（[CONCEPTS C-47](../../docs/CONCEPTS/04-kernel.md)、[thinking 11-11 kernel](../../thinking/2026-11/11/kernel/README.md)）。框架的圖紙：[thinking 11-12 kernel-framework](../../thinking/2026-11/12/kernel-framework/README.md)。

**一句話：請求寄到哪，那裡對寄件人就是 kernel**（資源管理＋排程；要不要處理、什麼時候執行由收件那邊說了算，啥都不管也是一種管理）。一般 proc 只寄 `$AOS_KERNEL`、不管背後信會去哪；收件的 proc 不必知道自己是 kernel。

掛 proc 最後都是一封 `procs_added` 信進某台 daemon 的 ctl 信箱（`procs_requests/`）。差別只在「寄進 ctl 信箱之前有沒有人先看一眼」。沒人看，就是直接寄給 daemon（daemon 來者不拒，是最基礎的 kernel）。有人看，看的那支程式就是**框架站**（通用 kernel 的站）：[`lib/aos/kernel`](../../lib/aos/kernel/README.md)，零件表與 `kernel.json` 的鍵在[入口](../README.md)，每個鍵的細節與錯誤代號在它自己的 README。

### 三種擺法

三種都是範例，不是只有這三種。自己寫一個收請求、決定要不要轉的 proc 也算 kernel（見下面「改成自己的」）。

| 擺法 | 像什麼 | 要掛 proc 寄到哪（`AOS_KERNEL`） | 範本 |
|---|---|---|---|
| 不擺站 | 來者不拒的門房：信進來就照辦 | daemon 的 ctl 信箱（沒設 `AOS_KERNEL` 就是這個） | 任何一台 daemon |
| daemon 的身體 | daemon 自己的身體就是站：過了規則才轉寄進自己的 ctl 信箱 | `<daemon 的 stack>/requests` | [`kernel/daemon-kernel/`](../daemon-kernel) |
| daemon 底下一個 loop proc | daemon 底下一個專門收請求的 proc（像 Linux 的 0 號），過了規則替你寄進 daemon 的 ctl 信箱 | `<那個 proc 的 stack>/requests` | [`kernel/procs-kernel/`](../procs-kernel) |
| 鏈的中間站 | 上面兩種任一種，但放行的信不給自己那台 daemon，而是轉給另一個站 | `<這一站的 stack>/requests` | 沒有現成範本，見下面「鏈的例子」 |

- **身體還是 loop proc**：當身體時，站跑在 daemon 那一圈裡，這一輪卡多久 daemon 那一圈就卡多久，所以要快。要慢慢判（例：hook 裡要問腦）就用 loop proc。loop proc 自己也是表上一列 `running`，`max_running` 要把它算進去（範本 `procs-kernel` 寫 2＝站自己＋1 格）。
- **`daemon-kernel` 範本的格數**：出廠帶 `--enable-logs`、不帶鐘列。`max_running` 數的是這台表上所有在跑的列，範本帶的清道夫 `_sweeper` 也佔一格，所以預設 5＝4 隻工作 proc＋清道夫。不掛清道夫的（從 `daemon.json` 刪掉那列）自己把 `kernel.json` 的 `max_running` 調回 4；自己加了鐘列的再加一。`max_running` 是可選的：寫非負整數＝上限，寫 `null` 或不寫＝不限（使用者 11-10「上限應該是可選的，默認的值就隨意，改5吧。」）。

### 框架站怎麼判

- **規則**（寫在 `kernel.json`，放在定義裡）：`allowed`＝名字的白名單（`null` 或沒寫＝不限）；`max_running`＝同時最多幾個在跑（數 `count_daemon` 那台表上 `running` 與 `stuck` 的列，加上這一輪已放行的新名字）。`procs_added` 兩條都看；`procs_started`、`procs_woken`（讓停著、睡著的回來跑）不看 `allowed`，但照樣算進 `max_running`（不算的話 sleep 一隻、add 一隻、再 wake 就超過）。`procs_removed`、`procs_stopped`、`procs_slept`、`{"ping": true}` 與其他不認得的 body 都不判、原樣轉。`allowed`、`max_running` 都沒寫、信也沒帶期限時，站連 body 是不是物件都不驗。
- **放行**：body 原樣轉寄給下一站，原信的 `reply_to` 照帶，所以下游（例如 daemon）套完直接回 `{"applied": true}` 給原寄件人。站只判斷、轉寄與代回，不自己跑任何東西。
- **不放行**：站回 `{"applied": false, "error": {"code": "…", "msg": "…"}}` 給原寄件人，同一句印在自己的 stderr：`kernel: warning: letter <名> refused: 代號 原因`。拒信是站的答案、不是它的錯，這一輪照樣退 0。代號：`NameUnknown`（不在白名單）、`SlotMissing`（沒格，或期限過了）、`BodyBad`（規則要看的欄形狀不對）、`ForwardFailed`（轉不進下一站）、`HookRejected`（被 hook 攔下）。信沒 `reply_to`＝只收掉，只有 stderr 那行。
- **排隊**：`queue` 預設 `false`（沒寫也一樣），格滿立刻 `SlotMissing`。寫 `true` 才把要格的 add／start／wake 留在 `requests/cur/`，**先來先掛（FIFO）**，不看 priority。隊首還沒格時，後面要新格的不能插隊；stop／rm／sleep／ping 照樣立即轉寄，能騰出格的信不會被隊首擋住。排隊不算在跑。程式預設關；範本 `daemon-kernel/kernel.json` 開 `queue: true`。（使用者裁定 sol 審查 #1）一封請求只有最後一封回信，排隊中不另回「排隊中」的信。
- **排隊窗**：`$AOS_STACK/queue.json` 是公開的進度窗：`{"queued": [{"letter", "names", "queued_at", "queued_at_cycles"?, "expires_at"?}]}`，陣列順序就是順位（已在隊的保持原順位；同一輪新進的照 aos-post 處理順序：有序信先、再照信名）；有 `AOS_CLOCK` 才記 `queued_at_cycles`。窗讀不懂（搬家、人手改壞）＝站印一行 `kernel: warning:`、當空窗，從 `requests/cur/` 照處理順序重排，不整輪退 1。
- **寄件人的期限**：信 body 的選填 `queue_wait_ms` 必須是非負整數。`0`＝不排，沒格就拒。正值從信封 `sent_at` 起按牆鐘算，不是從站第一次看到信起算；到期不轉、回 `SlotMissing` 並收信，就算當下有格也拒，不能補掛。`queue: false` 時也先拒已過期的信。沒有期限就一直排。**期限用牆鐘；凍住期間牆鐘照走，醒來第一輪已過期的排隊信一起拒絕；要跨凍住排隊，用 `--on-queued ok`。**（使用者裁定 sol 審查 #6）`--on-queued ok` 不帶期限，表示信可能永遠排著。（使用者裁定 sol 審查 #4）
- **有序信**：`keep_ordered` 選填布林，沒寫或 `null` 都是 `false`（使用者裁定 sol 審查 #3）。關的時候，有序信用去掉序號的尾名當一般信轉寄：**經過站不保有序，下游回信的 `in_reply_to` 是尾名，要對得上請寄一般信**。（代定、可翻案：[晚審 04](../../../wf/workflows/refactor/reports/2026-11-07-晚審/04-要使用者裁定.md)）開的時候照有序轉寄，信名會變，站在 `$AOS_STACK/forwarded.json` 記一列防重。
- **回信先回我**：`reply_via_me: true` 時，轉寄的信把 `reply_to` 改成站自己的 `$AOS_STACK/replies/`，並在 `forwarded.json` 記 `{轉寄後信名: {"letter": 原信名, "reply_to": 原回信箱, "sender": 原寄件人}}`。之後每輪收 `replies/`，用原信名代回原回信箱。原信沒 `reply_to` 就不改。代回寄不進去或原回信箱不在了＝一行 warning、收掉，不重試（寄件人本來就靠自己的逾時）。`keep_ordered` 與 `reply_via_me` 是兩個獨立的鍵：只開 `keep_ordered` 時下游直接回，回信對到的是轉寄後的新信名；要保有序又要回信對得上原信，兩個都開。（框架圖紙代定）
- **`aos-agent ctl` 怎麼收到拒信**（[edge-agent 題 2](../../thinking/2026-11/05/edge-agent/README.md)，使用者選「加 --reply-to 等回信」）：`aos-agent ctl add` 等每封都帶共用回信信箱（`$AOS_STACK/daemon_reply/`，人殼＝`<daemon stack>/procs_requests/reply/`），站不放行＝立刻 `AddRejected`（start／wake 被 `max_running` 擋＝`CtlRejected`）＋站的代號與原因，不用等滿 `--timeout-s`（預設 30 秒）（[aos-agent README「等回信」](../../cmd/aos-agent/README.md)）。

### `AOS_KERNEL`＝一般 proc 寄請求的地方

- 值＝一般 proc 送 syscall 請求的信箱資料夾（C-47「一律寄 `AOS_KERNEL`」）；現在收的是 `procs_*` 信，形狀跟 daemon 的 ctl 信箱一模一樣，所以 daemon 的 ctl 信箱本身就是最基礎的那個。
- **沒設＝kernel 就是 daemon**：寄到 `$AOS_DAEMON` 的 ctl 信箱（不報錯）。`AOS_DAEMON` 也沒設時，再找 cwd 的 `./.stack`，也不是資料夾才 `DaemonMissing`（[N-63「`AOS_DAEMON` 沒設＝找 cwd 的 `./.stack`」](../../docs/NORMS/10-基礎設施-定義與工作區/07-hub-型環境變數與父子交代/02-N-63-實例-AOS_DAEMON與沒有AOS_HUB.md)）。
- **有設**：`aos-agent ctl` 的 `procs_*` 信改寄到 `$AOS_KERNEL`。站當 daemon 身體時設成 `<daemon 的 stack>/requests`，當 loop proc 時設成 `<那個 proc 的 stack>/requests`；可以由人設，或寫進 daemon 的 `.env` 帶給子項。
- **`aos-daemon-ctl` 不看它、一律直寄 daemon**（使用者 11-07 選項框「aos-daemon-ctl 永遠直寄」，[os-impl 08](../../thinking/2026-11/06/os-impl/08-aos-daemon-ctl永遠直寄實作結果.md)）：它是「指名 daemon」的工具，直寄＝不經過站，有 Linux 權限就能用。使用者 11-13 裁定照現況：`aos-daemon-ctl` 是人直接敲板子的保底，「唯一的門」只約束 proc（[裁定落地-1113](../../thinking/2026-11/13/裁定落地-1113.md)）。
- 站自己要把信轉去哪，是 `kernel.json` 的 `next`，跟 `AOS_KERNEL` 各管一事（[入口「`next` 與 `AOS_KERNEL` 各管什麼」](../README.md)）。問腦的 llm kernel 用另一個變數 `AOS_LLM_KERNEL`（[01](01-llm-kernel.md)）。

### 誰能繞過 kernel：靠 Linux 權限

aos 不驗寄件人是誰，安全的保底是 Linux 本身（使用者、權限；[C-47](../../docs/CONCEPTS/04-kernel.md)「安全的保底是 Linux 本身」）。

- **要真的擋**：daemon 與站用帳號 A，其他 proc 用帳號 B；daemon 的 ctl 信箱 `new/`、`tmp/` 不給 B 寫（B 寄進去當場 `aos-post: error: MailboxBad …`），`requests/` 給 B 寫。不加任何程式。
- **沒設權限也可以**：同一個帳號擋不住——daemon 的 ctl 信箱照樣寫得進去，`aos-daemon-ctl` 也照樣直達，等於繞過站，風險自己承擔。使用者 11-05：「linux權限沒設也可以(因為我知道有些人嫌麻煩，或是還處在demo狀態)，就自行承擔風險。」
- daemon 不認寄件人白名單（要驗身分，跟「寄信的人是誰不驗」的先例相反）。

### 跑法

先準備（PATH 放 `proto8/impls/*/bin` 與 `proto8/cmd/*/bin`，或跑過 `proto8/install.sh`）。下面每一段都在同一個暫存夾裡做，每台 daemon 用完就用 `aos-daemon-ctl -d <它的 stack> shutdown` 收掉。

```sh
P=<repo>/proto8
export AOS_HOME=$P            # 範本裡框架站的路徑寫 {"$env": "AOS_HOME", …}，要先設
unset AOS_DAEMON AOS_KERNEL   # 殼裡如果本來有，先拿掉，免得寄到別的樹
T=$(mktemp -d)
```

**daemon 的身體**：起一台帶框架站的 daemon，寄信進它的 `requests/`：

```sh
mkdir -p $T/m1 $T/me && cd $T/m1
aos-exec --stack $T/m1/st $P/kernel/daemon-kernel &             # 一台 daemon；身體每 300 ms 跑一輪框架站
aos-post init $T/me/box                                          # 收回信的信箱
echo "{\"procs_added\": {\"peek_now_time\": {\"exec\": \"$P/lib/base/peek_now_time\", \"interval_ms\": 1000}}}" \
  | aos-post send --reply-to $T/me/box $T/m1/st/requests
echo '{"procs_added": {"evil": {"exec": "/bin/true"}}}' \
  | aos-post send --reply-to $T/me/box $T/m1/st/requests
aos-daemon-ctl -d $T/m1/st ls                                    # _sweeper、peek_now_time 兩列 running
cat $T/me/box/new/*/letter.json                                  # 兩封回信
aos-daemon-ctl -d $T/m1/st shutdown                              # 收工
```

`peek_now_time` 的回信 body 是 `{"applied": true}`（daemon 回的）。`evil` 不在白名單，回信 body 是：

```json
{"applied": false, "error": {"code": "NameUnknown", "msg": "evil not in allowed"}}
```

daemon 的 stderr 同時多一行 `kernel: warning: letter <信名> refused: NameUnknown evil not in allowed`。

**看排隊**：範本的 `max_running` 是 5，手上的例子塞不滿。抄一份範本、把上限改成 2（清道夫佔一格，只剩一格）：

```sh
cp -r $P/kernel/daemon-kernel $T/mine
echo '{"allowed": ["peek_now_time", "peek_now_time2"], "max_running": 2, "queue": true}' > $T/mine/kernel.json
mkdir -p $T/q && cd $T/q
aos-exec --stack $T/q/st $T/mine &
aos-post init $T/me/qbox
# 照上面的寫法先寄 peek_now_time、再寄 peek_now_time2（都帶 --reply-to $T/me/qbox，寄到 $T/q/st/requests）
cat $T/q/st/queue.json
```

第一封放行。第二封沒格、而且開了 `queue`，所以**不是拒、是排隊**，這時還沒有它的回信，窗裡看得到它：

```json
{"queued": [{"letter": "01794537115204849541.669633.829759", "names": ["peek_now_time2"], "queued_at": "2026-11-13T02:31:55.219Z"}]}
```

要立刻看到 `SlotMissing`，在信 body 加 `"queue_wait_ms": 0`（意思是沒格就不要排），或把 `kernel.json` 的 `queue` 改成 `false`。帶 `queue_wait_ms: 0` 再寄一次 `peek_now_time2`，回信是：

```json
{"applied": false, "error": {"code": "SlotMissing", "msg": "max_running is 2, 2 running now (counting ones let through this round), this letter adds 1"}}
```

騰出一格，排著的那封就出隊：寄 `{"procs_stopped": ["peek_now_time"]}`（停的信不判、原樣轉，回 `{"applied": true}`），之後 `aos-daemon-ctl -d $T/q/st ls` 看到 `peek_now_time  stopped`、`peek_now_time2  running`，`queue.json` 變回 `{"queued": []}`，排隊那封的回信 `{"applied": true}` 也到了。收工：`aos-daemon-ctl -d $T/q/st shutdown`。

**daemon 底下一個 loop proc**：一台普通 daemon，把 `procs-kernel` 掛上去，寄信進它的 `requests/`：

```sh
mkdir -p $T/m2/st && cd $T/m2
echo '{"interval_ms": 200}' > daemon.json
AOS_STACK=$T/m2/st/ aos-daemon daemon.json &
aos-daemon-ctl -d $T/m2/st add $P/kernel/procs-kernel            # 表上多一列 procs-kernel  running
aos-post init $T/me/box2
echo "{\"procs_added\": {\"peek_now_time\": {\"exec\": \"$P/lib/base/peek_now_time\", \"interval_ms\": 1000}}}" \
  | aos-post send --reply-to $T/me/box2 $T/m2/st/procs/procs-kernel/requests
aos-daemon-ctl -d $T/m2/st ls                                    # procs-kernel、peek_now_time 兩列 running；回信 {"applied": true}
```

範本 `max_running` 是 2（含 `procs-kernel` 自己）、沒開 `queue`，這時再寄 `peek_now_time2` 立刻回 `SlotMissing`。這台 daemon 先留著，下一段「手跑一輪」還會用到；用完 `aos-daemon-ctl -d $T/m2/st shutdown`。

**手跑一輪**：框架站每次執行就是一輪，可以不靠 daemon 自己叫一次，方便看設定對不對：

```sh
mkdir -p $T/hand/st && echo '{}' > $T/hand/kernel.json
AOS_STACK=$T/hand/st AOS_DAEMON=$T/m2/st aos-exec $P/lib/aos/kernel $T/hand/kernel.json   # 沒信也退 0，建好 st/requests/
AOS_STACK=$T/hand/st aos-exec $P/lib/aos/kernel $T/hand/kernel.json
# kernel: error: DaemonMissing AOS_DAEMON is not set or not a directory: (empty)      （退 1）
echo '{"next": "x", "max_running": 1}' > $T/hand/kernel.json
AOS_STACK=$T/hand/st aos-exec $P/lib/aos/kernel $T/hand/kernel.json
# kernel: error: CfgBad next with max_running requires count_daemon                   （退 1）
```

### 鏈的例子：前站轉給後站

一封請求可以走「寄件人 → 前站 → 後站 → daemon」。站不知道自己在鏈上，只知道信從哪來、`next` 寫要轉去哪。下面的後站用 `daemon-kernel` 範本原樣；前站是另一台 daemon，身體也是框架站，`kernel.json` 只寫兩個鍵：轉給後站、回信先回我。

```sh
mkdir -p $T/back && cd $T/back
aos-exec --stack $T/back/st $P/kernel/daemon-kernel &            # 後站

mkdir -p $T/front-def $T/front && cd $T/front                    # 前站的定義
echo '["aos-daemon", "daemon.json"]' > $T/front-def/_entry
echo '{"exec": {"argv": ["aos-exec", {"$env": "AOS_HOME", "$path": "/lib/aos/kernel"}, {"$env": "AOS_CD", "$path": "kernel.json"}]}, "interval_ms": 300}' > $T/front-def/daemon.json
echo "{\"next\": \"$T/back/st/requests\", \"reply_via_me\": true}" > $T/front-def/kernel.json
aos-exec --stack $T/front/st $T/front-def &                      # 前站

aos-post init $T/me/box3
# 寄 procs_added 的 kid 與 evil 到 $T/front/st/requests（都帶 --reply-to $T/me/box3）
aos-daemon-ctl -d $T/back/st ls                                  # _sweeper、kid 兩列 running：kid 掛在後站那台
cat $T/me/box3/new/*/letter.json
```

`kid` 的回信是 `{"applied": true}`，`evil` 的回信是後站回的 `NameUnknown`。兩封回信信封上的 `sender` 都是前站：因為前站開了 `reply_via_me`，後面的回信先回到前站的 `replies/`，再由前站用原信名代回。前站自己沒寫規則，所以它的 stderr 是空的；拒信那行 warning 印在後站。

### hook 的例子：前站多管兩件事

hook 是站在三個時機叫的小程式（設定寫在 `kernel.json` 的 `hooks`，契約跟 agent 的 hook 一樣，細節在 [lib/aos/kernel README「hooks」](../../lib/aos/kernel/README.md#hooks)）：

| 事件 | 什麼時候 | 能改什麼 |
|---|---|---|
| `before_verdict` | 一封新信、內建規則判之前 | 信的 `body`；退 10＝直接拒 |
| `after_verdict` | 判決定下來的那一刻 | 判決（只能改成 `pass` 或 `refuse`）與拒因 |
| `before_reply` | 下游回信到了、代回之前（要開 `reply_via_me` 才有） | 回信的 `body` |

接著上面的鏈，給前站加兩個 hook：`no_rm` 不准「收掉 proc」的信經過，`hide` 把代回的回信換成一句短的。事件 JSON 從 handler 的 stdin 進來。

```sh
mkdir -p $T/front-def/hooks
cat > $T/front-def/hooks/no_rm <<'EOF'
#!/bin/sh
# refuse letters that remove procs; everything else passes untouched
if grep -q procs_removed; then echo "rm is not allowed through this station"; exit 10; fi
EOF
cat > $T/front-def/hooks/hide <<'EOF'
#!/bin/sh
# replace every relayed reply with a short one
cat >/dev/null
printf '%s\n' '{"body": {"applied": true, "note": "via front"}}'
EOF
chmod +x $T/front-def/hooks/no_rm $T/front-def/hooks/hide
echo "{\"next\": \"$T/back/st/requests\", \"reply_via_me\": true, \"hooks\": {\"no_rm\": {\"event\": \"before_verdict\", \"handler\": \"hooks/no_rm\"}, \"hide\": {\"event\": \"before_reply\", \"handler\": \"hooks/hide\"}}}" > $T/front-def/kernel.json
```

設定每輪重讀，不用重起前站。再寄兩封到 `$T/front/st/requests`：

- `{"procs_removed": ["kid"]}`：被 `no_rm` 攔下，回信是 `{"applied": false, "error": {"code": "HookRejected", "msg": "rm is not allowed through this station"}}`，前站 stderr 一行 `kernel: warning: letter <信名> refused: HookRejected rm is not allowed through this station`。
- `procs_added` 的 `kid2`：照常轉給後站、掛上去；回信經過 `hide`，寄件人收到的是 `{"applied": true, "note": "via front"}`。

每個 hook 在前站的 stack 有自己的小格 `hooks/<名>/`，裡面的 `event.json` 是它最後一次收到的事件。收工：`aos-daemon-ctl -d $T/front/st shutdown`、`aos-daemon-ctl -d $T/back/st shutdown`，最後 `rm -r $T`。

### 改成自己的

複製範本資料夾、改 `kernel.json`。範本裡框架站的路徑寫成 `{"$env": "AOS_HOME", "$path": "/lib/aos/kernel"}`（`AOS_HOME`＝這台 proto8 資料夾的絕對路徑），搬到 repo 外不用改；設定檔用 `{"$env": "AOS_CD", "$path": "kernel.json"}` 指定義資料夾裡那份（aos-exec 會 cd 進框架站自己的資料夾，相對路徑會算錯）。

內建的規則只看得懂 `procs_*` 這一類。別種 body 要判，寫 `before_verdict` hook。要優先序、額度這種排程器，自己寫一個 kernel 身體（llm kernel 是範例）；可以照樣寫五個口交給骨架 `round.run()`，也可以只拿 `letters.py` 幾個零件自己組（[lib/aos/kernel README](../../lib/aos/kernel/README.md)）。

### 已知限制

- 沒開 `reply_via_me` 的無序信，防重的依據只有下一站信箱 `new/`、`cur/` 裡的同名信。下游已做完並移走那封信、站才重起，站認不出原信已經轉過，可能再轉一次。
- 站當 loop proc 時跟 daemon 各自打拍子：轉了、daemon 還沒套的不算在跑，連著很快寄好幾封時可能多放幾個。當 daemon 身體時沒這個問題（站跑在 daemon 那一圈裡，下一圈之前 daemon 已套完）。
- **當 loop proc 的站睡著或停著**：信照 `AOS_KERNEL` 寄、不認誰是 kernel、不預判收件者有沒有在跑；沒有回信就等寄件人期限。站睡著＝這是設計系統的人要管的風險（使用者 11-07），手動叫醒：`aos-daemon-ctl wake NAME`（停著用 `start`；這支是指名 daemon 的工具，一律直寄 daemon、不看 `AOS_KERNEL`）。程式不自動辨識、不自動叫醒、不自動繞過。逾時撤信與已轉寄後撤不回的競態見 [aos-agent 已知限制](../../cmd/aos-agent/docs/02-已知限制.md)。
- 站自己的錯（`kernel.json` 壞、沒 `AOS_DAEMON`、daemon 沒開 ctl 信箱、`on_error: stop` 的 hook 失敗）退 1。當 daemon 身體時 daemon 不停——stderr 一行 `aos-daemon: warning: body … failed (code N), retrying next round`（碼變了才印，好了印 ok again）、`state.json` 記 `body_code`、下一圈再跑（使用者裁「記一行、下一圈再跑 (Recommended)」，N-28「daemon 的身體失敗」）；那段時間站沒在跑、`requests/` 的信沒人判。當 loop proc 時那個 proc 出錯結束、表上留 `stopped`＋`reason`，修好 `start`（P-20）。
- 同一個收件箱同時只能有一個站在跑：第二個會拿不到 `requests/.flock`，報 `LockFailed` 退 1。
