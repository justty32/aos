# 通用 kernel 的站：共用一輪骨架，掛 proc 的包負責規則、排隊與轉寄。

`_entry` 把 `procs_rules` 交給 `round.run(pack, cfg_path, name="kernel")`；每次執行做一輪，沒信也退 0。由 daemon 身體或 loop proc 一次次叫，不自己常駐。需要 `AOS_STACK`；沒寫 `next` 時也需要 `AOS_DAEMON`。

## 零件怎麼用

| 檔案 | 工作 |
|---|---|
| `_entry` | 英文 help、參數、共用模組入口，呼叫骨架 |
| `round.py` | 讀設定、鎖 `requests/.flock`、依序呼叫包、逐封套用判決 |
| `letters.py` | 包 aos-post：認領、看信、收信、轉寄、拒信、代回、轉寄對照 |
| `procs_rules.py` | 掛 proc 的五個口、設定檢查、白名單與 running 上限 |
| `queue_fifo.py` | 先來先掛的排隊窗、寄件人期限與時間換算 |

包提供 `collect(ctx)`、`check(ctx)`、`order(ctx, letters)`、`admit(ctx, name, letter)`、`dispatch(ctx, name, letter, detail)`，以及 `load(cfg, cfg_dir)`、`refuse(ctx, name, letter, code, msg)`、`finish(ctx, queued)`。設定不對丟 `round.CfgBad`。骨架給的 `ctx` 有 `cfg`、`stack`、`requests`、`name`、`die`、`warn`；包需要的輪內狀態自己加。

`admit` 回 `(verdict, detail)`：`pass` 的 detail 是新名字清單、`refuse` 是 `(code, msg)`、`queue` 是窗的一列。`dispatch` 成功回 `None`，失敗回 `(code, msg)` 交骨架拒信。包的 `collect(ctx, before_reply=None)` 可傳代回前的回呼；每封對得上表的回信會以 `(原信記錄, 回信信封)` 呼叫，回傳要代回的 body。這版沒有 hook 派發；`hooks` 當不認得的設定鍵，不驗也不執行。

## kernel.json

每輪重讀，內容先過 `aos-directive --file <設定檔>`，cwd 是設定檔所在夾；相對路徑的普通字串從該夾轉成絕對。不認得的鍵略過。

| 鍵 | 值與作用 | 沒寫時 |
|---|---|---|
| `next` | 下一站信箱的非空路徑字串 | `$AOS_DAEMON` 表上 `procs_requests`；表未寫出來用 `procs_requests` |
| `count_daemon` | 數 running 的 daemon stack 路徑字串 | 沒寫 `next` 時用 `$AOS_DAEMON` |
| `allowed` | `procs_added` 名字的字串陣列或 null | 不限 |
| `max_running` | 非負整數或 null | 不限 |
| `queue` | 布林，滿格是否留隊 | false |
| `keep_ordered` | 布林或 null，有序信是否仍以有序寄出；null 等同 false | false |
| `reply_via_me` | 布林，下游回信是否先寄到自己再代回 | false |

寫了 `next` 與 `max_running` 就須寫 `count_daemon`，即使上限值為 null；不猜下一站是哪台。`count_daemon` 必須是資料夾；表還沒有時 running 為 0，讀不懂時整輪報錯。只數 `running`、`stuck` 與本輪放行的新名字，在飛的信不算。數量另指時不看那台的 ctl 信箱。轉寄目標解開捷徑後若等於自己的 `requests/`，設定不成立。

空輪照原本行為不讀 daemon 表。其他 body 原樣轉；未寫有效 `allowed`、`max_running` 且信未帶期限時，連 body 是不是物件也不驗。規則需要的 `procs_added` 必須是物件，`procs_started`、`procs_woken` 必須是字串陣列。

## 一輪順序

1. 讀設定、檢查 stack、建 requests 信箱，嘗試鎖 `requests/.flock`。
2. 認領信，先收掉已轉寄的原信：對照表同時比 key 與 `letter`；也看下一站 `new/`、`cur/` 的同名信（有序轉普通時比尾名）。不等回信的對照列隨原信收掉。
3. 收 replies，查表代回；再認領並看 requests 的信封，壞信 warning 丟掉。
4. 已在隊的照原隊序先看，新信照 aos-post 順序（有序先、再名字）。逐封依序判期限、白名單、上限：放行轉寄並收原信，拒信回 `{"applied": false, "error": {"code", "msg"}}` 並收原信，留隊繼續留在 cur。轉寄前再驗一次期限。
5. 寫排隊窗（空隊也寫空陣列），釋放鎖、退 0。

`queue_wait_ms` 必須是非負整數。正數從本站收到的 `sent_at` 起算，過期即拒 `SlotMissing`，有格也拒；0 不算過期，有格照放行，沒格不排。隊首沒格會擋住後方要新格的信，不增加 running 的信照轉。隊中信每輪仍驗期限；`queued_at`、`queued_at_cycles` 續用，壞窗 warning 後當空窗、從 cur 重排。

`keep_ordered` 與 `reply_via_me` 各自獨立。有序轉寄會產生新信名；只開保有序時，下游直接回的 `in_reply_to` 會是新信名。開代回且原信有 `reply_to` 才改成自己的 replies；代回時以原信名當 `in_reply_to`。原回信箱以絕對路徑記錄，不留原 body。

代回寄不進去或原信箱已不在：warning、刪對照、收掉回信，不重試。找不到對照的回信也 warning 丟掉。下游一直不回的對照列不自動清。沒開代回的無序信，若下游已做完移走、原信又還沒收掉就重起，仍可能重轉。

## 站的 stack

```text
requests/          對外收件箱，AOS_KERNEL 指這裡
  .flock           一輪的互斥鎖
queue.json         {"queued": [{letter, names, queued_at, queued_at_cycles?, expires_at?}]}
replies/           下游回信箱
forwarded.json     {轉寄後信名: {"letter": 原信名, "reply_to": 原信箱或null, "sender": 原寄件人}}
```

開 `queue` 或既有窗存在時寫窗。開代回或已有回信／對照時收 replies。保有序時不管原信有沒有 `reply_to` 都先記防重列；沒有代回需求的列 `reply_to` 是 null，原信收掉即刪。

## 錯誤代號

自己的錯印 `kernel: error: CODE reason`，退 1；拒信印 `kernel: warning: letter NAME refused: CODE reason` 並回信，一輪仍退 0。下層 stderr 直接放行，不讀來猜錯。

| 自己的代號 | 原因 |
|---|---|
| `ArgumentsBad` | 不是恰好一個非空設定檔參數 |
| `CfgMissing` | 設定檔不存在 |
| `CfgBad` | 設定讀不懂、鍵的型別錯、缺數量來源或轉寄目標是自己 |
| `StackMissing` | 沒設 AOS_STACK |
| `DaemonMissing` | 所需 daemon 未設或不是資料夾 |
| `StateBad` | daemon 表、轉寄對照讀不懂，或對照／窗寫不了 |
| `MailboxMissing` | 目標 daemon 的表明寫 procs_requests 為 null |
| `CommandMissing` | aos-post 或 aos-directive 起不來 |
| `PostFailed` | 建信箱、認領、看信或收信失敗 |
| `LockFailed` | 不能取得 requests/.flock |

| 拒信代號 | 原因 |
|---|---|
| `BodyBad` | 規則要看的 body、期限或時間格式不對 |
| `NameUnknown` | procs_added 名字不在 allowed |
| `SlotMissing` | 期限已過或沒有足夠格子且不能排 |
| `ForwardFailed` | 下一站信箱不在或寄不進去 |
