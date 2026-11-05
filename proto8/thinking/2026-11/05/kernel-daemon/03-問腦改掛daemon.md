← [入口](README.md)｜涵蓋：llm kernel 收信→請 daemon 掛問腦 proc→收結果→回信：掛信形狀、一拍流程、完成判定、slots、逾時、失敗、kernel 睡醒、kernel.json 改動｜上一份 [02-兩種模式](02-兩種模式.md)｜下一份 [04-邊緣狀況](04-邊緣狀況.md)

# 問腦改成 daemon 底下的 proc（fable 照原則定的細節，可翻案）

對外不變：請求信 `{"endpoint"?, "request", "priority"?}`、回信 `{"message","usage","model"}`／`{"error"}`、`aos-llm send／recv／ask／regret`（11-04 定）。只改 aos-llm-kernel 裡「跑一封」那一段：**fork＋`run_inst` → 寄一封掛信給 daemon、下一拍收**。endpoint 函數（`lib/base/llm_http`、`llm_fake`）的 stdin／stdout 契約不動。

## 1 掛信（kernel → daemon 的 ctl 信箱）

挑到一封請求信 `<id>`（信在 `mailbox/cur/<id>/`，已寫好 `request.json`＝那組設定解好指示詞＋`request`）之後，寄進 `$AOS_KERNEL`（沒設＝`$AOS_DAEMON/procs_state.json` 回報的 `procs_ctl_mailbox`，[02/01 § 4](02-兩種模式/01-唯一-AOS_KERNEL-命名.md)）：

```json
{"procs_added": {"llm_<id>": {
   "exec": {"argv": ["aos-exec", "<那組的 exec，絕對路徑>"],
            "stdin": "<cur/<id>/request.json，絕對>", "stdout": "<cur/<id>/reply.json，絕對>",
            "timeout_ms": 120000},
   "max": 1,
   "stack": "<cur/<id>，絕對>"}}}
```

- **loop 型、`max: 1`**（不用 exec 型）：子 aos-loop 在 stack 寫 `state.json`，跑完有 `phase`＝`done`／`stopped` 與 **`code`**（10-14「結果從 state 窗讀」），exec 型結束就下表、結束碼拿不到；loop 型 daemon 收工時留 `sleeping`、開門自己醒＝問腦自動重跑（11-03「輕鬆回復原本狀態」）；aos-daemon docs 02 本來就說「要一次性的東西能停，寫成 `max: 1` 的 loop」。多一支 aos-loop＝開銷不算啥。
- **內嵌單子**：`stdin`／`stdout` 是 inst 現成的 key（aos-exec 認的 16 個之一）、絕對路徑所以不靠 `cwd`；`timeout_ms`＝kernel.json 的 `timeout_ms`（沒寫就不放這個 key＝不限）；stderr 不寫——daemon 本來就把子項的 stderr 接到 `<stack>/stderr.txt`，同一個資料夾。`argv[0]` 直接寫 `aos-exec`（少用 sh，user/03）。
- **`stack`＝那封信的資料夾**（11-04 定「stack＝那封信的資料夾」照舊）：endpoint 函數的 `$AOS_STACK` 不變；daemon 會在那裡多寫 `loop.json`、`state.json`、`stderr.txt`，跟 `request.json`／`reply.json` 並排。不寫 `ws`（繼承 daemon 的）、不寫 `def`（這不是 agent；aos-agent 對這列會 `InterfaceMissing`，天然）。
- **名字 `llm_<id>`**：`<id>`＝信件名稱（UTC 奈秒.pid.ticks，體系內唯一），只含數字與 `.`，過 `check_name`（不准 `/`、`#`、開頭 `.`）。兩台 kernel 掛同一台 daemon 也不撞。
- **`reply_to`**＝kernel 自己 stack 裡的 `daemon_reply/`（aos-post 庫開，沒有才建）：daemon 套完回 `{"applied": true}`、`in_reply_to`＝掛信名；壞信不回（daemon 現狀）。
- 掛信的名稱、寄出時間、重試次數寫進 `cur/<id>/proc.json`＝`{"name", "mount_letter", "mounted_at", "retries"}`（N-05 先暫存再改名）。這封請求信從此是「在飛」。

## 2 kernel 一拍（一次跑完就結束，C-47 照舊）

今天一拍＝挑→fork→等全部跑完→回信。改成不等：

1. 鎖 `mailbox/.flock`（照舊；搶不到＝`LockFailed`，11-04 夜使用者「自擔」照舊）。
2. **收成品**（原 `recover`）：逐個 `cur/<id>/`（有 `proc.json` 的＝在飛）→ 讀 `<id>/state.json`：
   - `phase`∈`done`／`stopped` → **完成**：`code` 0 且 `reply.json` 讀得懂＝回信 body；`code` 0 但讀不懂＝`ReplyBad`；`code` 非 0＝`EndpointFailed`，msg＝`reply.json` 非空就取它第一行（llm_http 失敗時 stdout 也印同一行）、否則 `stderr.txt` 第一行（這是 kernel 自己叫 daemon 收的檔，不是偷讀下層）、再否則「退 N」；`code` 143／`signal`＝逾時或被收掉：`mounted_at`＋`timeout_ms` 已過＝`EndpointFailed 逾時`，沒過＝被收掉→§ 5。
   - 沒有 `state.json`、或 `phase` 不是收尾的 → 看 daemon 的表 `$AOS_DAEMON/procs_state.json`（aos-directive 解 `$ref`，切檔也讀得到）：**列在**＝還在跑（算一格 busy）；**列不在**＝(a) `daemon_reply/` 有這封掛信的 `applied` 或 `proc.json` 記過 `seen: true`→ 跑過但沒留收尾＝死在半路（kill -9）→§ 5；(b) 都沒有＝daemon 還沒套（或暫停中、或拒了：`mailbox_warning` 提到這封掛信名＝`LaunchFailed`，回信、刪）→ 繼續等、照算一格。
   - 完成的：照 `reply_to` 寄回信、記 `used.json`、整封刪（11-04 夜「舊信根本不用留」照舊；`reply_letter.txt` 防重寄照舊）。
3. 收新信 `new/`→queue、排序（級數→deadline→等得久→先寄）、`DeadlineMissed`／`BudgetMissing` 照舊回信刪信。
4. **補位**：在飛數 < `slots` 就挑下一封：解指示詞寫 `request.json`→寫 `proc.json`→寄掛信。一拍可以掛好幾封（到 `slots` 為止）。
5. 寫 `queue.json`、`used.json`，結束。

一拍不再卡住：「一次裡不補位」的已知限制自然消失；kernel 死在半路不再回 `RunFailed`（在飛的接著等）。多出的拍距（kernel 300＋daemon 200 ms）＝使用者「開銷不算啥」。

## 3 slots、額度、排序

`slots`＝同時在飛的封數（跨拍計數＝`cur/` 裡有 `proc.json` 的）；`budget`、優先序、`priority.deadline` 全照舊；token 從 `reply.json` 的 `usage` 記、`AOS_KERNEL_REPORT` 已退場。C-20「誰先用腦」仍在這裡：排的是「哪封先請 daemon 掛」。

## 4 kernel 自己睡著、醒來、暫停、被拔

- **llm daemon 收工（Ctrl-C）**：身體不再跑；在飛的問腦 loop 被 SIGTERM、列留 `sleeping`（都是它自己這台的 proc）；開門 wake→問腦從頭跑一次（`max: 1` 的 loop 重起＝重跑單子）、寫新的 `state.json`→身體下一拍收。等待的 agent 這段一直停在 wait（跟今天 kernel 不在同義）。
- **kernel 當 proc 掛在別台 daemon 上**（舊佈局）：kernel 的 loop 睡下、它掛的問腦 loop 也睡下，同上。kernel 的 loop 被 `pause`／`stop`：問腦照跑完、成品留在 `cur/`，resume／start 後那拍收。kernel 被 `rm`：問腦照跑完、列下表；再 `add` 同名 kernel＝接回同一個 stack、收成品。
- **daemon 睡著時另一台 agent daemon 照寄請求信**：堆在 `new/`，醒來照收。

## 5 死在半路、被收掉：重掛一次

`state.json` 說被訊號收掉但沒逾時、或跑過卻沒收尾、或列不見了又沒 `applied`——都是「沒答案、沒錯誤」。代定：**`retries` 0→1 重掛同一封**（新的掛信、同名——列已不在才會走到這裡；若 `sleeping` 列在表上就不重掛、等它自己醒）；**第二次仍沒答案＝`EndpointFailed 問腦跑了兩次都沒結果`**。可能多花一次腦（端點收到了、回信沒落地）——使用者口徑「風險自擔」，不加機制。

## 6 kernel.json 與環境

- 新：讀 **`AOS_DAEMON`**（沒設＝`DaemonMissing`，退 1，loop 停、P-20；使用者「不在任何 daemon 下的我們不管」；demo 的「直接跑」說明改掉，[01 第 8 列](01-現況對照.md)）、讀 **`AOS_KERNEL`**（選填，有＝掛信寄這裡，[02/01 § 4](02-兩種模式/01-唯一-AOS_KERNEL-命名.md)）。
- **`mailbox` 這個 key 拿掉**：信箱固定在 `$AOS_STACK/mailbox/`（[07 § 2](07-llm-daemon佈局.md)：`AOS_LLM_KERNEL`＝stack，寄信的人要能從 stack 算出信箱）。寫了照 C-48 不看。
- `exec`、`endpoints`、`endpoint`、`slots`、`budget`、`timeout_ms` 照舊；`exec` 轉絕對後寫進掛信（daemon 從自己的 cwd 算相對路徑，kernel 不靠它）。
- endpoint 函數的環境＝daemon 給子項的（`AOS_STACK`＝信資料夾、`AOS_DAEMON`、daemon 的 `AOS_WS`、daemon 殼裡的其他變數），**不再是 kernel 的**；金鑰已經解進 `request.json`，不受影響。函數要別的環境變數（代理、憑證）＝寫進 daemon 的 `.env` 或函數自己的 `.env`。
- 新代號：`DaemonMissing`（現成共用）、`LaunchFailed` 沿用（daemon 拒掛）、`MailboxMissing`（daemon 沒開 ctl 信箱：`procs_state.json` 的 `procs_ctl_mailbox` 是 null）。拿掉：`RunFailed`（不再有「殘骸」）、`runner.json`。
