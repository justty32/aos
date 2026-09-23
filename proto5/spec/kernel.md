# kernel：排程也是一格一格的 aos-exec（第 1 版，**草稿**）

← [proto5 README](../README.md)｜範式：[cpu.md](cpu.md)｜跑一次：[aos-exec.md](aos-exec.md)｜下層：[daemon](daemon.md)

> 2026-09-23 重架構第二份；同日照 astra 三輪審查改過（K／X／R、K2／X2／R2、K3／X3／R3）。
> 舊 kernel-home.md／aos-kernel.md 等新的齊了一次換掉。已拍板的前提在 §9，我自己選的在 §10。

一句話：**kernel 不是長命行程，是一格一格的 `aos-kernel tick`：每一格是一則普通的 `aos-exec` request、
跑在一顆專用的 exec cpu 上，格的開頭先把下一格放進那顆 cpu 的 `requests/`，像尾遞迴一樣接下去**
（意思是：這格不等下一格跑完，先把它排上去就自己退出）。
工作與 syscall 走資料夾（往 cpu 的 `requests/` 放、從 `responses/` 收、放 `ack`），父子生死走 pipe，
兩者共用 JSON-RPC 信封。kernel 跟 daemon 講話也走 daemon 家的資料夾。
**`K/state.json` 是唯一的帳本**：每個決定都是一次原子寫；除了接鏈，其他檔都是先記進帳本再放出去的。

---

## 0. 名詞（白話）

跟 cpu 範式共用的詞（inst、目標、request、主人、link、notification、偷看…）在 [cpu.md §0](cpu.md)，這裡只列 kernel 自己的。

| 詞 | 意思 |
|---|---|
| 長命行程 | 開著就不退、一直待命的程式（daemon、cpu 的主人都是）。kernel **不是**：它每次只活一格的時間，記憶全放在 `K/state.json` 裡 |
| tick（一格） | kernel 的一次心跳：跑一次 `aos-kernel tick K --chain C --seq N`，把 §3 那十步做完就退出。「格」就是一次 tick |
| kernel cpu（`kcpu`） | 專門拿來排 tick 的那一顆 exec cpu，boot 時從 `info.cpus` 裡 pool 標 `kernel` 的挑出來、名字釘進帳本；一般工作不准進去。要換得重 boot |
| 鏈／接鏈 | 一格排下一格、一格接一格串成的那一串 tick。接鏈＝這格開頭就把下一格的 request 放進 kernel cpu 的 `requests/` |
| 尾遞迴 | 借程式的講法：這格**不等**下一格跑完，只把它排上去就自己退出。所以不會越疊越深，也不會兩格同時在跑 |
| 鏈 id（`chain`） | boot 發的一串 `<epoch ns>-<pid>`，用來認「你是哪條鏈的格」。**kernel 取的每個檔名都帶它**，所以跨 boot 名字不會重複 |
| 序號（`seq`） | 這格在鏈裡是第幾格，寫在 tick 的 args 裡；下一格就是 seq+1。只拿來取名，不拿來守門 |
| 殘格 | 舊鏈排在隊上、現在才被跑到的 tick。它 args 裡的 chain 對不上帳本的，所以什麼都不做就退出（自滅） |
| syscall | 借作業系統的講法；在這裡只是「往 `K/requests/` 放一個 JSON 檔」（`add`／`rm`／`stop`）。下一格會讀它，回音寫在 `K/responses/` |
| ack | 收件者說「這份回音我拿走了」的那張單（範式 §3.3）；放了對方才刪回音。kernel 收 cpu／daemon 的回音要放 ack 給它們；別人收 kernel 的回音要放 ack 給 kernel |
| 帳本 | `K/state.json`。kernel 所有的記憶：鏈、階段、每顆 cpu 手上的工作、每個行程的紀錄與計數、還沒結清的出貨。一次原子寫 |
| 出貨箱（outbox） | 帳本裡四張「記了、還沒結清」的清單：`acks`（欠 cpu／daemon 的 ack）、`replies`（欠客戶的回音）、`stops`（欠 cpu 的 stop）、`deletes`（該刪的 syscall 原單）。先記進帳本、再放檔、放完清掉；「還沒結清」包含「已放還沒清」，重放是安全的 |
| 階段（`phase`） | kernel 整體在哪：`running` 照常派工／`stopping` 不再派新的、把在途的收完／`stopped` 連鏈都不接了 |
| 行程（`procs.<NAME>`） | **不是**作業系統那個行程。在 kernel 這裡是「一份登記好的工作」：記著要跑哪個 target、多久跑一次、跑到哪；真的有東西在跑是派工之後的事 |
| 狀態（`status`） | 一個行程現在在哪：`queued` 排隊中／`running` 派出去了／`done` 做完了／`bad` 被退件。後兩種只是留給人看，`rm` 能刪 |
| 佇列（`queue`） | 等著被派上 cpu 的行程名單；已經派出去的不在裡面 |
| boot | 開機：先叫 daemon 把舊的 kernel cpu 收掉、等它從孩子表消失，發一個新鏈 id、拉起所有 cpu、把第 1 格放進 kernel cpu。boot 自己不跑格 |
| 反覆行程 | `once: false` 的行程：跑完回佇列，隔 `interval_ms` 再跑一次，直到完成或被退件 |
| `once` | 只跑一次的行程：那次跑完把結果直接交給當初 `add` 的人，行程跟著消失 |
| 完成／`done_exit` | 反覆行程的退出碼剛好是 `done_exit`（預設 100）＝它自己說「我做完了」，狀態改 `done`、不再排 |
| 退件／`bad_after` | 一直失敗就不再排它，狀態改 `bad` 給人看：連續失敗 `bad_after` 次（預設 10）。kind=aos（檔讀不到、inst 壞掉）也算一次失敗 |
| 池（`pool`） | 給 cpu 貼的一個字串標籤；行程也標一個，只會被派到標籤相同的 cpu 上（例如打模型的工作都排去 `llm` 那顆） |
| `tick_ms` | 一格睡多久。跟行程的 `interval_ms`（同一個行程兩次之間隔多久）是兩回事 |
| `req`／`proc` | `req`＝派給這顆 cpu、還沒結清的 request 檔名（可能已放、也可能剛記還沒放）；`proc`＝那則是哪個行程的。**一顆 cpu 忙不忙只看 `req` 是不是 `null`**，kernel 不去讀 cpu 自己的 state |
| `discard` | 那個行程已經被 `rm` 了，但工作還在 cpu 上跑；回音到了直接丟掉、不計數 |
| 在途 | 已經記了 `req`、還沒收到回音的工作。`stopping` 要等它們全部收完才真的停 |
| 冪等 | 同一步做一次跟做兩次結果一樣。崩了重跑才安全——帳本＋出貨箱就是為這個 |
| EEXIST（在這裡） | `link` 到已經存在的名字會失敗。kernel 把它當「已經放過了」的訊號，照樣往下走，不當錯誤 |
| 先放後記 | **只有接鏈**用的順序：**先**把下一格放進 kernel cpu 的 `requests/`、**再**寫帳本。崩在中間下一格照跑，鏈不會斷 |
| 先記後放 | 其他所有出貨（派工、回音、ack、stop、刪原單）的順序：**先**寫帳本、**再**放檔。崩在中間最多「記了沒放」、下一格補放，絕不會同一個行程被派到兩顆 cpu |
| 收回音 | 去 `cpus/<name>/responses/` 讀那則 request 的結果，判定（§4）、更新帳本、再放 ack |
| `spawn` | 叫 daemon「把這份 inst 拉起來當孩子」。同名同 target 已經活著就回它的 pid、不重拉，所以逾時後重送是安全的 |
| `restart:true` | 拉起來時交代 daemon：這孩子非 0 退出就自己再拉一次，kernel 不用管 |
| `Interrupted` | 「結果不明」的錯誤回音：cpu 的上一任死在那件工作上，下一任補的（範式 §6.2）。kernel 當一般失敗計數 |
| 派工 | 從佇列挑一個輪得到的行程，把它的 `aos-exec` request 放進某顆閒著的 cpu |
| `stopped`（回音裡的） | 這次是被強制停砍掉的，結果不算數：計數不動，行程直接回佇列 |

---

## 1. 家

```text
K/
  info.json                 身分、daemon 家、cpu 表、排程預設；人寫的
  state.json                帳本（§1.2）
  requests/ responses/      syscall（範式 §3）
  cpus/<name>/              每顆 cpu 的家（各自 info／state／requests／responses／inst.json）
  kernel.log                每格 append
```

`K/` 的主人是「當下正在跑的那一格 tick」（鏈保證同時只有一格，§7）；外人只能往 `requests/` 放單、
讀 `responses/` 然後放 `ack`；`state.json` 隨便偷看。`K/cpus/<name>/` 各是另一個家，主人是那顆 `aos-cpu`；
kernel 對它們也是外人，**只在家不存在時**替它們建家、寫 `info.json` 與 `inst.json`（初始化，不算動別人的家）；
已經有的一律不改寫，人可以自己編那顆的 `inst.json`（例如加環境變數，見 §1.1 `envs`）。
沒有 `procs/` 資料夾：行程紀錄全在帳本裡。

### 1.1 `info.json`

```json
{
  "_metainfo": {"_type": "kernel", "_version": 1},
  "daemon": "/abs/D",
  "cpus": {"k": {"pool": "kernel"}, "0": {}, "1": {},
           "llm": {"pool": "llm", "envs": {"PATH": {"$fmt": "/abs/tools/llm:${PATH}", "PATH": {"$env": "PATH"}}, "LMSTUDIO_KEY": {"$env": "LMSTUDIO_KEY"}}}},
  "tick_ms": 1000,
  "interval_ms": 1000,
  "timeout_ms": 0,
  "done_exit": 100,
  "bad_after": 10
}
```

| 鍵 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `daemon` | 絕對路徑 | boot 寫 | daemon 家；tick 靠它找 daemon |
| `cpus` | 物件 | 必填 | key 是 cpu 名（也是 `cpus/<name>/` 的資料夾名、給 daemon 的孩子名）；值 `{"pool": 字串, "envs": 物件}`，`pool` 沒寫＝`"default"`，`envs` 可省。**恰好一顆** pool 是 `kernel`（少於或多於一顆＝`FieldTypeMismatch`），一般行程不准進這個池 |
| `cpus.<c>.envs` | inst 的 `envs` 格 | 無 | kernel 建那顆的家時原樣抄進 `cpus/<c>/inst.json` 的 `envs`（含 `$opt` 選項）——這就是「這顆 cpu 帶什麼環境」（範式 §4.1）。家已經在就不管它 |
| `tick_ms` | 非負整數 | 1000 | 一格睡多久（§3 第 3 步） |
| `interval_ms` | 非負整數 | 1000 | 行程 `interval_ms` 的預設 |
| `timeout_ms` | 非負整數 | 0 | 行程 `timeout_ms` 的預設；tick 自己不限時 |
| `done_exit` | 0～255 | 100 | 反覆行程回這個碼＝完成；0＝關掉 |
| `bad_after` | 非負整數 | 10 | 連續失敗幾次退件；0＝關掉 |

整份解指示詞，中心是 K，不提供 `$opt`（`envs` 那格例外：它是要抄進 inst 的，原樣留著不解）。
**頂層必須是字面物件**（頂層整份 `$ref` ＝ `FieldTypeMismatch`），不然 boot 寫進去的 `daemon` 會被引用吃掉。
boot 把整份驗完才動任何東西（§6）。「專門打 LLM 的 cpu 只開一顆」就是開一顆 `{"pool":"llm","envs":…}`、
把 `aos-llm-call` 那種行程標 `pool: "llm"`。要幾顆就寫幾顆，佔著沒關係。
改 info 之後：tick 每格重讀；多出來的 cpu 下格會拉，被拿掉的 cpu 若帳本裡還有 `req`，照樣收完那則才忘掉它；
池裡沒有 cpu 的行程就一直排隊，不算錯，`ls` 看得出。**kernel 池那顆例外**：帳本裡釘死的 `kcpu` 才算數，
改 info 不會換，要換就重 boot。

### 1.2 `state.json`（帳本）

```json
{
  "chain": "1790000000000000000-4242", "kcpu": "k", "cli": "/abs/proto5/cli/aos-kernel",
  "last_seq": 41, "phase": "running",
  "cpus": {"0": {"req": "k-1790000000000000000-4242-40-0.json", "proc": "bob", "discard": false},
           "1": {"req": null, "proc": null, "discard": false}},
  "queue": ["alice"],
  "procs": {
    "bob":   {"request": "cli-1790000000000000000-77.json", "target": "/abs/agent-bob/tick.json",
              "dir_target": ".aos/inst.json", "once": false, "pool": "default", "interval_ms": 1000, "timeout_ms": 0,
              "status": "running", "runs": 7, "fails": 0, "not_before": 1790000001.2, "pending": null},
    "alice": {"request": "agent-1790000000000000000-77.json", "target": "/abs/agent-alice/think.json",
              "dir_target": ".aos/inst.json", "once": true, "pool": "llm", "interval_ms": 1000, "timeout_ms": 60000,
              "status": "queued", "runs": 0, "fails": 0, "not_before": 0,
              "pending": {"name": "agent-1790000000000000000-77.json", "id": "agent-1790000000000000000-77"}}},
  "acks":    [{"home": "/abs/K/cpus/1", "name": "k-1790000000000000000-4242-39-1.json"}],
  "replies": [{"name": "cli-1790000000000000000-78.json", "id": "cli-1790000000000000000-78", "body": {"result": {"name": "carol"}}}],
  "stops":   [],
  "deletes": ["cli-1790000000000000000-78.json"]
}
```

| 鍵 | 意思 |
|---|---|
| `chain` | 這條鏈的 id，boot 給的（`<epoch ns>-<pid>`）。tick 帶著它來，對不上就是舊鏈的殘格 |
| `kcpu`、`cli` | boot 釘的：kernel cpu 的名字、`cli/aos-kernel` 的絕對路徑（tick 的 target 用它）。tick 只認帳本這兩格，不看 info、不看自己怎麼被叫 |
| `last_seq` | 最後一格的序號，給人看；下一格的序號來自 tick 自己的 args，不從這裡拿 |
| `phase` | `running`／`stopping`／`stopped`（§3 第 9 步） |
| `cpus.<name>` | **只有工作 cpu**，kernel cpu 不在這裡。`req`＝派給它、還沒結清的 request 檔名，`null`＝閒（**cpu 忙不忙就看這格**）；`proc`＝那則是哪個行程的；`discard`＝那個行程已被 `rm`，回音到了丟掉 |
| `queue` | 等派工的行程 NAME，先進先出；`status=queued` 的都在這 |
| `procs.<NAME>` | 行程紀錄：`request`（當初那則 add 的檔名，給人看）、`target`／`dir_target`／`args`（沒給就沒這個鍵）／`once`／`pool`／`interval_ms`／`timeout_ms`（政策，add 之後不改）；`status`／`runs`／`fails`／`not_before`（下次最早可派的 epoch 秒）／`pending`（`once` 還沒回的那則 add：檔名＋id） |
| `acks`／`replies`／`stops`／`deletes` | 出貨箱（§0）：ack 給哪個家、哪個名；回音給 `K/responses/` 的檔名、id、內容；stop 給哪顆 cpu；哪些 syscall 原單該刪。§3 第 4 步與第 10 步出貨 |

NAME 是非空檔名，不能是 `.`／`..`、含 `/` 或 NUL。kernel **不讀 target 指的檔**，只記路徑。
重拉節奏、階梯進度這種執行中的東西不在帳本裡（那是 daemon 的）；帳本裡的每一格重啟後都還算數。

### 1.3 kernel 取的檔名

| 放到哪 | 檔名 | 誰的 |
|---|---|---|
| kernel cpu 的 `requests/` | `k-<chain>-<seq>.json` | 第 seq 格 tick |
| 工作 cpu `<c>` 的 `requests/` | `k-<chain>-<seq>-<c>.json` | 第 seq 格派給 c 的工作 |
| 任一 cpu 的 `requests/` | `ack-<chain>-<seq>-<c>.json`（同格對同顆最多一則）、`stop-<chain>.json` | ack、stop |
| daemon 的 `requests/` | `k-<chain>-<seq>-spawn-<c>.json`、`ack-<chain>-<seq>-<c>.json`、boot 用 `k-<chain>-boot-kill.json` | 拉 cpu、ack、boot 收舊 kernel cpu |

kernel 放出去的檔名全部帶 `chain`，跨 boot 永不重複；同一格對同一個家的同一種東西最多一份，所以格內也不重複。
這是範式 §1「名字不重用」在 kernel 這邊的做法。前提是 `chain` 本身不重複——`<epoch ns>-<pid>` 在同一台機器上夠用。

## 2. syscall（`K/requests/`）

| method | params | 回音 |
|---|---|---|
| `add` | `target` 必填（絕對路徑）；`dir_target`／`args` 可省（同範式 §4.1；`args` 沒給就不要放這個鍵）；`name` 可省（省＝數字名最大值加 1）；`once`（預設 false）；`pool`（預設 `default`，必須是 info.cpus 裡有的、且不是 `kernel`）；`interval_ms`／`timeout_ms`（預設照 info） | **反覆**行程：`{"name": NAME}`。**`once`**：回音等到那一次跑完才寫，內容就是那次的 exec 回音（`result` 或 `error` 原樣）；交件者等 `K/responses/<自己的檔名>.json` 一個檔、讀完放 ack |
| `rm` | `name` | `{"name": NAME}`；不在＝`-32000`／`NotFound`。細節見下 |
| `stop` | notification | `phase` 改 `stopping`（§3 第 9 步）。daemon 不動，由人停 |
| `ack` | 範式 §3.3 | kernel 是一個家，別人收了 `K/responses/` 的回音要放 ack，處理方式照範式（刪回音、刪 ack 檔） |

沒有 `ls` syscall：看狀態就偷看 `K/state.json`（§6 的 `ls` 就是這樣做，鏈斷了也看得到）。
同名 `add`（不管 `status` 是什麼、含被 rm 但還在 cpu 上跑的）回 `-32000`／`AlreadyExists`；
params 形狀或 pool 不合回 `-32602`。kernel 不解指示詞、不驗 inst、不看檔在不在——那些都是跑起來的回音。

**每則 syscall 都是「一次帳本寫入」＋出貨**：判定 → 把結果（行程紀錄、queue、pending）跟兩筆出貨
（回音進 `replies`、原單名進 `deletes`）**一次**寫進帳本 → 出貨（放回音、刪原單）。
重掃看到某份原單，先看 `deletes`：**在裡面＝已收過**，只補刪、不重判——去重憑據是出貨箱，不是行程紀錄
（行程紀錄會被別的 rm 刪掉，靠不住）。`deletes` 在原單真的刪掉之後才清。

**`rm` 的三種情況**：
- 行程 `queued`／`done`／`bad`：從帳本拿掉（含 queue）。`once` 且 `queued`：它 `pending` 的 add 回 `-32000`／`Removed`（進 `replies`）。
- 行程 `running`、那顆 cpu 的 `req` 是它：照範式順序查——`cpus/<c>/requests/<req>` **在** → 在途，標 `discard`、
  行程紀錄留著（回音到了才拿掉，同名 add 在那之前都 `AlreadyExists`）；原單不在再看回音，**在** → 同上；
  兩個都不在 → 上一格記了沒放，直接取消：`req`／`proc` 清 null、行程拿掉。
- **`once` 不管在途還是取消，`rm` 當下就把 pending 的 add 回 `Removed`**、`pending` 清掉；之後那顆 cpu 的回音只是被 discard 掉。

## 3. 一格 tick 做什麼

```sh
aos-kernel tick K --chain C --seq N
```

每一步標了 **讀**／**寫帳本**／**放檔**；「崩在這裡」的後果寫在步驟後面。cpu 那邊的順序是
「先發回音、再刪原單」（範式 §6.3），這裡查檔一律**先查原單、再查回音**，才不會看錯。
第 5～9 步新增的出貨不在當步放，統一在第 10 步；崩在中間下格第 4 步補。

1. **讀** info、帳本。`--chain` ≠ `chain` → 舊鏈的殘格：退 0、什麼都不做。
2. `phase=stopped` → 出貨（第 4 步的方式，含 `stops`）、不接鏈、退 0。否則**放檔**：把下一格 `link` 到
   `cpus/<kcpu>/requests/k-<chain>-<N+1>.json`（`aos-exec`：`target`＝帳本的 `cli`，是普通檔，
   `args`＝`["tick", K 的絕對路徑, "--chain", C, "--seq", "N+1"]`，全是字串；沒有 timeout）。EEXIST＝上一格已放過
   （它崩在放檔之後、寫帳本之前，這格被重跑）——只有第 N 格會放第 N+1 格，所以 EEXIST 不會是別人。
   然後**寫帳本** `last_seq=N`。**先放後記**：這格之後崩了，下一格照跑。崩在放檔之前＝鏈斷，daemon 的
   `restart` 救不了（cpu 沒死、是沒單），`ls` 看得出（§6），人重新 boot。
3. 睡 `tick_ms`（下一格已在隊上，但 kernel cpu 正被這格佔著，睡完退出它才開始；實際週期＝睡＋這格做事的時間）。
4. **出貨**：四張出貨箱每筆放檔（`link`，EEXIST 當已放；`deletes` 是刪檔，ENOENT 當已刪）、每放完一筆**寫帳本**拿掉。
   順手把 kernel cpu 的 `responses/` 全部 ack 掉（都是舊 tick 的回音，不進 `acks`；`code≠0` 的記 log 一行）。
5. **讀** `requests/`，收 syscall（§2；`ack-` 照範式 §3.3、`stop-` 只改 `phase`）。放在 daemon 操作之前。
6. **收回音**：每顆 `req` 非 null 的工作 cpu，先**讀** `cpus/<c>/requests/<req>` 在不在——
   - 在：在途，跳過。
   - 不在，再看 `cpus/<c>/responses/<req>`：**在** → 判定（§4），把結果（計數、status、queue、pending 的回音進
     `replies`、這則的 ack 進 `acks`、`req`／`proc`／`discard` 清掉）**一次寫帳本**。崩在寫帳本之前＝下格重讀
     同一份回音、重判一次，冪等（回音要 ack 才會消失，而 ack 在帳本之後才放）。
   - 兩個都不在：從沒放出去（上格崩在寫帳本之後、放檔之前）→ **再放一次**（`link`，EEXIST 就當已在）。
     這個推論成立是因為 cpu 只在回音發出之後才刪原單，而回音只有 kernel 放 ack 才消失、ack 又在帳本之後。
7. **daemon**（§5）：偷看 `D/state.json` 的孩子表。對 info.cpus 裡每顆 c（含 `kcpu`）：
   - 表裡有 c、`alive=true`、`target` 是 `K/cpus/<c>/inst.json` → 好。
   - 表裡有 c 但 `target` **不是**我們的 → 別的 kernel 的孩子：stderr `NameTaken`、退 1，不派工。
   - 表裡沒有 c、或 `alive=false` 且 `state` 不是 `dead`（不是在等重拉）→ 家不在就建（info、inst，`envs` 照 info），
     `spawn`（`name`＝c、`restart:true`），等回音。`state=dead` 的讓 daemon 自己重拉。
   死了的 daemon 自己會重拉，這裡不用管；重生那顆手上若有 `req`，它的開機對帳會回 `Interrupted`
   （原單還沒開始的它照做，不是每件都 `Interrupted`），下格在第 6 步照常收。
8. **派工**（`phase=running` 才做）：每顆 `req` 為 null 的工作 cpu，從 `queue` 頭找第一個 pool 相符且
   `not_before` 已到的行程 → 從 queue 拿掉、`status=running`、`req`＝`k-<chain>-<N>-<c>.json`、`proc`＝NAME、
   **寫帳本** → **放檔**（`aos-exec`，params 照行程紀錄：`target`／`dir_target`／`args`（有才放）／`timeout_ms`）。
   崩在寫帳本之後、放檔之前＝第 6 步補放。**先記後放**，所以永遠不會同一行程派兩顆。
9. **停機**（`phase=stopping`）：先把 `queued` 的 `once` 全部拿掉、各回 `-32000`／`Stopping`（進 `replies`）。
   然後所有工作 cpu `req` 為 null、四張出貨箱空、沒有任何 `pending` → `stops`＝所有 cpu（含 `kcpu`）、
   `phase=stopped`、**寫帳本** → 第 10 步出貨。kernel cpu 收到 stop 就不會再跑已排的下一格，那份殘格留著，
   下次 boot 換了 chain 它會自滅。崩在寫帳本之後、放完之前＝下格（若還跑得到）第 2 步補放；跑不到
   （kernel cpu 已停）就算了——boot 會把舊的 `stops` **丟掉**不重放（§6），因為那些 stop 是給上一代 cpu 的。
   `stopped` 之後再來的 syscall／ack 沒人處理，留在 `K/requests/`，下次 boot 的第 1 格會收。
10. **出貨**（同第 4 步）、**寫帳本**、append `kernel.log`、退 0。

一格裡 daemon 或磁碟出錯：stderr 一行、退 1、可能只做了一半；帳本＋出貨箱讓下格接得上。

## 4. 回音怎麼判

回音是範式 §4.1 的 aos-exec 回音。先看 cpu 那格的 `discard`：是 → 丟掉、行程紀錄拿掉，不計數
（`once` 的 pending 在 rm 時就回過 `Removed` 了）。再分兩種：

**`once`**：不管內容是什麼，把回音原樣（`result` 或 `error`）當成 `pending` 那則 add 的回音進 `replies`，
行程紀錄拿掉。`stopped:true` 也原樣交，交件者自己決定。

**反覆**：照順序第一個命中的列做，每列寫清楚兩個計數：

| 回音 | `runs` | `fails` | 之後 |
|---|---|---|---|
| `result.stopped = true` | 不動 | 不動 | 回 queue（`not_before` 不動） |
| `error`（含 `Interrupted`） | 不動 | +1 | 看退件 |
| `result.kind = aos` | +1 | +1 | 看退件 |
| `result.code = done_exit`（done_exit ≠ 0） | +1 | 歸 0 | `status=done`，不回 queue |
| `result.code` 是 0 或 101 | +1 | 歸 0 | 回 queue（101＝在等，不算錯） |
| 其他非零 | +1 | +1 | 看退件 |

看退件＝`fails` 達 `bad_after`（≠ 0）→ `status=bad`、不回 queue；沒達 → 回 queue。
回 queue＝`status=queued`、`not_before = now + interval_ms`、排到 `queue` 尾。
**每次派工對應恰好一則回音**，計數才準；沒有 quantum、沒有 runs 差值、沒有另外的 aos 計數。

## 5. 跟 daemon 講話

kernel 對 daemon 只做兩件事：`spawn`（每格第 7 步）、`kill`（只有 boot）。看孩子活不活是偷看 `D/state.json`
（唯讀）；看 daemon 本身活不活是對 `D/.daemon.lock` 試拿**非阻塞的共享 flock**——拿不到＝daemon 持著獨占鎖＝活著，
拿到了就馬上放掉＝沒有 daemon（[daemon §6.1](daemon.md)）。不看 pid。
放單、等 `D/responses/` 同名回音（最多 5000 ms，逾時＝`-32000`／`ReadFailed`，**逾時不代表沒做**，
下格重送是安全的）、ack 進 `acks`。

| method | kernel 怎麼用 |
|---|---|
| `spawn {"name","target","restart":true}` → `{"pid"}` | `name`＝cpu 名；`target`＝`K/cpus/<c>/inst.json`（argv `aos-cpu K/cpus/<c>`、cwd 那個家、stderr 接 `cpu.log` append、`envs` 照 info）；`restart:true`＝非 0 退出 daemon 自己再拉。同名同 target 已活著＝回它的 pid、不重拉；同名**不同** target＝`NameTaken`——兩個 kernel 共用一個 daemon 又都叫 `k` 會在這裡大聲失敗，不會靜默搶到別人的孩子 |
| `kill {"name"}` | boot 用它收掉舊的 kernel cpu：取消重拉、走階梯、死透從孩子表消失（[daemon §3](daemon.md)） |

## 6. 命令列

```sh
aos-kernel init K                     # 建家、預設 info（cpus: k＋0、1、2）；拒絕覆蓋
aos-kernel boot K [--daemon D] [--wait-ms N]   # 見下；不跑整格
aos-kernel tick K --chain C --seq N   # 一格；正常只有鏈自己會叫
aos-kernel add K TARGET [--name NAME] [--once] [--pool P] [--wait-ms N]
aos-kernel rm K NAME
aos-kernel ls K                       # 偷看 K/state.json、D/state.json、kernel cpu 的 state.json 與 requests/；不放單，鏈斷了也能看
aos-kernel stop K
```

**boot** 只做「交接、拉起來、放第 1 格」，K 的帳本從此只在 kernel cpu 上被改。**兩個 boot 不能同時跑**——
這是給人的規矩，不在保證內（沒有 boot 鎖）。步驟：
1. K 轉絕對路徑；`cli/aos-kernel` 取自己的 realpath、驗有執行位；驗 D 是 daemon 家、daemon 活著（§5 的 flock 探測）；
   info 整份驗過（頂層字面物件、恰好一顆 kernel 池）。這一步不改任何東西。
2. **交接**：kernel 池那顆叫 c。偷看 `D/state.json`：表裡有 c 且 `target` 不是我們的 → `NameTaken`、退 1。
   表裡有 c（不管 alive／dead）→ 向 daemon `kill c`（`NotFound` 也算成功），然後**等到 c 從孩子表消失**
   （最多 `--wait-ms`，預設 30 秒）。逾時＝退 1、`AlreadyRunning`——**kill 已送出、不會撤回**，舊的那格做完
   還是會被收掉，只是 chain 沒換；等一下再 boot 一次就好。c 消失＝沒有任何一格在跑、也不會再有——這才是「舊鏈停了」的證據。
3. 寫 info.daemon；帳本：`chain`＝新 id、`kcpu`＝c、`cli`、`last_seq`＝0、`phase`＝running、**`stops` 清空**
   （上一條鏈欠的 stop 是給上一代 cpu 的，不重放）；`cpus`／`queue`／`procs`／`acks`／`replies`／`deletes` **照舊**
   （在途 `req`、`pending` 都留著，新鏈接手收；名字帶舊 chain 沒關係，收的是舊名、ack 用新名）。
4. 每顆 cpu：家不在才建（info、inst，`envs` 照 info）；`spawn` 全部、等回音（c 剛被收掉，這裡拉回來；
   其他活著的同名同 target 就回 pid、不動）。
5. `link` 第 1 格 `k-<chain>-1.json` 到 `cpus/<c>/requests/`。退 0。

再 boot 一次＝重做第 2 步的交接再開新鏈；舊鏈殘格帶著舊 chain 自滅。
**daemon 重啟過**（孩子表被清空）也要 boot——kernel cpu 死了沒人會放第 1 格，「每格補拉」補的是工作 cpu。

**add**：TARGET 轉絕對路徑放單（kernel 不解指示詞，指示詞是跑的時候 aos-exec 以它自己的規則解——`.json`
是檔所在資料夾、資料夾目標是資料夾本身）。反覆＝等回音印 NAME；`--once` 預設不等、印自己取的檔名
（`--name` 沒給時 NAME 就用這個檔名），`--wait-ms N` 才等跑完印回音。**stop** 只確認放單成功。
其餘等回音最多 10 秒。D 預設 `AOS_DAEMON_HOME`，再預設 `~/.aos-daemon`。

**ls** 印帳本的摘要（chain、phase、每顆 cpu 的 req／proc、queue、每個行程的 status／runs／fails）、daemon 孩子表的
alive、還有 kernel cpu 的 `state.current` 跟它 `requests/` 裡有幾份——鏈斷了（`current` null、`requests/` 空、
`last_seq` 不動）就看得出來。

退出碼：0 成功；1 讀驗／daemon／I/O 錯，stderr 一行 `aos-kernel: <代號>: <白話>`；2 用法錯。

## 7. 為什麼這樣就不會重疊

- 同一顆 cpu 一次只做一件（範式 §4.1），kernel 又「先記 `req` 再放檔」、只在 `req` 為 null 時派——
  所以一份行程同時最多在一顆 cpu 上，不用讀任何人的快照。
- kernel 不會有兩格同時跑：格都排在帳本釘死的那顆 kernel cpu 上，那顆一次只做一件；boot 不跑格、先把舊 kernel cpu
  收掉等它從孩子表消失才開新鏈；舊鏈殘格靠 `chain` 自滅。
- 擋不住的：兩個 boot 同時跑（人的規矩）；人用手直接 `aos-cpu`／`aos-exec` 跑同一份 inst（規則一之外）；
  cpu 被 KILL 而子程式還活著（範式 §5.3，保證外）。

## 8. 這份沒管的

daemon 的 method 完整形狀、`restart`、daemon 自己怎麼停（[daemon](daemon.md)）；agent 怎麼用 `add --once`
問模型／跑工具（agent）；`aos-llm-call` 這支程式（之後）。

## 9. 已拍板的前提（使用者定的，不重問）

kernel 可以是 exec（tick 鏈）；`spawn` 有 `restart:true`，kernel cpu 死了靠它；rm 正在跑的行程後同名
add 拒絕到它跑完；stop 分 stopping／stopped 兩段，在途與 once 的回音收完才停；kind=aos 併進一般失敗、
沒有獨立 aos 計數；兩個 kernel 共用 daemon 而 cpu 同名＝`NameTaken` 大聲失敗。

## 10. 我自己選的（等你確認）

1. **kernel 跟 daemon 也走資料夾**，不走 pipe——pipe 在 cpu 手上，tick 是孫子。「只有 kernel 能叫 daemon」
   因此是軟性的，換來全系統兩條路一個信封。
2. **tick 用 aos-exec 的普通檔模式**（`target`＝帳本釘的 `cli`、`args` 帶 chain 與 seq），沒有 tick.json：
   chain 釘在 request 裡、不可變，殘格才真的會自滅。
3. **帳本＋四張出貨箱**：行程紀錄收進 state、`procs/` 資料夾拿掉；ack／回音／stop／刪原單先記再放；去重憑據是 `deletes`。
4. **boot 的交接是「叫 daemon `kill` 舊 kernel cpu、等它從孩子表消失」**，不是偷看 `current`；daemon 活不活用 flock 探測。
   代價：boot 最慢等一格做完＋階梯。兩個 boot 同時跑不保證。
5. **`kcpu`／`cli` 釘在帳本**：改 info 的 kernel 池不生效，要重 boot。
6. **`once` 的 add 回音延到跑完才回、內容就是執行結果**；stopping 期間還在排隊的 once 回 `Stopping`；rm 當下回 `Removed`。
7. **quantum／waiting／aos_ticks／last_target 全拿掉**，換 `interval_ms`＋`not_before`＋一次派工一則回音。
8. **cpu 分池用 `pool` 字串**；kernel 自己的池叫 `kernel`，恰好一顆。`info.cpus.<c>.envs` 抄進那顆的 inst。
9. **死掉的 cpu 只等 daemon 重拉**，它手上的單靠範式的開機對帳回 `Interrupted`。
10. **kernel 不讀 target 指的檔**，連在不在都不看；一切都是跑起來的回音。
11. **`ls` 不是 syscall**，直接偷看三個地方。
