← [kernel](README.md)｜[spec 總導航](../README.md)

## 1.2 `state.json`（帳本第 2 版）

（2026-09-24 proto5-2 池式納入：`cpus`（每顆一格）換成 `pools`＋`busy`，`queue` 拆成 `ready`＋`delayed`，拿掉 `stops`、加 `sends`、`on`。）
`procs` 的形狀與意思**完全不變**——[aos-agent §10](../aos-agent/pause-clean.md) 偷看它判斷「工作還在不在 cpu 上」。kernel 取的檔名見 [§1.3](names.md)。

仍是**唯一的帳本、一次原子寫**。帳本裡跟 cpu 有關的只記**忙的**，閒的只記號碼，不再每顆一個物件。

```json
{"chain": "1790000000000000000-4242", "kcpu": "kernel/0", "cli": "/abs/proto5/cli/aos-kernel",
 "last_seq": 41, "phase": "running",
 "pools": {
   "default": {"daemon": "/abs/D", "dpool": "k1-default",
               "want": {"count": 8, "skip": []}, "sent": {"count": 8, "skip": []}, "pending": null,
               "free": [0, 2, 5, 6, 7], "draining": 0, "dirty": false, "redeclare": false,
               "envs_digest": "3f1a…", "error": null, "retry_at": null},
   "llm":     {"daemon": "/abs/D", "dpool": "k1-llm",
               "want": {"count": 3, "skip": []}, "sent": {"count": 2, "skip": []},
               "pending": {"name": "k-1790000000000000000-4242-41-scale-llm.json", "count": 3, "skip": []},
               "free": [1], "draining": 0, "dirty": false, "redeclare": false,
               "envs_digest": "9c0d…", "error": null, "retry_at": null}},
 "busy": {"default/1": {"req": "k-1790000000000000000-4242-40-default-1.json", "proc": "bob", "discard": false},
          "llm/0":     {"req": "k-1790000000000000000-4242-39-llm-0.json", "proc": "agent-bob-t7", "discard": false}},
 "on": {"bob": "default/1", "agent-bob-t7": "llm/0"},
 "recent": ["default/1"],
 "ready": {"default": [["erin", "cli-1790000000000000000-80.json"]], "llm": []},
 "delayed": [[1790000001.2, "frank", "cli-1790000000000000000-81.json"]],
 "procs": {"bob": {"request": "cli-1790000000000000000-77.json", "target": "/abs/agent-bob/tick.json",
                   "dir_target": ".aos/inst.json", "once": false, "pool": "default", "interval_ms": 1000, "timeout_ms": 0,
                   "status": "running", "runs": 7, "fails": 0, "not_before": 1790000001.2, "pending": null}},
 "acks": [], "replies": [], "deletes": [],
 "sends": [{"home": "/abs/D", "name": "k-1790000000000000000-4242-41-scale-llm.json", "body": {"…": "scale 單"}}]}
```

| 鍵 | 意思 |
|---|---|
| `chain` | 這條鏈的 id，boot 給的（`<epoch ns>-<pid>`）。tick 帶著它來，對不上就是舊鏈的殘格 |
| `kcpu`、`cli` | `kcpu` 固定 `kernel/0`，留著給人看；`cli`＝boot 釘的 `cli/aos-kernel` 絕對路徑（tick 的 target 用它） |
| `last_seq`／`phase` | 最後一格的序號（給人看）；`running`／`stopping`／`stopped`（§3 第 9 步） |
| `pools.P.daemon`／`dpool` | 這池目前**實際**交給誰（搬池時照舊位置，直到舊池消失，[§1.1](info.md)） |
| `pools.P.want` | 上一次處理過的 info `count`／`skip`（處理完當場更新；新池還沒處理過＝`null`） |
| `pools.P.sent`／`pending` | daemon 確認過的成員；送出還沒確認的那張單（檔名＋成員）。一池最多一張 |
| `pools.P.free` | 可以派的號碼，當堆疊用（從尾巴拿、放回尾巴）。條件見 [§3.1](pools.md) |
| `pools.P.draining` | 已不是成員、還在做事的號數；歸 0 時設 `dirty` |
| `pools.P.dirty`／`redeclare` | 要重算集合／要整份重送宣告（§3.1） |
| `pools.P.boot_redeclare` | boot 設 true：只有**這條鏈**送出那張的成功回音才清掉；舊鏈的回音照收但不清（實作 D-48） |
| `pools.P.acquired` | daemon 確認過這個位置一次沒有；false 的位置換走時不等舊池消失（實作 D-49） |
| `pools.P.envs_digest` | 上次寫 `envs.json` 時 info envs 的 SHA-256 前 16 字元 |
| `pools.P.error`／`retry_at` | daemon 最近一次的錯：`{"code": data.code, "message"}`；`Stopping` 時下次重試的格序號 |
| `pools.kernel` | 只有 `daemon`／`dpool`／`sent`／`pending`；第 7 步不碰它（只有 boot、停機碰） |
| `busy` | **只有忙的 cpu**，key `P/<i>`，值 `{req, proc, discard}`：`req`＝派給它、還沒結清的 request 檔名；`proc`＝哪個行程的；`discard`＝那個行程已被 `rm`，回音到了丟掉。閒了整格拿掉。寫入時**保持插入順序**（巡檢靠它輪轉） |
| `on` | 反查：行程 NAME → 它在哪顆（`rm` 一個 `running` 的行程時不用掃 `busy`） |
| `recent` | 上一格派出去的 cpu；下一格一定查一次 |
| `ready` | 每池一條先進先出，每格 `[NAME, request]` |
| `delayed` | 還沒到 `not_before` 的，每格 `[not_before, NAME, request]`，存成**二元堆積**（heap 陣列） |
| `stale` | 每池的舊格數（見下） |
| `halting` | 停機時「縮池」階段（§3 第 9 步） |
| `procs.<NAME>` | 行程紀錄：`request`（當初那則 add 的檔名）、`target`／`dir_target`／`args`（沒給就沒這個鍵）／`once`／`pool`／`interval_ms`／`timeout_ms`（政策，add 之後不改）；`status`／`runs`／`fails`／`not_before`（下次最早可派的 epoch 秒）／`pending`（`once` 還沒回的那則 add：檔名＋id） |
| `acks`／`replies`／`deletes` | 出貨箱：ack 給哪個家、哪個名；回音給 `K/responses/` 的檔名、id、內容；哪些 syscall 原單該刪 |
| `sends` | 出貨箱：往**別人家的 `requests/`** 放一張單（`home`、檔名、內容）。scale 單走這裡 |

NAME 是非空檔名，不能是 `.`／`..`、含 `/` 或 NUL。kernel **不讀 target 指的檔**，只記路徑。
重拉節奏、孩子活不活這種執行中的東西不在帳本裡（那是 daemon 的）。

**排隊的格帶 `request`**：`request` 就是 `procs.NAME.request`（那次 `add` 的檔名，每次 add 都不同）。
拿出來時 `procs` 沒有 NAME、`status` 不是 `queued`、`request` 對不上、或（`delayed` 的）時間不等於 `procs.NAME.not_before`，就是舊格，丟掉。
所以 `rm` 排隊中的行程只刪 `procs` 那筆（懶刪），同名重 add 也不會撿到舊格的位置。
**舊格累積**：每池記舊格數（`stale`），超過活格數就整條壓縮一次（O(那條長度)，攤還到每次 rm 是 O(1)）。

**一個行程在哪**：`queued` 的有且只有一個有效格（`ready` 或 `delayed`）；`running` 的在 `on` 與某格 `busy`；`done`／`bad` 只在 `procs`。

## 什麼時候寫帳本

第 1 版是「每則 syscall、每筆出貨寫一次」。上萬顆時一格可能幾百筆，每筆重寫整份太貴。改成固定的四個提交點：

| 提交點 | 在第幾步 | 包含 |
|---|---|---|
| 1 | 第 2 步 | `last_seq`（先放後記） |
| 2 | 第 4 步出貨完 | 拿掉已出貨的項目 |
| 3 | 第 5～9 步全部決定完 | syscall 結果、收回音判定、池的決定、派工記錄、停機判定，連同新增的出貨項目 |
| 4 | 第 10 步出貨完 | 拿掉已出貨的項目 |

- 出貨是「全部放完（或刪完）→ 一次寫帳本拿掉」。中間崩了，下一格重放——`link` 的 EEXIST、刪檔的 ENOENT 都當成功，所以合併寫不改正確性，只是崩了會多放幾次。
  scale 單重放前先看對方 `responses/` 有沒有同名回音，有就不再放（實作 D-25）。
- 派工仍是「先記後放」：提交點 3 之後才放派工單。
- syscall 仍是「先記後出貨」：判定進提交點 3，回音與刪原單在第 10 步出貨。崩在提交點 3 之前＝這格的判定全部沒發生，下一格重讀同樣的原單重判，冪等。

帳本仍是整份讀、整份寫，大小跟 `procs`＋`busy`＋`free`＋`skip` 成比例（[§11](scale.md)）。
