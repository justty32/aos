# aos-agent：走一格、登記、取消登記（第 2 版，2026-09-24 定稿（astra 三輪審查＋第 4 輪補 3 條）；程式未跟）

← [proto5 README](../README.md)｜資料夾：[agent.md](agent.md)｜問模型：[aos-llm-call.md](aos-llm-call.md)｜送件：[kernel.md §2](kernel.md)、[cpu.md §3](cpu.md)

> 2026-09-23 草稿；2026-09-24 照 [審查報告](../notes/2026-09-23-rearch/review-agent1-report.md)「定稿前必改」與使用者三件裁決改成第 2 輪；同日照 [第 2 輪審查](../notes/2026-09-23-rearch/review-agent2-report.md) E／D／B／C 改成第 3 輪；照 [第 3 輪審查](../notes/2026-09-23-rearch/review-agent3-report.md) D 節補 3 條（第 4 輪）後定稿。
> **程式還沒照這份改**：現行 `aos_agent.py` 仍是舊架構（直接往 llm cpu／tool cpu 放單）。
> 調度者裁決在下一節，已拍板的前提在 §14。

一句話：**`aos-agent tick` 每次只送出或接回一批工作，更新記憶與進度後就退出；結果還沒到就保留進度，留給下一次。**
問模型、跑工具都是往 kernel `add --once` 的普通工作；反覆叫 `tick` 是 kernel 的事——`aos-agent start` 把它登記成一個反覆行程。

## 調度者裁決（第 2～3 輪，實作層級）

1. 送件前先把當批寫進 `state.batch`（`sent:false`），全送完才標 `sent:true`；崩了用 §5.2 的四步查「放過沒」，不盲目重送。
2. 收回時先讀驗、把結果寫進 `done`，才 ack；記憶一律寫成「前 `base_len` 則＋這批」，重做不會重複接。
3. `work/` 檔什麼時候刪，看 K 帳本的 `procs` 還有沒有那個名字（§10）；被 `rm` 還在跑的工作跑完前不刪。
4. 子命令化：`aos-agent tick|start|stop [dir]`；`tick.json` 由 `start` 寫，把 `AOS_K` 寫進它的 `envs`。
5. 工作名 `aw-<資料夾名>-<epoch ns>-<pid>-<i>`，think 也帶 `-0`；前綴 `aw-` 避開 `ack-`／`stop-`。
6. 壞模型輸出、`Removed`、`Interrupted`、逾時、非 0 都算一次連敗；`Stopping` 與 `stopped:true` 不算、下次重問。
7. 連敗暫停的訊號檔每次不同名：`continue-<批 id>.json`（第 3 輪；不用分新舊訊號）。
8. 工具 `kind=aos` 給模型固定一句話、指向 cpu.log，不把診斷塞進結果。

## 0. 名詞（白話）

| 詞 | 意思 |
|---|---|
| 走一格 | 叫一次 `aos-agent tick`：最多做一件事（收輸入、送一批、收回一批並結清）就退出 |
| 門 | `state.json` 的 `waits`，外人的等待表（[agent.md §4.2](agent.md)） |
| 當批 | `state.batch`：一次送出、一起收回的工作（[agent.md §4.3](agent.md)） |
| 工作名 N | 一件工作的名字。**三種名字寫死**：kernel 行程名＝`N`；放進 `K/requests/` 的 request 檔名＝`N.json`（回音就出現在 `K/responses/N.json`）；ack 的 `params.name`＝`N.json`。`work/` 裡的檔是 `N.inst.json`、`N.in`、`N.out` |
| 批 id B | `aw-<agent 資料夾名>-<epoch ns>-<pid>`；第 i 個 call 的工作名是 `B-<i>` |
| 放單／回音／ack | 放單＝往 `K/requests/N.json` 放 `add`（tmp＋`link`，[cpu.md §3.1](cpu.md)）；回音＝`K/responses/N.json` 的執行狀態，答案在 `work/N.out`；ack＝結果寫進 `done` 後放的 notification（[cpu.md §3.3](cpu.md)） |
| K | kernel 家。只有 §5.1 建批那一刻讀 `AOS_K`（絕對路徑）記進 `batch.kernel`；之後送件（含崩了重送）、收回、ack、清檔一律用 `batch.kernel` |

## 1. 用法

```
aos-agent tick  [dir]
aos-agent start [dir]
aos-agent stop  [dir]
```

`dir` 留空＝`.`，必須是 agent 家（`NotAnAgent`）。三個子命令都要 `AOS_K`：沒設或不是絕對路徑＝用法錯 2。沒有別的旗標。

## 2. 一次 `tick` 的順序

1. 讀驗 `info.json`、`state.json`、記憶、工具檔（[agent.md](agent.md)）。不過＝退 1，**什麼都不寫**。
2. `consuming` 非空 → 逐對照 [agent.md §4.4](agent.md) 的搬法搬（`dst` 在就不碰 `src`）→ 寫 `consuming: []`。
3. 清檔（§10），盡力做，K 的帳本讀不到就跳過。
4. 看門（§3）。沒開＝退 101。
5. `batch` 不是 `null` → 收回（§6），全收齊就接著結清（§7）。不管 `state` 是什麼，有批先收批。
6. `batch` 是 `null` → 照 `state`（§4）。

第 2 步以後崩了，下次從第 1 步重來；每一步做到一半都能照 `batch`／`intake`／`consuming`／`sweep` 接下去。

## 3. 門

1. 逐條解（中心 agent 家）、逐條看到了沒（[agent.md §4.2](agent.md)）。解不開＝讀驗錯，退 1。
2. 有到了的：取一個新的消費 id，**一次寫** `state.json`——到了的條目從 `waits` 劃掉（按索引），其中開 `consume` 的，把要搬的檔（資料夾就是當下裡面所有 `*.json`）
   以 `{"src": 絕對路徑, "dst": "<src>.<消費 id>.done"}` 加進 `consuming`。然後照第 2 節第 2 步搬、清 `consuming`。
3. 表還有剩＝退 101（有劃掉的已經寫回，進度留著）；表空了＝往下走。

崩在「劃掉」之後、搬完之前：`consuming` 裡有記，下次第 2 步補做，不會又被同一道門關住；已經搬過的（`dst` 在）不會再去動原路徑上新放的同名檔。
人要它暫停：加一條指到不存在的檔（例如 `{"$opt":"consume","$val":"continue.json"}`）；要它繼續：touch 那個檔。
門關著時當批也不收：回音留在 K，開門後再收。

## 4. `batch` 是 `null` 時照 `state` 走

| 現在是 | 情況 | 做什麼 | 退出碼 |
|---|---|---|---|
| `idle` | `intake` 非 null，或 `input` 有東西 | 收輸入（§8），state 改 `think` | 0 |
| `idle` | 都沒有 | 不動 | 101 |
| `think` | — | 建一批 think、送出（§5） | 0 |
| `act` | 記憶尾巴是帶非空 `tool_calls` 的 `assistant` | 建一批 act、送出（§5） | 0 |
| `act` | 其他 | 沒東西可跑：state 改 `think` | 0 |

## 5. 送出一批

### 5.1 建批

取批 id B、K＝`AOS_K`、L＝現在記憶的長度。

- **think**：`calls` 一筆 `{"name": "B-0", "done": null, "acked": false}`。
- **act**：記憶尾巴那則 assistant 的每個 `tool_calls[i]` 一筆，順序照 i：按 `function.name` 在工具裡找——
  找到 → `{"name": "B-i", "tool_call_id": id, "tool": 名, "done": null, "acked": false}`；
  找不到 → `name: null`、`done: {"content": "沒有這個工具：<名>"}`、`acked: true`。

**寫 state**：`batch = {"kind", "kernel": K, "base_len": L, "sent": false, "calls"}`。這一寫之前什麼都沒送。

### 5.2 送件（`sent:false` 時做；崩了下次重做同一段）

這一段的 K 一律是 `batch.kernel`，不重讀 `AOS_K`（中途換了 `AOS_K` 也不會往別的 kernel 查或放）。

對每一筆 `name` 非 null、`done` 是 null 的 call：

1. `work/N.inst.json` **不在** → 產生（think 照 §5.4；act 先寫 `work/N.in`，再照 §5.3 寫 inst）。都是 `.tmp` 再 rename，
   **inst 最後寫**，所以「inst 在」就表示這件的檔都齊了。act 的 `_meta` 解不過 → 這筆記成
   `done: {"content": "工具 <名> 跑不起來：<代號>: <白話>"}`、`acked: true`，不送（留到第 3 步一起寫）。
2. inst 在 → **查有沒有放過**；沒放過才放單：

   ```json
   {"jsonrpc": "2.0", "id": "N", "method": "add",
    "params": {"target": "/abs/agent-bob/work/N.inst.json", "name": "N", "once": true, "pool": "<池>", "timeout_ms": T}}
   ```

   think 的池＝`info.llm.pool`、T＝`info.llm.timeout_ms`；act 的池＝`info.tool_pool`、T＝那個工具的 `_timeout_ms`。
   `link` 回 EEXIST＝已經放過（只有自己前一次崩了才會），當成功。其他放檔錯誤＝退 1（`io`），`sent` 仍是 false，下次重做。
3. **寫 state**：`sent: true`，加上第 1 步本地結束的那幾筆。退 0。

**查有沒有放過**（照這個順序，一步不能換）：

1. `K/requests/N.json` 在 → 放過了（kernel 還沒收，或 kernel 已經 `stopped`、留到下次 boot 收）。
2. 偷看 `K/state.json`：`procs` 有 `N`，或 `replies` 有一筆 `name` 是 `N.json` → 放過了（在排隊、在跑、或回音在出貨）。
3. `K/responses/N.json` 在 → 放過了。
4. 都不在 → 沒放過。`K/state.json` 不在＝kernel 從沒 boot 過，當作第 2 步沒有；讀得到但壞掉＝退 1。

理由：kernel 先記帳（`procs`／`replies`）再刪原單、同一次寫把回音放進 `replies` 並拿掉 `procs`、先放回音檔再從 `replies` 拿掉（[kernel.md §2、§3](kernel.md)），
一件工作只往後走；回音只有 ack 才消失，而 `done` 是 null 的從沒 ack 過；boot 保留 `procs`／`replies`。不能照搬 cpu 的「原單回音都不在＝沒放」。

### 5.3 act：工具的 inst

`_meta` 用 inst 的讀驗（`aos_inst.load_obj`，base＝agent 家）解完，**重新編成一份合法的字面 inst**——
不能把 `load_obj` 回傳的內部結構直接寫檔（形狀不同，aos-exec 會拒）。對照：

| 欄 | 寫成 |
|---|---|
| `_metainfo` | `{"_type": "posix", "_version": 1}` |
| `argv` | 解好的字串陣列，不改寫 |
| `cwd` | 絕對路徑；原本有 `mkdir` → `{"$opt": "mkdir", "$val": 絕對路徑}` |
| `envs` | 原本有 `clear` → **一定寫** `{"$opt": "clear", "$val": {…}}`（`$val` 是空物件也照寫——那就是完全空的環境）；沒 `clear` → 解好的物件，只有這時空物件才能省略 |
| `stderr`、`exit` | 沒寫就不寫；`inherit`／`merge` → `{"$opt": "inherit"}`／`{"$opt": "merge"}`；路徑 → 絕對路徑，帶 `append`／`mkdir` 時 → `{"$opt": [選項…], "$val": 絕對路徑}` |
| `stdin` | `/abs/agent-bob/work/N.in` |
| `stdout` | `{"$opt": "mkdir", "$val": "/abs/agent-bob/work/N.out"}` |

`work/N.in` 的內容是 `function.arguments` 字串原樣（UTF-8），不驗是不是 JSON。
`_meta` 的 `$env` 讀的是跑 aos-agent 那顆 cpu 的環境；工具要用自己那顆 cpu 的環境，就別寫 `$env`、也別 `clear`（不 clear 就整包繼承）。

### 5.4 think：問模型的 inst

```json
{"_metainfo": {"_type": "posix", "_version": 1},
 "argv": ["aos-llm-call", "/abs/agent-bob"], "cwd": "/abs/agent-bob",
 "stdout": {"$opt": "mkdir", "$val": "/abs/agent-bob/work/N.out"},
 "stderr": {"$opt": ["append", "mkdir"], "$val": "/abs/agent-bob/log/llm.err"}}
```

`argv[0]` 靠 llm 池那顆 cpu 的 PATH 找；模型表與金鑰也在那顆 cpu 的環境（[aos-llm-call.md §1](aos-llm-call.md)）。

## 6. 收回

每次（門開著、`batch` 非 null）：

1. `done` 非 null、`acked` 是 false 的先補 ack → 寫 `acked: true`。
2. `sent` 是 false → 先做 §5.2，退 0。
3. 對每筆 `done` 是 null 的 call：`K/requests/N.json` 在＝還沒；不在再看 `K/responses/N.json`：不在＝還沒（還在 kernel 裡）；
   在＝讀（JSON 壞＝退 1、不動任何東西），照 §6.1／§6.2 算出 `done`——要讀 `work/N.out` 的在這一步讀，讀驗不過照表記成失敗，**不留到結清才發現**。
4. 這次有新算出的 → **寫 state**（這幾筆 `done`，`acked` 仍 false）→ 逐則 ack → **寫 state**（`acked: true`）。
5. 全部 `done` 非 null 且 `acked` → 結清（§7）。否則：這次有寫東西退 0，什麼都沒到退 101。

ack 的形狀：`K/requests/ack-<epoch ns>-<pid>-<i>.json`（i 是 call 的序號；每則新取名、用 link 放，EEXIST 就換個 ns 再放），內容
`{"jsonrpc":"2.0","method":"ack","params":{"name":"N.json"}}`。多送一次無害（回音已不在＝kernel 當成功）。
程式上：放單＝`aos_client.submit(K, "add", params, name="N.json")`、ack＝`aos_client.ack(K, "N.json")`（取名要補序號）；**不用** `call()`（它同步等、自動 ack）。

等回音**沒有上限**：`timeout_ms` 只限在 cpu 上跑多久，不含排隊、停機、等 boot；不會因為等太久就判「沒送」重送。

### 6.1 think 的 `done`

照順序第一個命中的列：

| 回音 | `done` |
|---|---|
| `result`、`kind=child`、`code=0`、`timed_out=false`、`stopped=false` | 讀 `work/N.out`：去掉結尾換行後要恰好是一個 JSON 物件，照 [agent.md §3.2](agent.md) 驗成模型回的 assistant → `{"ok": true}`；不合 → `{"fail": "MessageInvalid: …", "count": true}` |
| `result.stopped=true` | `{"fail": "被強制停", "count": false}` |
| `result.timed_out=true` | `{"fail": "逾時（T ms）", "count": true}` |
| `result.kind=aos` | `{"fail": "aos-llm-call 沒跑起來（kind=aos），看 llm 池 cpu 的 cpu.log", "count": true}` |
| `result`、`code≠0` | `{"fail": "aos-llm-call exit <code>，看 log/llm.err", "count": true}` |
| `error.data.code=Stopping` | `{"fail": "kernel 停機時取消，沒跑", "count": false}` |
| `error.data.code=Interrupted`／`Removed` | `{"fail": "結果不明（Interrupted／Removed）", "count": true}` |
| 其他 `error` | `{"fail": "kernel 退件：<data.code，沒有就 code>", "count": true}` |

### 6.2 act 的 `done`

`{"content": …}`，照順序第一個命中的列；「輸出」＝`work/N.out` 以 UTF-8 讀、非法位元組換成 U+FFFD，檔不在＝空字串：

| 回音 | `content` |
|---|---|
| `result`、`kind=child`、`code=0`、`timed_out=false`、`stopped=false` | 輸出原樣 |
| `result.stopped=true` | 固定 `{"ok": false, "error": "結果不明：工具可能已經跑了，也可能沒有"}` 的 JSON 字串 |
| `result.timed_out=true` | 「工具 <名> 逾時（T ms）：」＋輸出 |
| `result.kind=aos` | 「工具 <名> 無法執行（kind=aos），詳情在跑它那顆 cpu 的 cpu.log」 |
| `result`、`code≠0` | 「工具 <名> 失敗（exit <code>）：」＋輸出 |
| `error.data.code=Interrupted`／`Removed` | 同 `stopped` 那列的固定字串（可能已經跑了） |
| `error.data.code=Stopping` | 「工具 <名> 沒跑：kernel 停機時取消」 |
| 其他 `error` | 「工具 <名> 沒跑：kernel 退件（<data.code，沒有就 code>）」 |

四種停：`Stopping`＝排隊時被停機取消，**確定沒跑**；`Removed`＝被 `rm`，**可能正在跑**；`Interrupted`＝cpu 主人死在這件上，**結果不明**；
`stopped:true`＝被強制停砍，**可能跑一半**。只有 `Stopping` 算「沒發生」；刪檔另看 §10，跟是哪一種無關。

## 7. 結清

全部 `done` 齊了、都 ack 了，才做。記憶的寫法固定是「**前 `base_len` 則＋這批的訊息**」整份重寫（`.tmp` 再 rename），
所以崩在寫記憶之後、寫 state 之前，下次再結清一次寫出來的是同一份，不會接兩次。

先檢查記憶跟當批對得上，不對＝`HistoryChanged`、退 1、不動（人改過記憶，要人處理）：
記憶長度必須是 `base_len`（還沒接），或是 `base_len`＋這批要接的則數、而且尾巴逐則等於這批要接的訊息（上次接過、崩在寫 state 之前）；
其他長度（例如人在途中加了訊息）一律 `HistoryChanged`，不悄悄截掉。act 另外要求第 `base_len` 則（從 1 算）是 assistant、它的 `tool_calls` 的 id 依序等於 `calls[].tool_call_id`。
**檢查的範圍就這些**：前 `base_len` 則被人等長改寫不偵測、也不擋——寫回用的前綴就是這次讀到的那份，人的改動照樣保留。

| 當批 | 寫記憶 | 然後**一次寫 state** |
|---|---|---|
| think、`{"ok": true}` | 前 L 則＋`work/N.out` 那則 message | `state`＝有非空 `tool_calls` → `act`，否則 `idle`；`errors: 0`；`batch: null`；`sweep` 加這批 |
| think、`count: true` | 不動 | `errors`＋1（到 3 見 §9）；`state` 留 `think`；`batch: null`；`sweep` 加這批。stderr 一行 `aos-agent: engine: <fail>` |
| think、`count: false` | 不動 | `errors` 不動；`state` 留 `think`（下一格重問）；`batch: null`；`sweep` 加這批 |
| act | 前 L 則＋每筆 call 一則 `{"role": "tool", "tool_call_id": …, "content": done.content}`（照 `calls` 順序） | `state: think`；`batch: null`；`sweep` 加這批有名字的 |

連敗計數跟「這批結清了」在同一次寫裡，所以不會漏算、也不會重算。退 0。
同一則 assistant 叫多個工具，只保證接回的順序，**不保證執行順序**（可能派到不同 cpu 平行跑）。

## 8. idle：收輸入

1. `intake` 是 null：列出 `input` 指到、現在存在的檔（[agent.md §4.1](agent.md)）。一個都沒有＝退 101。
   有 → 取新的消費 id，**寫 state**：`intake = {"id", "base_len": 現在記憶長度, "files": [{"src", "dst": "<src>.<id>.done"}…]}`。這一步還沒讀內容。
2. 逐對搬（[agent.md §4.4](agent.md)：`dst` 在＝搬過了、不碰 `src`；`dst` 不在 `src` 在＝rename；都不在＝那份被人拿走了，讀的時候跳過）。
3. 從每個 `dst` 讀訊息、照 agent.md §3.2 驗。壞檔＝退 1，**已寫的 `intake` 與已搬的檔都留著**。人要處理：就地改好那個 `dst`；
   或照 [agent.md §4.4](agent.md) 放棄那一對（先 stop、在 state 裡拿掉那一對、才動 `dst`）——只刪 `dst` 不改 state，下次會去搬原路徑上的新檔。全部略過＝沒輸入：寫 `intake: null`、退 101。
4. 記憶寫成「前 `base_len` 則＋讀到的訊息」（長度檢查同 §7；其他＝`HistoryChanged`）。
5. **寫 state**：`state: think`、`intake: null`。退 0。

崩在 1 之後任何地方：下次看到 `intake` 從第 2 步重做。讀的永遠是封存名，內容不會變；同一份訊息不會接兩次；
原路徑上新投的同名檔不會被這次恢復搬走或吞掉，留給下一次收。

## 9. 連敗暫停

§7 那次寫把 `errors` 加到 3 時：同一次寫改成 `errors: 0`、`waits` 表尾加 `{"$opt": "consume", "$val": "continue-<B>.json"}`（B＝這批的批 id，所以每次暫停的訊號檔名都不同，不會有舊檔先在），
stderr 一行 `aos-agent: stuck: 問模型連敗 3 次，touch continue-<B>.json 繼續`。人也可以直接看 `state.json` 的 `waits` 找到檔名。
本次退 0，之後門沒開就 101。設定讀驗、I/O 錯、`HistoryChanged` 不算連敗（它們退 1，由 kernel 的 `bad_after` 管）；工具失敗也不算（那是給模型看的結果）。

## 10. 清工作檔

每次 `tick` 第 3 步，對 `sweep` 的每一筆 `{kernel: K, name: N}`：`K/requests/N.json` 不在、**而且**偷看 `K/state.json` 的 `procs` 沒有 `N`
→ 刪 `work/N.inst.json`、`work/N.in`、`work/N.out`（ENOENT＝已刪）→ 把這筆拿掉。全部看完一次寫 state。

依據：kernel 對一件派出去的工作，`procs.N` 一直留到那顆 cpu 的回音收回來才拿掉——被 `rm` 的也一樣（標 `discard`，[kernel.md §2](kernel.md)）。
所以 `procs` 沒有 `N`＝它已經不在任何 cpu 上（或根本沒送出去），檔可以刪；有 `N`＝可能還在讀 `.in`、寫 `.out`，先留著。
`K/state.json` 讀不到就整段跳過，下次再看。（cpu 被 KILL、子程式還活著這種情況在 [cpu.md §5.3](cpu.md) 的保證外。）

## 11. `start`／`stop`：登記進 kernel

**`aos-agent start [dir]`**：

1. 讀驗 `info.json`（不過＝退 1）；K＝`AOS_K`。
2. **查 K 的退出碼約定相不相容**：讀 `K/info.json`（讀不到、不是 JSON、頂層不是字面物件＝`NotAHome`、退 1），**只解驗 `done_exit`、`bad_after` 兩格**：
   型別與預設照 kernel.md §1.1（沒寫＝100、10），帶原文件與位置、中心 K 解（`$ref:""`、相對 `$at` 照常定位）；其他格不解不驗，
   start 端只需要這兩格用到的 `$env`。這兩格解不開或型別錯＝那個代號、退 1。
   `tick` 會回 0／101／1，所以 `done_exit` 是 1 或 101 ＝`KernelIncompatible`、退 1、不登記（kernel 判回音時先比 `done_exit`，
   撞到就會把 agent 當成「做完了」永久停排）。`done_exit` 是 0（關掉）或其他值都行。`bad_after` 是 0＝關掉退件，agent 一直退 1 也不會被標 `bad`，照登記。
   這只在 start 當下查；之後人改 K 的 info，要自己重查。
3. `tick.json` 不在就寫一份；在就讀它的 `envs.AOS_K`：是字面字串且等於現在的 `AOS_K` 才照用，否則（不同、不是字串、檔讀不懂）＝`KernelMismatch`、退 1，
   stderr 說「tick.json 綁在另一個 K，要換就刪掉 tick.json 再 start」。寫出來的長這樣：

   ```json
   {"_metainfo": {"_type": "posix", "_version": 1},
    "argv": ["aos-agent", "tick", "/abs/agent-bob"], "cwd": "/abs/agent-bob",
    "envs": {"AOS_K": "/abs/K"},
    "stderr": {"$opt": ["append", "mkdir"], "$val": "/abs/agent-bob/log/agent.err"}}
   ```

   `.tmp` 再 rename 寫，所以「在」就是完整的。`aos-agent` 靠 `tick.pool` 那顆 cpu 的 PATH 找。
4. 放單並等回音（最多 10 秒），等於替人打：

   ```sh
   aos-kernel add "$AOS_K" /abs/agent-bob/tick.json --name agent-<資料夾名> --pool <tick.pool> [--interval-ms <tick.interval_ms>]
   ```

   `interval_ms` 沒寫就不帶（用 kernel 的預設）；不帶 `timeout_ms`、不帶 `--once`。收到回音就 ack。

**`aos-agent stop [dir]`**：讀驗 info 後，等於 `aos-kernel rm "$AOS_K" agent-<資料夾名>`，等回音最多 10 秒、ack。不查 tick.json、不查 done_exit。

start／stop 的 request 檔名是 `aa-<資料夾名>-<epoch ns>-<pid>.json`（id 同名去掉 `.json`）。**等回音逾時**：stderr 印一行
`aos-agent: ReadFailed: 等回音逾時，回音會出現在 <K>/responses/<檔名>，讀完自己放 ack（cpu.md §3.3）`、退 1——
操作可能已經生效，不會撤回；那則回音 agent 之後不會再管。

退出碼：0＝kernel 回了 `{"name"}`；1＝`KernelIncompatible`、`KernelMismatch`、kernel 回 `error`（`AlreadyExists`：已登記或上次 stop 的那格還在跑；
`-32602`：池不在 K；`NotFound`）、讀驗錯、放檔錯、等回音逾時；stderr 一行 `aos-agent: <代號>: <白話>`；2＝用法錯。

stop 之後：正在跑的那格會跑完（kernel 丟掉它的回音）；當批送出去的工作照跑，回音留在 K，下次 start 之後再收。
kernel 行程名只看資料夾名，不同位置的兩個同名資料夾會撞 `AlreadyExists`（保證外，改資料夾名）。
`bad_after` 非 0 時，連續退 1 達那個次數 kernel 會把 agent 標 `bad` 不再排（是 0 就一直重跑）。被標 `bad` 後：看 `log/agent.err` 修好，再 `stop`（`rm` 刪得掉 `bad`）、`start`。

## 12. `tick` 的退出碼與 stderr

| 碼 | 什麼時候 |
|---|---|
| 0 | 這格做了事：收輸入、送一批、收到新回音、結清（含問模型失敗、連敗暫停） |
| 101 | 在等：門沒開、當批還沒到、`idle` 沒輸入 |
| 1 | §2 第 1 步的起始讀驗錯（[agent.md §5](agent.md) 的代號；**只有這種什麼都不寫**）；之後的讀驗錯（輸入檔、回音、K 帳本）、`HistoryChanged`、I/O 錯 `aos-agent: io: …`——可能已寫一部分，紀錄照留，下次照 `batch`／`intake`／`consuming` 接著做 |
| 2 | 用法錯（含 `AOS_K` 沒設） |

一行一件，開頭 `aos-agent: `；問模型失敗 `aos-agent: engine: …`、暫停 `aos-agent: stuck: …`。

## 13. 保證外與這份沒管的

- **一個 agent 家同時只能有一個驅動者**：kernel 按行程名排、不按資料夾去重；已登記時別再手動 `tick`、別用兩個名字登記同一個家。
  外人改 `state.json`（例如加門）會跟正在跑的那格互相蓋掉——要改就先 `stop`，等 `aos-kernel ls` 看不到 `agent-<資料夾名>` 了再改。沒有鎖。
- 人刪了 K 的檔、工作真的丟了：當批一直等；要放棄就 stop 後手動把 `batch` 設 `null`（工作檔自己清）。
- **問模型讀的是執行當下的 agent 家**：aos-llm-call 跑起來才讀人格、記憶、工具（[aos-llm-call.md §3](aos-llm-call.md)）；
  在途時人改了這些，會影響那一問。aos-agent 只保證**當前還沒取消的** think 批在途時不寫記憶；被 `Removed` 的舊問可能在重問、記憶變長之後才讀家，
  但它的回音 kernel 會丟掉、不會接進記憶（要連殘留也保證輸入不變，得等它的 `procs` 消失再重問，這版不做）。
- kernel `stop`：還在排隊的 once 回 `Stopping`（think 下次重問、工具告訴模型「沒跑」），在跑的照常跑完；
  agent 自己的那格在 stopping 時不會被派，當批留到下次 boot 之後收（kernel 跨 boot 保留 `procs`／`replies`）。
- 放單崩在 `link` 之後、刪 `.tmp` 之前：`K/requests/` 留一個 `.` 開頭 `.tmp` 結尾的殘檔；主人只收 `.json`，不會誤收；**沒人自動清**（保證外），人在都停著時刪。
- **日常 CLI 還沒完**：三份做完能走的只有「手動建家 → `start` → 往 `input` 放檔 → 問模型／跑工具 → 回 `idle`」，回話要自己看記憶檔。
  `init <template>`、`say`、`pause`／`continue`、`tools`／`llms`、`state`、專屬 cpu 都還沒有（構想在 [thinking/aos-agent.md](../../thinking/aos-agent.md)）；記憶太長也沒管。

## 14. 已拍板的前提（使用者定的，不重問）

1. **沒有同步工具**：問與跑都是 kernel `add --once`。取捨：最快等一格 tick；同批工具可能平行，有先後依賴的合成一個工具或拆兩輪。
2. **agent 先進現有的池**：`start`／`stop`＝替人 `aos-kernel add`／`rm` 反覆行程 `agent-<資料夾名>`；K 由 `AOS_K` 給，沒設＝用法錯 2。
3. **llm.json 放 llm cpu 那邊**：agent 只給代號；外圈逾時 `info.llm.timeout_ms`、HTTP 逾時在 llm.json（[aos-llm-call.md §6](aos-llm-call.md)）。
