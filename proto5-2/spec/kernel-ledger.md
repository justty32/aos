# kernel 的帳本（`K/state.json` 第 2 版）

← [spec 導航](README.md)｜每格怎麼用：[kernel-tick](kernel-tick.md)｜池的欄位：[kernel-pools](kernel-pools.md)

> 第 1 版，2026-09-24 草稿；未實作。**取代 [proto5/spec/kernel.md](../../proto5/spec/kernel.md) §1.2**：`cpus`（每顆一格）換成 `pools`＋`busy`，`queue` 拆成 `ready`＋`delayed`，拿掉 `stops`、加 `sends`、`on`。
> 也**取代 §2**「每則 syscall 一次帳本寫入」與 §3 第 4 步「每放完一筆寫帳本」（§3）。
> `procs` 的形狀與意思**完全不變**——[aos-agent.md §10](../../proto5/spec/aos-agent.md) 偷看它判斷「工作還在不在 cpu 上」。

仍是**唯一的帳本、一次原子寫**。帳本裡跟 cpu 有關的只記**忙的**，閒的只記號碼，不再每顆一個物件。

## 1. 範例

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
          "default/3": {"req": "k-1790000000000000000-4242-41-default-3.json", "proc": "carol", "discard": false},
          "llm/0":     {"req": "k-1790000000000000000-4242-39-llm-0.json", "proc": "agent-bob-t7", "discard": false}},
 "on": {"bob": "default/1", "carol": "default/3", "agent-bob-t7": "llm/0"},
 "recent": ["default/3"],
 "ready": {"default": [["erin", "cli-1790000000000000000-80.json"]], "llm": []},
 "delayed": [[1790000001.2, "frank", "cli-1790000000000000000-81.json"]],
 "procs": {"bob": {"…": "同 proto5 §1.2"}},
 "acks": [], "replies": [], "deletes": [],
 "sends": [{"home": "/abs/D", "name": "k-1790000000000000000-4242-41-scale-llm.json", "body": {"…": "scale 單"}}]}
```

## 2. 欄位

| 鍵 | 意思 |
|---|---|
| `chain`／`cli`／`last_seq`／`phase` | 同 proto5 |
| `kcpu` | 固定 `kernel/0`；留著給人看 |
| `pools.P.daemon`／`dpool` | 這池目前**實際**交給誰（搬池時照舊位置，直到舊池消失，[kernel-info §4](kernel-info.md)） |
| `pools.P.want` | 上一次處理過的 info `count`／`skip`（處理完當場更新） |
| `pools.P.sent`／`pending` | daemon 確認過的成員；送出還沒確認的那張單（檔名＋成員）。一池最多一張 |
| `pools.P.free` | 可以派的號碼，當堆疊用（從尾巴拿、放回尾巴）。條件見 [kernel-pools §1](kernel-pools.md) |
| `pools.P.draining` | 已不是成員、還在做事的號數；歸 0 時設 `dirty` |
| `pools.P.dirty`／`redeclare` | 要重算集合／要整份重送宣告（[kernel-pools §2](kernel-pools.md)） |
| `pools.P.envs_digest` | 上次寫 `envs.json` 時 info envs 的 SHA-256 前 16 字元 |
| `pools.P.error`／`retry_at` | daemon 最近一次的錯：`{"code": data.code, "message"}`；`Stopping` 時下次重試的格序號 |
| `busy` | **只有忙的 cpu**，key `P/<i>`，值同 proto5 的 `cpus.<c>`；閒了整格拿掉。寫入時**保持插入順序**（巡檢靠它輪轉） |
| `on` | 反查：行程 NAME → 它在哪顆（`rm` 一個 `running` 的行程時不用掃 `busy`，審查 R20） |
| `recent` | 上一格派出去的 cpu；下一格一定查一次 |
| `ready` | 每池一條先進先出，每格 `[NAME, request]` |
| `delayed` | 還沒到 `not_before` 的，每格 `[not_before, NAME, request]`，存成**二元堆積**（heap 陣列） |
| `procs` | 同 proto5 §1.2，一字不改 |
| `acks`／`replies`／`deletes` | 同 proto5 |
| `sends` | 往**別人家的 `requests/`** 放一張單（`home`、檔名、內容）。scale 單走這裡 |

**排隊的格帶 `request`**（審查 R10）：`request` 就是 `procs.NAME.request`（那次 `add` 的檔名，每次 add 都不同）。
拿出來時 `procs` 沒有 NAME、`status` 不是 `queued`、`request` 對不上、或（`delayed` 的）時間不等於 `procs.NAME.not_before`，就是舊格，丟掉。
所以 `rm` 排隊中的行程只刪 `procs` 那筆（懶刪），同名重 add 也不會撿到舊格的位置。
**舊格累積**：每池記「舊格數」，超過活格數就整條壓縮一次（O(那條長度)，攤還到每次 rm 是 O(1)）。

**一個行程在哪**：`queued` 的有且只有一個有效格（`ready` 或 `delayed`）；`running` 的在 `on` 與某格 `busy`；`done`／`bad` 只在 `procs`。

## 3. 什麼時候寫帳本（取代逐筆寫）

proto5 是「每則 syscall、每筆出貨寫一次」。上萬顆時一格可能幾百筆，每筆重寫整份太貴。改成固定的四個提交點（審查 R17）：

| 提交點 | 在第幾步 | 包含 |
|---|---|---|
| 1 | 第 2 步 | `last_seq`（先放後記，同 proto5） |
| 2 | 第 4 步出貨完 | 拿掉已出貨的項目 |
| 3 | 第 5～9 步全部決定完 | syscall 結果、收回音判定、池的決定、派工記錄、停機判定，連同新增的出貨項目 |
| 4 | 第 10 步出貨完 | 拿掉已出貨的項目 |

- 出貨是「全部放完（或刪完）→ 一次寫帳本拿掉」。中間崩了，下一格重放——`link` 的 EEXIST、刪檔的 ENOENT 都當成功，所以合併寫不改正確性，只是崩了會多放幾次。
- 派工仍是「先記後放」：提交點 3 之後才放派工單。
- syscall 仍是「先記後出貨」：判定進提交點 3，回音與刪原單在第 10 步出貨。崩在提交點 3 之前＝這格的判定全部沒發生，下一格重讀同樣的原單重判，冪等。

## 4. 還是 O(N) 的地方

帳本是整份讀、整份寫：tick 每格是新行程，**開頭要讀、解析整份**，大小跟 `procs`＋`busy`＋`free`＋`skip` 成比例。
上萬顆時約數百 KB 到幾 MB，每格讀一次、寫最多四次。這是這一版**接受**的，見 [scale](scale.md) §2。
