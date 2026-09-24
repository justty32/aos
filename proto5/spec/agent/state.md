← [agent](README.md)｜[spec 總導航](../README.md)

# 4. `state.json`

```json
{"state": "act", "errors": 0, "input": "input.json", "waits": [],
 "batch": {"kind": "act", "kernel": "/abs/K", "base_len": 12, "sent": true,
           "calls": [{"name": "aw-bob-1790000000000000000-77-0", "tool_call_id": "call_a", "tool": "sh",
                      "done": null, "acked": false},
                     {"name": null, "tool_call_id": "call_b", "tool": "nope",
                      "done": {"content": "沒有這個工具：nope"}, "acked": true}]},
 "intake": null, "consuming": [], "sweep": [{"kernel": "/abs/K", "name": "aw-bob-1789999999000000000-70-0"}]}
```

| 鍵 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `state` | `idle`／`think`／`act` | `idle` | 走到哪。沒有 `wait` 這格——等是門或當批，不是狀態 |
| `errors` | 非負整數 | `0` | 問模型連敗次數（aos-agent.md §9） |
| `input` | 路徑或路徑陣列（可用指示詞） | `input.json` | 輸入從哪來（§4.1） |
| `waits` | 字面單條或字面陣列 | 沒寫＝不用等 | 外人的門（§4.2） |
| `batch` | 物件或 `null` | `null` | 當批（§4.3） |
| `intake` | 物件或 `null` | `null` | 收輸入做到一半的紀錄（§4.4） |
| `consuming` | 物件陣列 | `[]` | 已經從門劃掉、還沒搬到封存名的檔（§4.4） |
| `sweep` | 物件陣列 | `[]` | 等著清 `work/` 檔的工作名（§4.4） |

檔不存在＝全預設；存在但壞掉＝`ReadFailed`／`JsonSyntax`／`NotAnObject`。`state` 不是三個之一＝`StateInvalid`；其他型別錯＝`FieldTypeMismatch`。

## 4.1 `input`

指到的每個檔：字串→一則 user 訊息；一則訊息物件→原樣；訊息陣列→原樣一串（都照 §3.2 驗）。檔不存在或空陣列＝沒輸入。
收法：先把檔 rename 到唯一封存名 `<原檔所在資料夾>/done/<原檔名>.<消費 id>.done`（09-24 試玩 r1 補）（`done/` 不在就先建；慣例輸入在 agent 家，所以就是 agent 家的 `done/`；同資料夾 rename、不跨檔案系統）、**再從封存名讀**（aos-agent.md §8）。所以原路徑一空出來，寫輸入的人就可以再投一份同名檔，
不會被上一次的恢復吞掉。仍要遵守的一條：**不要蓋掉還沒被收的檔**（原路徑還在就是還沒收）——蓋掉的那份本來就讀不到。
封存檔（`done/` 裡）agent 不清，人自己清——但**還被 `state.json` 的 `intake`／`consuming` 引用的封存檔不准清、不准搬**（它是「這次已經搬過」的憑據，清了恢復會把原路徑上的新檔當成舊的搬走）；
等那筆引用解除（`intake` 回 null、`consuming` 清空）之後才能清。

## 4.2 `waits`

```json
"waits": [
  "continue.json",
  {"$opt": "consume", "$val": "continue.json"},
  {"$opt": "all", "$val": ["a.json", "b.json"]}
]
```

- 原始 JSON 裡是字面單條或字面陣列；讀進來一律當條目列表，程式寫回一律寫陣列。沒寫或 `[]`＝沒有門。
- 一條＝路徑字串，或選項物件 `{"$opt": 名字|[名字…], "$val": 路徑|[路徑…]}`（`$opt` 必寫：只有 `$val` 的物件在指示詞機制裡是 `UnknownDirective`）；`$val` 可再是指示詞，解完要是字串或非空字串陣列，否則 `FieldTypeMismatch`。
- 選項：`consume`（到了之後 rename 到唯一封存名，規則同 §4.1：`<原檔所在資料夾>/done/<原檔名>.<消費 id>.done`（09-24 試玩 r1 補））；`exists`、`all` 是預設、寫了也一樣；其他名字＝`UnknownOption`、重複＝`UnknownOption`。
- 「到了」：檔存在；資料夾裡有任何 `*.json`（`.done` 不算）。`$val` 是陣列＝全部到了才算這條到了。
- `consume` 指到資料夾＝到了那一刻把裡面所有 `*.json` 各自 rename 到自己的封存名。
- 加門的人要確定那個檔**現在不在**，不然門一加就開（agent 不替人分辨新舊訊號）。
- 這張表只給外人用（人要它暫停、別的程式要它等某個檔）；aos-agent 自己只會加一種條目：連敗暫停的 `continue-<批 id>.json`，每次名字都不同（aos-agent.md §9）。
  kernel 家的回音**不要**寫進 `waits`，更不要開 `consume`：回音是 kernel 的家，只能 ack（[cpu.md §3.3](../cpu/messages.md)）。

## 4.3 `batch`：當批紀錄

在途工作的身分只記在這裡。`null`＝手上沒有送出去的工作。

| 鍵 | 型別 | 意思 |
|---|---|---|
| `kind` | `think`／`act` | 問模型／跑工具 |
| `kernel` | 絕對路徑 | 送去哪個 kernel 家；收回、ack、清檔都用這個 K，不看當下的 `AOS_KERNEL_HOME` |
| `base_len` | 非負整數 | 建批那一刻記憶的長度；收回時記憶寫成「前 `base_len` 則＋這批的訊息」（所以重做不會重複接） |
| `sent` | 布林 | `false`＝還在送（崩了要重跑送件步驟）；`true`＝該送的都送了 |
| `calls` | 陣列 | 每個 call 一筆，順序＝接回記憶的順序。`think` 恰好一筆 |
| `calls[].name` | 字串或 `null` | 工作名；`null`＝這個 call 本地就結束了、沒送 |
| `calls[].tool_call_id`、`tool` | 字串 | 只有 `act` 有：對應 assistant 的 `tool_calls[i].id` 與 `function.name` |
| `calls[].done` | 物件或 `null` | 這個 call 的結果，已讀驗完、持久了；`null`＝還沒收 |
| `calls[].acked` | 布林 | 回音已 ack（或本來就沒有回音） |
| `access` | `null`、`{"error": 字串}` 或物件 | 只有 `act` 有（09-24 access-impl）：建批那一刻解好的權限牆快照（[§3.5](access.md)），同批每件、重送都用它。物件＝`{"mounts": {名: {"path": 絕對路徑, "ro": 布林}}, "cwd": 名或 null, "net": 布林}`，名照 `[a-z0-9_-]+`、`cwd` 要在 `mounts` 裡；`null`＝沒 access 檔（要關牢的工具不送，`NoAccess`）；`error`＝壞表（這批要關牢的工具都跑不起來）。沒這個鍵（舊版寫的）＝`null`；形狀不合＝`FieldTypeMismatch` |

（09-24 第 4 隊補）`batch` 另外有 `id`（批的身分，事件用）；`calls[]` 另外可有 `ms`（kernel 回音的經過毫秒或 null）、`ok`（這件成不成）兩個鍵：收回時寫、結清時記進事件（[events.md](events.md)），讀驗不看。

`done` 的形狀：`act` 是 `{"content": 給模型看的字串}`；`think` 是 `{"ok": true}`（答案留在 `work/<名>.out`）
或 `{"fail": 白話原因, "count": 布林}`（`count` 說算不算一次連敗）。怎麼算在 aos-agent.md §6。

## 4.4 `intake`、`consuming`、`sweep`

- **消費 id**：`<epoch ns>-<pid>`，每次收輸入、每次門劃掉 consume 條目各取一個新的；封存名 `<原檔所在資料夾>/done/<原檔名>.<消費 id>.done`（09-24 試玩 r1 補）因此永不重複。
  state 裡記的是當時算好的 `dst`，改版前寫下的舊式同資料夾封存名照原樣搬、讀。
- `intake`：`{"id": 消費 id, "base_len": 整數, "files": [{"src": 原路徑, "dst": 封存名}…]}`，都是絕對路徑。idle 收輸入時先記這筆、再搬檔、
  再從 `dst` 讀、再寫記憶；崩了下次照這筆做完（aos-agent.md §8）。
- `consuming`：`[{"src": 原路徑, "dst": 封存名}…]`。門的 `consume` 條目到了，先在同一次寫裡把它從 `waits` 劃掉、把這些對記到這裡，再搬（aos-agent.md §3）。
- 搬的規則（兩處共用）：`dst` 已在＝搬過了，**不碰 `src`**（那可能是新投的另一份）；`dst` 不在、`src` 在＝rename；兩個都不在＝略過。
  這條規則成立的前提：**被引用中的 `dst` 沒人動**（§4.1）。要放棄某一對（例如壞輸入），得先 `aos-agent stop`、等行程消失，**在 `state.json` 裡把那一對從 `intake.files`／`consuming` 拿掉**，
  之後才能動那個 `dst`；只刪 `dst` 不改 state，恢復會回頭去搬 `src`（aos-agent.md §8）。
- `sweep`：`[{"kernel": K, "name": 工作名}…]`。批結清時把這批的工作名放進來；確定那件工作在 K 裡結束了才刪它的 `work/` 檔（aos-agent.md §10）。
