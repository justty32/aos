← [kernel](README.md)｜[spec 總導航](../README.md)

## 1.2（續）帳本每個鍵的意思

（2026-09-24 one-boot 從 [ledger.md](ledger.md) 拆出來：那邊講表與什麼時候存，這邊講讀進記憶體後每個鍵是什麼。形狀跟第 2 版一樣，只差 `kcpu`、`pools.kernel` 拿掉、`on` 不存、多 `version`、`ticker`、`last_tick_at`。）

## 讀進記憶體後的樣子

```json
{"version": 3, "chain": "1790000000000000000-4242", "cli": "/abs/proto5/cli/aos-kernel", "ticker": "/abs/D",
 "last_seq": 41, "last_tick_at": 1790000041.3, "phase": "running",
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
| `version` | 帳本版本，固定 3（`meta` 表）。不是 3＝`LedgerVersion` |
| `chain` | 這次 boot 的編號（`<epoch ns>-<pid>`；名字沿用第 2 版的鏈 id）。kernel 取的檔名都帶它，scale 單的 `decl` 也用它 |
| `cli`、`ticker` | `cli`＝boot 釘的 `cli/aos-kernel` 絕對路徑（登記給 daemon，daemon 用它開 tick）；`ticker`＝替這個 kernel 開 tick 的 daemon 家（boot 登記的那個，停好時向它撤登記）。第 2 版的 `kcpu` 拿掉 |
| `last_seq`／`last_tick_at`／`phase` | 最後一格的序號（下一格＝它＋1，只拿來取名）；最後一格做完決定的時間（epoch 秒，health 看它判「tick 停住」）；`running`／`stopping`／`stopped`（§3 第 9 步） |
| `pools.P.daemon`／`dpool` | 這池目前**實際**交給誰（搬池時照舊位置，直到舊池消失，[§1.1](info.md)） |
| `pools.P.want` | 上一次處理過的 info `count`／`skip`（處理完當場更新；新池還沒處理過＝`null`） |
| `pools.P.sent`／`pending` | daemon 確認過的成員；送出還沒確認的那張單（檔名＋成員）。一池最多一張 |
| `pools.P.free` | 可以派的號碼，當堆疊用（從尾巴拿、放回尾巴）。條件見 [§3.1](pools.md) |
| `pools.P.draining` | 已不是成員、還在做事的號數；歸 0 時設 `dirty` |
| `pools.P.dirty`／`redeclare` | 要重算集合／要整份重送宣告（§3.1） |
| `pools.P.boot_redeclare` | boot 設 true：只有**這次 boot**送出那張的成功回音才清掉；舊的回音照收但不清（實作 D-48） |
| `pools.P.acquired` | daemon 確認過這個位置一次沒有；false 的位置換走時不等舊池消失（實作 D-49） |
| `pools.P.envs_digest` | 上次寫 `envs.json` 時 info envs 的 SHA-256 前 16 字元 |
| `pools.P.error`／`retry_at` | daemon 最近一次的錯：`{"code": data.code, "message"}`；`Stopping` 時下次重試的格序號 |
| （已拿掉）`pools.kernel` | 第 2 版 kernel 池那格。one-boot 起沒有；舊帳本匯入時 boot 先把它縮到 0、收乾淨再拿掉（[§6 boot](boot.md)） |
| `busy` | **只有忙的 cpu**，key `P/<i>`，值 `{req, proc, discard}`：`req`＝派給它、還沒結清的 request 檔名；`proc`＝哪個行程的；`discard`＝那個行程已被 `rm`，回音到了丟掉。閒了整格拿掉。**保持插入順序**（巡檢靠它輪轉；sqlite 裡靠 `ord`） |
| `on` | 反查：行程 NAME → 它在哪顆（`rm` 一個 `running` 的行程時不用掃 `busy`）。**不存**：讀帳本時從 `busy` 反推（one-boot） |
| `recent` | 上一格派出去的 cpu；下一格一定查一次 |
| `ready` | 每池一條先進先出，每格 `[NAME, request]` |
| `delayed` | 還沒到 `not_before` 的，每格 `[not_before, NAME, request]`，存成**二元堆積**（heap 陣列） |
| `stale` | 每池的舊格數（見下） |
| `halting` | 停機時「縮池」階段（§3 第 9 步） |
| `procs.<NAME>` | 行程紀錄：`request`（當初那則 add 的檔名）、`target`／`dir_target`／`args`（沒給就沒這個鍵）／`once`／`pool`／`interval_ms`／`timeout_ms`（政策，add 之後不改）；`status`／`runs`／`fails`／`not_before`（下次最早可派的 epoch 秒）／`pending`（`once` 還沒回的那則 add：檔名＋id，（09-24 停車）帶 `wake` 的再加 `wake`）。（09-24 停車）`park_ms`（政策，add 時定）；`woken`（跑著時被叫醒過，判完清掉）；`parked`（上一格退 102 停著，給 `ls` 看；叫醒、派出去、或下一次判定清掉）——這三個舊帳本沒有，沒有＝info 預設／false |
| `acks`／`replies`／`deletes` | 出貨箱：ack 給哪個家、哪個名；回音給 `K/responses/` 的檔名、id、內容（09-24 停車：可帶 `wake`，出貨時叫醒，§2）；哪些 syscall 原單該刪 |
| `features` | （09-24 停車）這個 kernel 認得的能力，現在是 `["park", "again"]`（認得退出碼 102 與 `wake`；09-24 tick-gap 加 `again`＝認得 103）。每格讀帳本時補上；`aos-agent start` 看它（[register](../aos-agent/register.md)） |
| `sends` | 出貨箱：往**別人家的 `requests/`** 放一張單（`home`、檔名、內容）。scale 單、停好時撤登記的 `tick` 單走這裡 |
