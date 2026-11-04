# 探針 ledger：父子委派帳

← [probes](../README.md)｜出處：[astra 調查報告二 §14 實驗二](../../notes/research/2026-10-03-other-os-borrow.md)（§11.2 的守恆式與 split 範例）

全離線：provider 是 mock，不打任何模型。約 3 秒。

- **帳本** `ledger.py`：node `bank` 的 keep 任務，是唯一寫 ledger 的人。
  - 單一寫入靠 keep 保證只有一個活的，另外拿 `ledger/writer.lock` 的 flock。
  - 收 `bank/io/requests/*.json`，寫 `bank/io/receipts/<request_id>.json`，回條寫好才刪請求。
  - 帳是只加不改的 `ledger/events.jsonl`。每次起來從事件重播；同一個 request_id 已經落帳，就照事件補回條（`replayed`），不記第二筆。
  - 支援的請求：`delegate`（split，全有或全無，可帶 `expected_revision`）、`reserve`、`claim`（一筆保留額只給一個 attempt）、`settle`（用量取 provider 回條，不信 client 自報）、`release`（已 claim、provider 沒回條＝在途未知，不放）、`return`。
- **provider** `provider.py`：node `provider` 的 keep 任務，P、Q 共用。
  - 執行前查帳本發布的 `reservations/<res_id>.json`：要是 reserved，而且 claim 它的就是這個 attempt。
  - 付錢的人取帳上那筆保留額的 root，不看請求自己寫的。
  - 副作用記在 `executed.jsonl`；重起後照這份帳補回條，不重做。
- **worker** `worker.py`：spawn 起的一次性任務，依序 reserve → claim → 呼叫 provider → settle。每步的 request_id 固定，進度存在 `<node>/jobs/<job>.state.json`；被 kill 後新 worker 接著做。
- **探針**自己當 P 的 kernel，直接寫帳本請求。
- **獨立重算器**是 `probe.py` 的 `recompute`，跟 ledger.py 分開寫，把每個事件當成「桶子之間搬額度」。每一步都從 events.jsonl 重算、比對帳本的 summary，並驗這幾條：
  - `limit = spent + reserved + delegated_unspent + free`；
  - 每個桶子都不為負；
  - 同一 request_id 不記兩筆；
  - 一筆保留額只 claim 一次、只結一次。

  重算器自己也測過：塞一筆重複結算、一次重複 claim、一筆超出保留額的結算，三種都抓得到。

## 步驟與結果（30 個 check 全綠；4 份並行各跑一次也全綠）

| 步 | 做法 | 結果 |
|---|---|---|
| 1 | 照 §11.2 重播：P 10000，先花 3000、在途 1000（provider hold）；split 2400（S 1600、R 800）；S 用 1200、R 用 700；Q 的工作穿插在中間 | split 後 P 可再分配 3600。還回之後 P 是已花 4900、在途 1000、自由 4100，跟報告一字不差；Q 只有自己的 400 |
| 2 | 兩個 3000 的 reserve 同時搶 P 剩下的 4100 | 一個成功；另一個被拒，理由寫「額度不足：P 剩 1100，要 3000」 |
| 3 | 同一份 grant 交給兩個 worker（同一批 spawn） | 一個做完；另一個被拒，理由寫「重複：res-22 已被 attempt g-a1（p:w-g1-r9）claim」。provider 只執行一次 |
| 4 k1 | reserve 落帳之後、回條之前 kill 帳本，再重送同一個 id | keep 重起後照事件補回條（`replayed`），不記第二筆；worker 約 150 ms 後做完 |
| 4 k2 | provider 執行完、回條之前 kill provider，再重送 | 照 executed 補回條（`recovered`），不再執行；帳只結一次 |
| 4 k3 | settle 回條寫了、worker 還沒讀就被 kill；探針重送 settle，再 spawn 新 worker | 新 worker 讀到同一張回條；settle 只記一筆 |
| 5 | 未知在途（provider 一直不回）：先 release；再 kill worker、kill 帳本，等 worker 資料夾被 tock 搬到 tasks-old/ | release 被拒（「在途未知…不釋放」）。worker 死、帳本重起、資料夾歸檔之後，1000 仍保留。provider 回條後，接手的 worker 才結算（用 900、退 100）；它沒有重新 reserve／claim，也沒有重送 provider 請求 |
| 6 | P 的 grant（res_id＋attempt）洩漏給 Q 的任務，那個任務自稱 `p:w-real-r99` 去 claim | **claim 成功、provider 照做、記給 P**（記成「量」，不是 check）。守恆照樣成立，只是錢被別人花了 |
| 總 | | provider 每次執行都恰好對應一筆 settle（同 res、同 attempt、同用量）；Q 的帳裡只有 Q 的請求；寫入紀錄 0 筆超出範圍 |

報告 §14 實驗二第 3 步的同步 loan，以及第 6 步「撤銷 parent epoch 後重啟子任務」的 capability 模擬都沒做。

## 逼出的 daemon／tick 需求

- **帳本當單一寫入者、keep 重起、spawn 起 worker、tasks-old 歸檔不影響帳：現有基底足夠**。去重、守恆、未知在途這些語意都在帳本與 provider 裡做得到，不必搬進 daemon（同報告 §13 的判斷）。
- **N-77（對應報告 E-01，聲稱硬限制時必要；權限屬核心「之後再說」，要使用者決定）執行者身分是自報的**：
  - 帳本與 provider 收到的請求檔，分不出是誰寫的。claim 裡的 `executor`、請求裡的寄件者都是任務自己填的。
  - 任務只要在 tasks.json／spawn 宣告 mounts，就能掛到同一個收件夾；`mount_allow` 只管執行中加掛，不管宣告。
  - 寫入紀錄只看得到 Python 任務，而且是事後、由任務自己寫的。
  - tick 其實知道誰是誰（birth.json 的 node、tid、mounts），只是沒有交給服務驗的管道。
  - 第 6 步就是證據：洩漏的 grant 被別的 node 用掉，錢記在 P 身上。合作式的世界裡這算 grant 外洩的後果；要宣稱「只有 P 的任務能花 P 的錢」，tick／runner 就得提供服務可以驗的身分。
