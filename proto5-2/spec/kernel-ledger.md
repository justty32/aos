# kernel 的帳本（`K/state.json` 第 2 版）

← [spec 導航](README.md)｜每格怎麼用：[kernel-tick](kernel-tick.md)｜池的欄位：[kernel-pools](kernel-pools.md)

> 第 1 版，2026-09-24 草稿；未實作。**取代 [proto5/spec/kernel.md](../../proto5/spec/kernel.md) §1.2**：`cpus`（每顆一格）換成 `pools`＋`busy`，`queue` 拆成 `ready`＋`delayed`，拿掉 `stops`、加 `sends`。
> `procs` 的形狀與意思**完全不變**——[aos-agent.md §10](../../proto5/spec/aos-agent.md) 偷看它判斷「工作還在不在 cpu 上」。

仍是**唯一的帳本、一次原子寫**。改的目標：帳本裡跟 cpu 有關的只記**忙的**，閒的只記號碼，不再每顆一個物件。

## 1. 範例

```json
{"chain": "1790000000000000000-4242", "kcpu": "kernel/0", "cli": "/abs/proto5/cli/aos-kernel",
 "last_seq": 41, "phase": "running",
 "pools": {
   "default": {"daemon": "/abs/D", "dpool": "k1-default",
               "want": {"count": 8, "skip": []}, "sent": {"count": 8, "skip": []},
               "pending": null, "free": [0, 2, 5, 6, 7], "envs_digest": "3f1a…", "error": null},
   "llm":     {"daemon": "/abs/D", "dpool": "k1-llm",
               "want": {"count": 3, "skip": []}, "sent": {"count": 2, "skip": []},
               "pending": {"name": "k-1790000000000000000-4242-41-scale-llm.json", "count": 3, "skip": []},
               "free": [1], "envs_digest": "9c0d…", "error": null}},
 "busy": {"default/1": {"req": "k-1790000000000000000-4242-40-default-1.json", "proc": "bob", "discard": false},
          "default/3": {"req": "k-1790000000000000000-4242-41-default-3.json", "proc": "carol", "discard": false},
          "default/4": {"req": "k-1790000000000000000-4242-38-default-4.json", "proc": "dave", "discard": false},
          "llm/0":     {"req": "k-1790000000000000000-4242-39-llm-0.json", "proc": "agent-bob-t7", "discard": false}},
 "recent": ["default/3"],
 "ready": {"default": ["erin"], "llm": []},
 "delayed": [[1790000001.2, "frank"], [1790000003.0, "gina"]],
 "procs": {"bob": {"…": "同 proto5 §1.2"}},
 "acks": [], "replies": [], "deletes": [],
 "sends": [{"home": "/abs/D", "name": "k-1790000000000000000-4242-41-scale-llm.json", "body": {"…": "scale 單"}}]}
```

## 2. 欄位

| 鍵 | 意思 |
|---|---|
| `chain`／`cli`／`last_seq`／`phase` | 同 proto5 |
| `kcpu` | 固定 `kernel/0`（kernel 池只有 0 號）；留著給人看 |
| `pools.P.daemon`／`dpool` | 這池目前**實際**交給誰（info 改了也照這個，直到搬完，[kernel-info §4](kernel-info.md)） |
| `pools.P.want` | 上一次處理過的 info `count`／`skip`。跟 info 一樣＝沒變，這格不用算集合 |
| `pools.P.sent` | daemon **已經回音確認**的成員（`count`＋`skip`） |
| `pools.P.pending` | 送出去還沒收到回音的那張 scale 單：檔名＋要的成員。一池同時最多一張 |
| `pools.P.free` | 閒著、可以派的號碼（當堆疊用：從尾巴拿、放回尾巴） |
| `pools.P.envs_digest` | 上次寫 `envs.json` 時 info envs 的 SHA-256 前 16 字元 |
| `pools.P.error` | daemon 最近一次對 scale 回的錯（`{"code","message"}`），給 `ls` 看；成功就清 null |
| `busy` | **只有忙的 cpu**，key 是 `P/<i>`。值同 proto5 的 `cpus.<c>`（`req`／`proc`／`discard`）；閒了就整格拿掉 |
| `recent` | 上一格派出去的 cpu。下一格一定查一次（補「記了還沒放」那個窗口，[kernel-tick](kernel-tick.md) 第 6 步） |
| `ready` | 每池一條先進先出：`not_before` 已到、等派工的行程 |
| `delayed` | 還沒到 `not_before` 的行程，照時間排好的 `[epoch 秒, NAME]` |
| `procs` | 同 proto5 §1.2，一字不改 |
| `acks`／`replies`／`deletes` | 同 proto5 的出貨箱 |
| `sends` | 新出貨箱：往**別人家的 `requests/`** 放一張單（`home`、檔名、內容）。scale 單走這裡 |

拿掉的：`cpus`（→ `pools`＋`busy`）、`queue`（→ `ready`＋`delayed`）、`stops`（停機改成把池縮到 0，[handoff §3](handoff.md)）。

**一個行程在哪**：`status=queued` 的在 `ready` 或 `delayed` 其中一個、只在一個；`running` 的在某格 `busy` 的 `proc`；
`done`／`bad` 只在 `procs`。這跟 proto5「`queued` 的都在 `queue`」是同一條規矩換了兩個容器。

**閒、忙、收掉中**：一顆 cpu 在不在 `free` 或 `busy`，看它是不是 info 要的成員：
- 是成員、`busy` 沒它 → 在 `free`。
- 不是成員了（縮小中）、還在 `busy` → 收完這件就**不回** `free`，它的號留在 `sent` 裡直到下一張 scale 單把它拿掉。
- `sent` 沒確認過的新號不進 `free`——scale 單回成功才進（[kernel-pools](kernel-pools.md)）。

## 3. 寫帳本的次數

proto5 是「出貨箱每做完一筆就寫一次帳本」。上萬顆時一格可能出幾百筆，每筆重寫一次整份帳本太貴。改成：

- **一格最多寫四次**：第 2 步（`last_seq`）、第 6～9 步的所有決定合成一次、第 4 步與第 10 步出貨各一次。
- 出貨是「全部放完（或刪完）→ 一次寫帳本拿掉」。中間崩了，下一格重放一遍——每種出貨本來就可以重做（`link` 的 EEXIST、刪檔的 ENOENT 都當成功），所以合併寫不改變正確性，只是崩了會多放幾次。
- 派工仍是「先記後放」：這格要派的全部先記進帳本（一次寫），再逐一放檔。

**取代 proto5 kernel.md §3 第 4 步**「每放完一筆寫帳本拿掉」。

## 4. 還是 O(N) 的地方

帳本仍是整份一次寫：大小跟 `procs` 數＋`busy` 數＋`free` 號碼數成比例。上萬顆時約數百 KB 到幾 MB，每格寫最多四次。
這是這一版**接受**的，理由與替代方案在 [scale](scale.md) §2。
