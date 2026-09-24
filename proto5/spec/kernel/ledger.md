← [kernel](README.md)｜[spec 總導航](../README.md)

## 1.2 `state.json`（帳本）

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
| `kcpu`、`cli` | boot 釘的：kernel cpu 的名字、`cli/aos-kernel` 的絕對路徑（tick 的 target 用它）。這兩格 tick 只認帳本；其他設定仍每格重讀 `info.json` |
| `last_seq` | 最後一格的序號，給人看；下一格的序號來自 tick 自己的 args，不從這裡拿 |
| `phase` | `running`／`stopping`／`stopped`（§3 第 9 步） |
| `cpus.<name>` | **只有工作 cpu**，kernel cpu 不在這裡。`req`＝派給它、還沒結清的 request 檔名，`null`＝閒（**cpu 忙不忙就看這格**）；`proc`＝那則是哪個行程的；`discard`＝那個行程已被 `rm`，回音到了丟掉 |
| `queue` | 等派工的行程 NAME，先進先出；`status=queued` 的都在這 |
| `procs.<NAME>` | 行程紀錄：`request`（當初那則 add 的檔名，給人看）、`target`／`dir_target`／`args`（沒給就沒這個鍵）／`once`／`pool`／`interval_ms`／`timeout_ms`（政策，add 之後不改）；`status`／`runs`／`fails`／`not_before`（下次最早可派的 epoch 秒）／`pending`（`once` 還沒回的那則 add：檔名＋id） |
| `acks`／`replies`／`stops`／`deletes` | 出貨箱（§0）：ack 給哪個家、哪個名；回音給 `K/responses/` 的檔名、id、內容；stop 給哪顆 cpu；哪些 syscall 原單該刪。§3 第 4 步與第 10 步出貨 |

NAME 是非空檔名，不能是 `.`／`..`、含 `/` 或 NUL。kernel **不讀 target 指的檔**，只記路徑。
重拉節奏、階梯進度這種執行中的東西不在帳本裡（那是 daemon 的）；帳本裡的每一格重啟後都還算數。

## 1.3 kernel 取的檔名

| 放到哪 | 檔名 | 誰的 |
|---|---|---|
| kernel cpu 的 `requests/` | `k-<chain>-<seq>.json` | 第 seq 格 tick |
| 工作 cpu `<c>` 的 `requests/` | `k-<chain>-<seq>-<c>.json` | 第 seq 格派給 c 的工作 |
| 任一 cpu 的 `requests/` | `ack-<chain>-<seq>-<c>-<digest>.json`（09-24 補，見表下）、`stop-<chain>.json` | ack、stop |
| daemon 的 `requests/` | `k-<chain>-<seq>-spawn-<c>.json`、`ack-<chain>-<seq>-<家名>-<digest>.json`、boot 用 `k-<chain>-boot-kill.json`（要收兩顆時各加 cpu 名：`k-<chain>-boot-kill-<c>.json`） | 拉 cpu、ack、boot 收舊 kernel cpu |

kernel 放出去的檔名全部帶 `chain`，跨 boot 永不重複；同一格對同一個家的同一種東西最多一份，所以格內也不重複。
這是範式 §1「名字不重用」在 kernel 這邊的做法。前提是 `chain` 本身不重複——`<epoch ns>-<pid>` 在同一台機器上夠用。

（09-24 補）ack 是例外：同格同家可能要好幾則（第 4 步補前格的、清多則舊 tick 回音、第 6 步收的），所以 ack 名稱為
`ack-<chain>-<seq>-<c>-<digest>.json`，digest 是**被 ack 的檔名**之 SHA-256 前 16 個十六進位字元。同格同家可以有多筆 ack，
不得把不同回音的確認合併成一則。
