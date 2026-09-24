← [cpu](README.md)｜[spec 總導航](../README.md)

# 1. 資料夾與規則一

```text
C/
  info.json           身分與設定；人寫的（啟動前）
  state.json          主人寫的現況；原子替換
  requests/<n>.json   下一個指令；外人只能原子放進來
  responses/<n>.json  回音，檔名照 request；收件者 ack 之後主人才刪
  cpu.log             主人的 stderr（由拉起它的人接）
```

**規則一（一個家一個主人）**：只有主人行程會改這個家。外人被允許的動作只有兩個，都是往
`requests/` 放檔：(a) 放一則 request（§3.1）；(b) 放一則 `ack`，說「`responses/` 那份我拿走了」（§3.3）。
外人**讀** `responses/`、`state.json`、`requests/` 隨意（偷看），但不刪不改。現在是軟性約定、靠自律；要硬性的以後走 FUSE。

所以這裡**沒有鎖**：放單靠 `link` 的「有就失敗」、換檔靠 `rename` 的原子性。沒有 `running/`
（正在做哪一件在 `state.json`）、沒有 `bad/`（壞單也回音，§4.3）、沒有收屍（主人死了拉它的人
立刻知道；死在哪件上，下一任開機對帳處理，§6.2）。

**名字不重用**：一個家裡，request 的檔名一旦用過（放過、做過、回音 ack 掉了）就**不能再給另一件工作用**。
`link` 只擋「當下同名」，擋不了「刪掉後再用同名」；再用同名會讓遲到的 ack 刪錯回音、舊回音被當成新結果。
慣例 `<交件者名>-<epoch ns>-<交件者 pid>`；kernel 另有帶鏈 id 的取名法（[kernel §1.3](../kernel/names.md)）。
唯一性是交件者的責任，cpu 不查歷史。

# 2. `info.json` 與 `state.json`

```json
{"_metainfo": {"_type": "exec_cpu", "_version": 1}, "poll_ms": 20, "timeout_ms": 0}
```

| 鍵 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `_metainfo` | 物件 | 必填 | `_type` 說主人是哪支程式（exec cpu＝`exec_cpu`、kernel＝`kernel`、daemon＝`daemon`）；`_version` 只認整數 1 |
| `poll_ms` | 正整數 | 20 | 沒事時看一次 `requests/` 的間隔（不准 0，避免空轉） |
| `timeout_ms` | 非負整數 | 0 | request 沒帶 `timeout_ms` 時的預設；0＝不限 |
| `notify` | 絕對路徑（資料夾） | 沒這個鍵＝不通知 | 每則回音發出去之後，往這個資料夾放一張通知（[§6.4](notify.md)；2026-09-24 池式納入加）。鍵在但不是絕對路徑字串（含 `null`）＝`FieldTypeMismatch` |

讀的時候先展開 [指示詞](../directives/README.md)（`$ref` 的相對路徑從 C 算起），再驗欄位型別；不提供 `$opt`。缺檔、身分不合＝`NotAHome`。

```json
{"pid": 1234, "current": {"name": "agent-1790000000000000000-77.json", "id": "agent-1790000000000000000-77", "notify": false}, "runs": 3}
```

| 鍵 | 意思 |
|---|---|
| `pid` | 主人的 PID。有 pid 不代表活著——活不活問拉它起來的人，不從這裡猜 |
| `current` | 正在做的那件：`name` 是 request 檔名（含 `.json`）、`id` 是它的 JSON-RPC id、`notify` 是不是 notification（是＝不寫回音）。閒著是 `null` |
| `runs` | 做完幾件 |

主人啟動時寫一次、每件開始與結束各寫一次；閒著不重寫。
