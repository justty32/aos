# multid：一個 kernel 管好幾個 daemon（路二）

**是什麼**：daemon A 的 node `k` 跑一個 kernel 任務（`kern.py`），它要看、要控制另外兩個不同空間根的 daemon：

- B：根放在 A 的根底下（`sub_b/`，先建 `.aosd/`，A 掃描會跳過）。
- C：根在 A 外面（`sp.new_root("c")`），A 裡還放了一個指向 C 的符號連結 `link_c`。

kernel 每 50 ms 讀各 daemon 的 status.json，用三種訊號判斷死活：`at` 停更超過 0.5 秒、pid 不在、`daemon.lock` 鎖得到。看到死了就寫自己 node 的 `.aos/spawn/` 請 A 的 tick 把它起回來。probe 透過 `kern/cmd/*.json` 叫 kernel 寫控制檔，kernel 再記下拿到回條花了多久。

**想逼出的**：路二跨 daemon 時，哪些事碰得到、哪些碰不到；ctl 回條；daemon 死掉和重開時怎麼辦；kernel 能不能「起」一個 daemon。

**結果**（跑 3 次都綠，約 3 秒）：

| 量 | 數字 |
|---|---|
| 經掛載寫 B 的 ctl，到拿到回條 | 0.05 秒 |
| 用絕對路徑硬寫 C 的 ctl，到拿到回條 | 0.05 秒 |
| 寫 C（空間外）時，寫入紀錄留了幾筆 | 0 |
| kill -9 之後多久看出來：pid 不在／鎖得到 | 0.01～0.05 秒 |
| kill -9 之後多久看出來：`at` 停更 | 0.51～0.53 秒（門檻設 0.5） |
| SIGSTOP B（卡住、沒死） | `stale: true, pid_dead: false, lock_free: false` |
| kill -9 到 B、C 被 kernel 起回來 | 0.58～0.81 秒 |
| B 死的時候寫的 ctl，拿到回條 | 0.56～0.70 秒（B 重開後才執行） |

**發現**

- **掛載**：巢狀的 B 掛 `sub_b/.aosd` 可以。C 在外面，寫 `../c/.aosd` 會被拒，走 `link_c/.aosd` 也會被拒（realpath 跑出根），執行中請求加掛同樣被拒。結果只能把絕對路徑寫進 kernel 設定直接寫，**寫入紀錄完全看不到**（audit 只記空間根底下）。
- **node id**：沒有跨 daemon 的 id，kernel 只能自己記成 `b:x`。同一個資料夾在 A 空間裡叫 `sub_b/x`。對 A 寫 `pause sub_b/x` 會拿到 `ok: true`，但 B 的 x 照跑（0.5 秒多跑 2～5 回合）。控制送錯了地方，回條卻說成功。
- **死活**：status.json 不會說自己死了。kill -9 之後檔案還寫著舊 pid、`stopping: false`。只看 `at` 會把「卡住」誤判成「死掉」，要配 pid（不屬於檔案介面）或 flock（只在懷疑時才試，否則會跟正要起來的 daemon 搶鎖，搶輸的 daemon 直接退出碼 1）。
- **重開**：路二只能寫控制檔，沒有「起 daemon」這個 op。kernel 只能寫自己 node 的 spawn，讓 A 的 tick 去起，這其實就是路一。起回來的 B 變成 A 的任務，`status.root` 從 `.../sub_b` 變成 `.../k/.aos/tasks/bd-rN/mnt/broot`，用 root 認 daemon 的人會以為換了一個。
- B 死的時候寫的 ctl 留在 `ctl/` 裡，B 重開後才執行，回條上沒有寫延遲多久。B 的 keep 任務 `s` 在 B 死掉期間是孤兒（P-04），重開的 B 照 pid.json 把它當活任務接回來，沒有重起。crash 那一回合沒有 tock，回合總結有時會跳號（P-08）。
