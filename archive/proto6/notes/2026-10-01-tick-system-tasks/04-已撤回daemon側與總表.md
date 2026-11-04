← [2026-10-01：aos-tick 的系統級任務總整理（給 hooks 慢慢想用）](../2026-10-01-tick-system-tasks.md)（分檔 4/4）｜[上一份](03-普通程式工具與構想.md)

## 九、已撤回或改名、不會照原樣回來的

| 舊東西 | 變成什麼 | 出處 |
|---|---|---|
| `aos-needs`（包裝、回 125） | `aos-tick-check-task` | [暫緩區篇末](../../spec/deferred/tick/04-已撤回與被取代.md#已撤回被取代) |
| 收件 aos-inbox → aos-intake → `aos-sysinbox`；投件 aos-outbox | `aos-mq get`／`post` | verdicts 11「astra 審整理區」 |
| 檔案收件、檔案投件（`requests/`、`responses/`） | 普通程式，aos 不管 | [B-623、B-624](../../spec/deferred/mq.md) |
| 鬧鐘 `alarm_ticks`、`.aos/alarms/` | 撤，任務自己記 | B-624 |
| `.aos/journal/`、`aos-tick adopt` | 結束碼紀錄取代 | [B-632](../../spec/deferred/git.md) |
| tick 側 cgroup 備援 | 撤，改 `aos-cg` | [B-631](../../spec/deferred/cg.md) |
| 第十九批「標準配備」（同一支 aos-tick、必須全掛） | 標準任務表範本 | verdicts 11 追答 8、9 |

## 十、daemon 那側、本來就不在任務表上的

這些原本跟範本一起講，但歸 daemon，全在暫緩區：格後收屍與 runner（B-601）、重啟清框（B-603）、排空停機（B-604）、once 掛行程 `node.mount`（B-613，任務自己呼叫）、helper 固定動作（B-609）。擋板檔的「之後各格不開」現在由 `aos-tick` 自己看（B-620）。這些大概都不是 tick hooks 的事，列著備查。

proto5 沒有同名的東西：它的 daemon 直接開 `aos-kernel tick`（`lib/aos_daemon_ticks.py`），沒有任務表與系統級任務。

## 總表

| 名字 | 狀態 | 可能的掛點（待使用者想） | 備註 |
|---|---|---|---|
| 標準任務表範本 B-629 | 待實作 | `tasks`＋`after_all` 兩半 | 保證多半靠停格擋後面 |
| `aos-git open` | 待實作 | `tasks` 首項／`before_all` | git 先不動 |
| `aos-git mark`（mark-get、mark-user） | 待實作 | `tasks` 中間／`after_task` | index 會跟 hook 撞號 |
| `aos-git close` | 待實作 | `tasks` 倒數／`after_all` | 進 `after_all` 會改「停格＝作廢」 |
| `aos-mq get` | 待實作、依賴暫緩 | `tasks` 首項／`before_all` | 要通道 |
| `aos-mq post` | 待實作、依賴暫緩 | `tasks` 尾／`after_all` | `after_all` 要自己判停格 |
| `aos-clean` | 待實作（plan 建議先不做） | `after_all`／`tasks` | 有 git 時要排 close 前 |
| `aos-tick-check-task` | 待實作（已裁定） | 留 `tasks`；將來 `before_task` | `after_all` 無意義 |
| `aos-cg` | 暫緩（第二十三批） | 不用了，daemon 收屍模組（B-644）做 | 無 cgroup 時 hook 收不到孤兒 |
| `aos-as` | 暫緩 | 留包裝 | 要 helper |
| 恢復前驗證（aos-check） | 待實作（plan 建議先不做） | 不需要 | 格外工具 |
| `aos-config-add` | 暫緩 | 不需要 | 格外工具 |
| `aos-publish` | 暫緩 | `after_all` | 要改名 |
| `aos-summarize` | 構想，不做 | `after_all`／可能不需要 | 紀錄已像摘要 |
| `aos-tick-check-task-continue` | 未來方向 | `before_task` 或改核心 | 停格先不動 |
| `aos-ctl wake <上層>` | 第七批建議 | `after_all` | node 還在想 |
| 收屍（runner） | 暫緩（daemon） | 不明 | 要 cgroup 才收得到 |
| 逾時 | 不做模組 | 不需要 | 用系統 `timeout` |
| 歷史紀錄 | 不做 | — | 第七批 |
