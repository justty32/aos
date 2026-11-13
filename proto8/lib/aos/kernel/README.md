# 通用 kernel 的站：共用一輪骨架，掛 proc 的包負責規則、排隊與轉寄。

`_entry` 把 `procs_rules` 交給 `round.run(pack, cfg_path, name="kernel")`；每次執行做一輪，沒信也退 0。由 daemon 身體或 loop proc 一次次叫，不自己常駐。需要 `AOS_STACK`。下一站照三段找：`kernel.json` 的 `next`；沒寫看環境的 `AOS_KERNEL`（指到自己的 `requests/` 就跳過）；再沒有才用 `AOS_DAEMON`。三段都用不上＝`DaemonMissing`。`next` 只有一個；要照規則把不同的信轉給不同的下一站（一封只去一處），寫 `after_verdict` hook 替那一封指定，見下方「分流」。

## 零件怎麼用

| 檔案 | 工作 |
|---|---|
| `_entry` | 英文 help、參數、共用模組入口，呼叫骨架 |
| `round.py` | 讀設定、鎖 `requests/.flock`、派發三個 hook 時機、逐封套用判決 |
| `letters.py` | 包 aos-post：認領、看信、收信、轉寄、拒信、代回、轉寄對照與排隊 body |
| `hooks.py` | 三個事件的設定與回話規則，執行交給共用 hook_run |
| `hold.py` | 「先留著等表態」：留著的信的窗 `hold.json`、表態檔 `decisions/<信名>.json` |
| `procs_rules.py` | 掛 proc 的五個口、設定檢查、白名單與 running 上限 |
| `queue_fifo.py` | 先來先掛的排隊窗、寄件人期限與時間換算 |
| `runner.py` | 「自己跑」零件：把一件工作掛成 daemon 的 proc、看表收成品、逾時、重掛一次、拔列；去處由呼叫的包給 |

包提供 `collect(ctx, before_reply=None)`、`check(ctx)`、`order(ctx, letters)`、`admit(ctx, name, letter)`、`dispatch(ctx, name, letter, detail)`，以及 `load(cfg, cfg_dir)`、`refuse(ctx, name, letter, code, msg)`、`finish(ctx, queued)`。設定不對丟 `round.CfgBad`。包另外提供 `read(path)` 時，骨架改叫它讀設定、不走下面「整份先過 aos-directive」的讀法，hooks 也由包自己交給 `hooks.load` 驗（問腦那一包用：每組端點的指示詞用到才解）。骨架給的 `ctx` 有 `cfg`、`stack`、`requests`、`name`、`die`、`warn`、`previous`（上一輪的排隊列）與 `queued`（這輪已確定留隊的列）；包需要的輪內狀態自己加。

`admit` 回 `(verdict, detail)`：`pass` 的 detail 是新名字清單、`refuse` 是 `(code, msg)`、`queue` 是窗的一列。hook 從拒或排改成 pass 時，交給 `dispatch` 的 detail 是 None；包從 body 數實際轉出的名字，不回頭驗規則。`dispatch` 成功回 `None`，失敗回 `(code, msg)` 交骨架拒信。包的 `collect(ctx, before_reply=None)` 可傳代回前的回呼；每封對得上表的回信會以 `(原信記錄, 回信信封)` 呼叫，回傳要代回的 body。骨架在這個回呼派發 `before_reply`，三個時機都交給共用的 `lib/hook_run.py` 執行。

包另外提供 `check_next(ctx, box)` 時，骨架才收 `after_verdict` hook 替單封信指定的下一站：hook 給了就先叫它驗（設定配不上由包 `ctx.die`，這個值不能用丟 `ValueError`、算 hook 自己失敗），放行時路徑放在 `ctx.route[信名]`，包在 `dispatch` 取走。沒有這個口的包（問腦那一包，放行＝自己掛去跑、不轉寄）遇到 hook 給 `next` 算 hook 自己失敗。

包另外提供 `held(ctx, name, letter)` 時，骨架才收 `after_verdict` hook 的「先留著」（`hold`，見下方「先留著等表態」）：留著、還沒人表態的信每輪交給它，回 `None`＝繼續留，回 `(code, msg)`＝現在就拒。掛 proc 這一包的 `held` 只驗寄件人的期限。沒有這個口的包（問腦那一包）遇到 hook 回 `hold` 算 hook 自己失敗。

## kernel.json

每輪重讀，內容先過 `aos-directive --file <設定檔>`，cwd 是設定檔所在夾；相對路徑的普通字串從該夾轉成絕對。不認得的鍵略過。

| 鍵 | 值與作用 | 沒寫時 |
|---|---|---|
| `next` | 下一站信箱的非空路徑字串 | 環境有非空的 `AOS_KERNEL`、又不是自己的 `requests/`＝用它；否則 `$AOS_DAEMON` 表上 `procs_requests`，表未寫出來用 `procs_requests` |
| `count_daemon` | 數 running 的 daemon stack 路徑字串 | 下一站是從 `$AOS_DAEMON` 來的才用 `$AOS_DAEMON`；其他情形沒有預設 |
| `allowed` | `procs_added` 名字的字串陣列或 null | 不限 |
| `max_running` | 非負整數或 null | 不限 |
| `queue` | 布林，滿格是否留隊 | false |
| `keep_ordered` | 布林或 null，有序信是否仍以有序寄出；null 等同 false | false |
| `reply_via_me` | 布林，下游回信是否先寄到自己再代回 | false |
| `hooks` | `{名字: 一格}`，只讀這一份；格的鍵見下方 | 沒有 hook |

寫了 `next` 與 `max_running` 就須寫 `count_daemon`，即使上限值為 null；不猜下一站是哪台。下一站取自 `AOS_KERNEL` 時同理：寫了 `max_running` 卻沒寫 `count_daemon`＝`CfgBad`。`count_daemon` 必須是資料夾；表還沒有時 running 為 0，讀不懂時整輪報錯。只數 `running`、`stuck` 與本輪放行的新名字，在飛的信不算。數量另指時不看那台的 ctl 信箱。轉寄目標解開捷徑後若等於自己的 `requests/`，設定不成立。

下一站的三段（使用者 11-13 裁）：

1. 寫了 `next`：照字面用它。它解開捷徑後就是自己的 `requests/`＝`CfgBad`，不跳過。
2. 沒寫 `next`、環境有非空的 `AOS_KERNEL`：解開捷徑後等於自己的 `requests/` 就跳過這一段；否則下一站就是它（轉成絕對路徑，不讀任何表、不驗它在不在，寄不進去照 `ForwardFailed` 拒信）。這一段不需要 `AOS_DAEMON`。
3. 前兩段都沒有：`$AOS_DAEMON` 表上的 `procs_requests`。算出來是自己的 `requests/`＝`CfgBad`（有信那一輪才讀表、才報）。

三段都用不上（`AOS_DAEMON` 沒設或不是資料夾）＝`DaemonMissing`。兩站互指成環不偵測。

整棵樹 export `AOS_KERNEL` 時，沒寫 `next` 的站也會繼承到它：指到自己才跳過，指到別站就把信轉給那一站。不想要就在起那一站的殼 `unset AOS_KERNEL`，或明寫 `next`。

空輪照原本行為不讀 daemon 表。其他 body 原樣轉；未寫有效 `allowed`、`max_running` 且信未帶期限時，連 body 是不是物件也不驗。規則需要的 `procs_added` 必須是物件，`procs_started`、`procs_woken` 必須是字串陣列。

## 一輪順序

1. 讀設定、檢查 stack、建 requests 信箱，嘗試鎖 `requests/.flock`。
2. 認領信，先收掉已轉寄的原信：對照表同時比 key 與 `letter`；也看下一站 `new/`、`cur/` 的同名信（有序轉普通時比尾名）。不等回信的對照列隨原信收掉。
3. 收 replies，查表、跑 `before_reply`、代回；再認領並看 requests 的信封，壞信 warning 丟掉。
4. 已在隊的照原隊序先看，新信照 aos-post 順序（有序先、再名字）。新信先跑 `before_verdict`；隊中信讀回保存的 body，不重跑它。依序判期限、白名單、上限；新信判完跑 `after_verdict`，隊中信只有這輪出隊才跑。放行轉寄並收原信，拒信回 `{"applied": false, "error": {"code", "msg"}}` 並收原信，留隊繼續留在 cur。hook 回 `hold` 的信也留在 cur、不回信；之後每輪先看表態檔，沒人表態就不重判、不再問 hook（見「先留著等表態」）。
5. 改過 body 的新入隊信原子存到 `bodies/<信名>.json`；出隊轉寄或拒掉後刪掉。寫排隊窗（空隊也寫空陣列），釋放鎖、退 0。

`queue_wait_ms` 必須是非負整數。正數從本站收到的 `sent_at` 起算，過期即拒 `SlotMissing`，有格也拒；0 不算過期，有格照放行，沒格不排。隊首沒格會擋住後方要新格的信，不增加 running 的信照轉。隊中信每輪仍驗期限；`queued_at`、`queued_at_cycles` 續用，壞窗 warning 後當空窗、從 cur 重排。

## hooks

每格必填 `event`、`handler`；`handler` 是非空路徑字串或指示詞物件，相對路徑從 `kernel.json` 所在夾算。選填 `intercept`（預設 true）、`async`（預設 false）、`on_error`（stop／continue，預設 stop）、`timeout_ms`（正整數，預設 60000）。`condition` 是字串或字串陣列，只有 `after_verdict` 收，用來比 `verdict`。名字須非空、不含 `/`、不以 `.` 開頭；清單或格的形狀錯、事件名不認得，都是 `CfgBad`。掛 proc 這一包有 `before_reply` hook 時必須開 `reply_via_me`，由包的 `load` 檢查。

| 事件 | 時機與事件欄位 | 能改 |
|---|---|---|
| `before_verdict` | 新信在內建規則前；`letter`、`sender`、`sent_at`、`reply_to`、`body` | `body` |
| `after_verdict` | 新信判完一次；隊中信出隊再一次，繼續排不跑。上述欄位再加 `verdict`、`error`（拒信的 `{code, msg}`，否則 null）、`next`（null；只有會轉寄的包有這一欄）、`decision`（平常 null；留著的信有人表態 pass、重判那一次是 `"pass"`；只有收 hold 的包有這一欄） | `verdict`（pass／refuse／hold；hold 見「先留著等表態」）、`error`、`next`（這一封的下一站，見「分流」） |
| `before_reply` | 下游回信代回前；`letter`（原信名）、`sender`（原寄件人）、`reply_to`（原回信箱）、`reply_sender`、`body` | `body` |

每份事件 JSON 都有 `event`、`hook`、`stack`（站的 stack），沒有 `names` 等 proc 專用欄。事件從 handler 的 stdin 進，也留在 `hooks/<名>/event.json`；handler 經 `aos-exec --stack <小格>/ <handler>` 跑。同一事件照 hook 名字排序，前一個改過的內容後一個看得到。退 0、stdout 空＝不改；stdout 是 JSON 物件時只取允許改的鍵。`intercept: false` 或 `async: true` 是純通知，不看 stdout，退 10 也不攔。

`after_verdict` 的 condition 沿名單引擎的做法，先比這次內建判決來挑 hook；前一格改判，後一格仍會收到改過的判決。每格拒因的預設值在下一格之前補好。

三個事件退 10 都能攔。`before_verdict` 直接拒 `HookRejected`，不跑內建規則和 `after_verdict`；`after_verdict` 也拒 `HookRejected`。原因用 stdout 去頭尾空白，空則用 `blocked by hook <name>`。`before_reply` 改代回 `{"applied": false, "error": {"code": "HookRejected", "msg": "reply blocked by hook <name>: <stdout>"}}`。

`after_verdict` 改成 refuse 卻沒完整的 `error`（物件、`code` 與 `msg` 都是字串），補 `{"code": "HookRejected", "msg": "refused by hook <name>"}`。把 refuse 或 queue 改成 pass 就照放行，不回頭驗期限、白名單或上限；改成 hold＝先留著；其他 verdict 值算 hook 自己失敗。

hook 自己逾時、退非 0／10、起不來或回話不合：`on_error: stop` 印 `kernel: error: HookFailed ...`、這輪退 1，信留在 cur，下輪重來；`before_reply` 失敗時回信留在 replies/cur。只有上一輪已寫進 `queue.json` 的信算隊中信，其他信下輪仍跑 `before_verdict`。`continue` 印一行 warning、當沒這個 hook。async 放出去就不等結果。

最小例子：`kernel.json` 與可執行的 `rewrite` 放在同一夾，每封新信都換成這個 body。

```json
{"hooks": {"rewrite": {"event": "before_verdict", "handler": "rewrite"}}}
```

```sh
#!/bin/sh
# 把新信換成固定的 ping body。
cat >/dev/null
printf '%s\n' '{"body":{"ping":true}}'
```

### 分流：hook 替這一封指定下一站

使用者 11-13：「按照規則分流吧。就用hook」——`next` 維持一個；要照規則把不同的信轉給不同的下一站，寫 `after_verdict` hook，stdout 回 `{"next": "<信箱的絕對路徑>"}`。這一封放行時就寄到那裡、不寄站原本的下一站；一封信只去一處。沒回 `next`（或回 null）＝照原本三段。三個時機只有 `after_verdict` 收 `next`；另外兩個回了也不看。

最小例子：`kernel.json` 與可執行的 `route` 放同一夾。body 的 `lane` 是 `side` 的信寄到旁邊那一站，其餘照 `next`。

```json
{"next": "/srv/main/requests", "hooks": {"route": {"event": "after_verdict", "condition": "pass", "handler": "route"}}}
```

```python
#!/usr/bin/env python3
# 照信裡的 lane 欄替這一封挑下一站；不說話＝照站原本的下一站。
import json, sys
event = json.load(sys.stdin)
body = event["body"] if isinstance(event["body"], dict) else {}
if body.get("lane") == "side":
    print(json.dumps({"next": "/srv/side/requests"}))
```

- **何時生效**：只有這一封最後的判決是 pass 才用得上。判決是留隊時給的 `next` 不記；那封信出隊時 `after_verdict` 會再跑一次，那時給的才算。被拒的信不轉寄，給了也沒用。`condition` 比的是內建判決：寫 `"pass"` 的 hook 不會看到別的 hook 從拒改成放行的信；改判的那個 hook 可以自己一起回 `next`。
- **值**：非空的絕對路徑字串或 null。相對路徑、空字串、別的型別、解開捷徑後是自己的 `requests/`＝hook 自己失敗（照 `on_error`：stop 這輪退 1、信留著；continue 印 warning、當沒這個 hook，信照原本的下一站）。站不驗那個信箱在不在；寄不進去照 `ForwardFailed` 拒信。
- **站自己仍要有原本的下一站**：三段都用不上照舊 `DaemonMissing`，即使 hook 會替每一封指定。
- **回信**：跟沒分流時一樣。開 `reply_via_me` 時不管信去哪一站，下游都回到本站的 `replies/`，`forwarded.json` 照轉寄後的信名對回原信、代回原寄件人；對照表不記信去了哪一站。
- **數量上限**：站只在一個地方數（`count_daemon`），不知道 hook 指的站後面是哪台 daemon。hook 給了 `next`、設定有 `max_running`、卻沒寫 `count_daemon`＝`CfgBad`（沒寫 `next` 時原本預設數 `AOS_DAEMON`，這裡不沿用）。寫了就照字面：不管信去哪一站，都算進同一個上限。各站各自的上限要在各站自己的 `kernel.json` 設。
- **有序信**：分到不同站的信，站與站之間沒有先後保證。`keep_ordered` 開著時 hook 給 `next`＝`CfgBad`（另一個原因：各站各自編有序信名，兩站可能編出同名，代回的對照會撞）。沒開 `keep_ordered` 時有序信照處理順序逐封寄出、轉成普通信，「有序」只保證到本站門口。
- **防重**：寄進指定的站之後、原信還沒收掉就中斷：下一輪 hook 再指到同一站，站看到那一站的 `new/`、`cur/` 還有同名信就只收原信、不寄第二次。hook 這次指到別站就認不出來，所以分流規則要對同一封信每次給同一個答案。

### 先留著等表態：hook 回 `hold`，別人寫表態檔，機器轉寄

使用者 11-13：「請求進來後agent收到通知，他自己判斷要不要過，然後再去轉送」；四題回覆「1乙，總之先做。」＝重用框架站，加一個「先留著等表態」的口，判的人只表態、轉寄由機器做。

`after_verdict` hook 的 stdout 回 `{"verdict": "hold"}`：這一封留在 `requests/cur/`，不轉寄、不回信，記進 `hold.json`。誰來判、怎麼通知他，站不管（hook 自己通知，或別的程式看 `hold.json`）。判的人把答案寫成一個檔 `<站的 stack>/decisions/<信名>.json`（先寫暫存檔再改名）：

```json
{"verdict": "pass"}
{"verdict": "refuse", "error": {"code": "NotNow", "msg": "say what it is for"}}
```

下一輪站看到表態檔就照做：

- `refuse`：回拒信 `{"applied": false, "error": …}`、收原信。`error` 沒寫或不完整（要物件、`code` 與 `msg` 都是字串）＝`{"code": "HoldRefused", "msg": "refused by the decision for this letter"}`。不再問 hook。
- `pass`：這一輪把這封信**重判一次**——內建規則照跑（期限、白名單、上限、排隊），`after_verdict` 再跑一次（事件的 `decision` 是 `"pass"`，這一次 hook 再回 `hold` 不算數、照那一格之前的判決走；分流的 `next` 這時給才算），之後照平常放行、拒或排隊。所以表態 pass 蓋不過規則：規則會拒的信照樣拒。放行走的是平常那條轉寄路（下一站三段、分流、代回、防重、臨轉寄再驗期限）。
- 沒有表態檔：繼續留著。不重判、不再問 hook、`before_verdict` 也不重跑（改過的 body 存在 `bodies/<信名>.json`，跟排隊的信一樣）。

其他：

- **寄件人的期限**：留著的信每輪驗 `queue_wait_ms`（從 `sent_at` 起算）。過了就拒 `SlotMissing`、原因 `held N ms, nobody decided in time (queue_wait_ms N)`，不等表態；期限過了才寫的 pass 不放行。沒帶期限的信一直留到有人表態。站沒有自己的「最多留多久」；要的話寫在通知或表態那一側。
- **哪些信會被留**：hook 自己決定。`condition: "pass"` 的 hook 只看內建規則放行的信，規則拒的直接拒、不留；不寫 condition 就連規則拒的、排隊的都看得到（留了規則拒的信，有人說 pass 時規則還是會拒）。
- **表態後沒格**：開著 `queue` 時進排隊窗，表態檔留著；出隊那一次 hook 回 `hold` 一樣不算數。排隊中的信有表態檔也算數（`refuse`＝現在拒）。
- **不算進數量上限**：留著的信不佔格、不擋後面的信。
- **站重起**：`hold.json`、表態檔、`bodies/` 都在 stack 裡，重起後照舊。`hold.json` 讀不懂＝warning、當沒有留著的信，cur 裡那些當新信重判（hook 會再被問一次）。表態檔讀不懂或 `verdict` 不是 pass／refuse＝warning、刪掉那個檔、信照舊留著。
- **站裡沒有這封信的表態檔**（信已離站、或信名打錯）：每輪收尾時刪掉。
- **只有掛 proc 這一包收 `hold`**；問腦那一包沒有 `held` 這個口，hook 回 `hold` 算 hook 自己失敗。

最小例子：機器先照 `kernel.json` 的規則判，規則放行的信裡只有帶 `desc` 的留給人看，其餘直接放行。`kernel.json` 與可執行的 `ask` 放同一夾。

```json
{"allowed": ["worker"], "hooks": {"ask": {"event": "after_verdict", "condition": "pass", "handler": "ask"}}}
```

```python
#!/usr/bin/env python3
# 規則放行的信裡，帶 desc 的先留著等人表態；不說話＝照規則的判決走。
import json, sys
event = json.load(sys.stdin)
body = event["body"] if isinstance(event["body"], dict) else {}
if "desc" in body:
    print(json.dumps({"verdict": "hold"}))
```

`keep_ordered` 與 `reply_via_me` 各自獨立。有序轉寄會產生新信名；只開保有序時，下游直接回的 `in_reply_to` 會是新信名。開代回且原信有 `reply_to` 才改成自己的 replies；代回時以原信名當 `in_reply_to`。原回信箱以絕對路徑記錄，不留原 body。

代回寄不進去或原信箱已不在：warning、刪對照、收掉回信，不重試。找不到對照的回信也 warning 丟掉。下游一直不回的對照列不自動清。沒開代回的無序信，若下游已做完移走、原信又還沒收掉就重起，仍可能重轉。

## 站的 stack

```text
requests/          對外收件箱，AOS_KERNEL 指這裡
  .flock           一輪的互斥鎖
queue.json         {"queued": [{letter, names, queued_at, queued_at_cycles?, expires_at?}]}
hold.json          {"held": [{letter, held_at, held_at_cycles?, expires_at?}]}，留著等表態的信
decisions/<信名>.json 別人對留著的那一封的表態 {"verdict": "pass"} 或 {"verdict": "refuse", "error"?}，站照做後刪
bodies/<信名>.json before_verdict 改過且還在排隊的 body，原子寫入、出隊後刪
replies/           下游回信箱
forwarded.json     {轉寄後信名: {"letter": 原信名, "reply_to": 原信箱或null, "sender": 原寄件人}}
hooks/<名>/        hook 小格，event.json 是最後一次事件
```

開 `queue` 或既有窗存在時寫窗。改過的 body 不放進公開的 queue.json；之後每輪從 bodies/ 讀回來判。開代回或已有回信／對照時收 replies。保有序時不管原信有沒有 `reply_to` 都先記防重列；沒有代回需求的列 `reply_to` 是 null，原信收掉即刪。

關掉 `queue` 後仍讀上一輪的窗，沿用隊中身分與保存的 body，這輪依新設定決定放行或拒掉。隊中信沒有 body 檔時用原信（沒有改 body 的信本來就不另存）；檔存在卻讀不懂、讀寫或刪除失敗則退 `StateBad`。

## 錯誤代號

自己的錯印 `kernel: error: CODE reason`，退 1；拒信印 `kernel: warning: letter NAME refused: CODE reason` 並回信，一輪仍退 0。下層 stderr 直接放行，不讀來猜錯。

| 自己的代號 | 原因 |
|---|---|
| `ArgumentsBad` | 不是恰好一個非空設定檔參數 |
| `CfgMissing` | 設定檔不存在 |
| `CfgBad` | 設定讀不懂、鍵的型別錯、缺數量來源（寫了 `next`、下一站取自 `AOS_KERNEL` 或 hook 替單封信給了 `next`，有 `max_running` 沒 `count_daemon`）、開著 `keep_ordered` 時 hook 給了 `next`、轉寄目標是自己，或 hooks 設定不合 |
| `StackMissing` | 沒設 AOS_STACK |
| `DaemonMissing` | 下一站三段都用不上（沒寫 `next`、`AOS_KERNEL` 沒設或指到自己、`AOS_DAEMON` 未設或不是資料夾），或 `count_daemon` 不是資料夾 |
| `StateBad` | daemon 表、轉寄對照讀不懂，或對照／窗／保存的 body 讀寫不了 |
| `MailboxMissing` | 目標 daemon 的表明寫 procs_requests 為 null |
| `CommandMissing` | aos-post 或 aos-directive 起不來 |
| `PostFailed` | 建信箱、認領、看信或收信失敗 |
| `LockFailed` | 不能取得 requests/.flock |
| `HookFailed` | on_error: stop 的 hook 自己失敗，信留著下一輪重來 |

| 拒信代號 | 原因 |
|---|---|
| `BodyBad` | 規則要看的 body、期限或時間格式不對 |
| `NameUnknown` | procs_added 名字不在 allowed |
| `SlotMissing` | 期限已過（含留著等表態等到過期）或沒有足夠格子且不能排 |
| `HoldRefused` | 留著的信被表態拒絕、表態檔沒給完整的 error（給了就用它的 code 與 msg） |
| `ForwardFailed` | 下一站（站原本的，或 hook 替這一封指定的）信箱不在或寄不進去 |
| `HookRejected` | hook 攔下請求或回信，或改判拒絕但沒有完整 error |

## runner（自己跑）

給「放行＝自己掛去跑」的包用（問腦那一包 [`lib/aos/kernel_llm`](../kernel_llm/README.md)）；掛 proc 那一包用不到。它不決定掛信寄去哪：呼叫的包給掛信信箱 `box` 與 daemon 的 stack `daemon`。一件工作一個資料夾 `job`，也是那個 proc 的 stack 與 cwd；工作的狀態記在 `job/proc.json`（`name`、`exec`、`mount_letter`、`mounted_at`、`retries`，等舊列拔掉時多 `remount`、被人停著時多 `stopped_seen_at`；包自己的鍵原樣留著）。

- `mount(job, name, target, proc, box, daemon, timeout_ms=None)`：寄 `{"procs_added": {name: {"exec": {argv: ["aos-exec", 目標], cwd, stdin: "request.json", stdout: "reply.json", timeout_ms?}, "max": 1, "stack": job}}}`、寫 `proc.json`。目標寫成相對 `AOS_DAEMON`。寄不進丟 `runner.Failed(code, msg)`。
- `read_table(daemon)`：回 `(列, mailbox_warning)`；窗不在或讀不懂當空的。
- `settle(job, proc, table, box, daemon, timeout_ms=None, name=None, target_for=None, accept=None, give_up_s=300)`：回 `None`＝還在飛（睡著的列、daemon 還沒套的掛信都算）。跑完回 `{"kind": "exit", "code", "timed_out"}`，成品在 `job/reply.json`、`job/stderr.txt`，並順手寄 `procs_removed`。被收掉、死在半路、沒到時限的 143 重掛一次（列還在就先拔、下一輪才掛），第二次回 `{"kind": "twice"}`。daemon 的 `mailbox_warning` 提到那封掛信或重掛信寄不進回 `{"kind": "launch", "msg"}`。列被人 stop 超過 `give_up_s` 回 `{"kind": "stopped", "name", "seconds"}`。`proc.json` 寫不了回 `{"kind": "write", "msg"}`。`accept(code)` 讓包說「退非 0 但這份成品我認」；`target_for(proc)` 讓包在重掛時重算目標。
- 怎麼把結果說成回信（代號、訊息）是包的事。
