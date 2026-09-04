# daemon-clocks：daemon 是所有時鐘的總管

← [ideas](README.md)｜前篇 [exec-run-async-time](exec-run-async-time.md)｜[play-watchlist](play-watchlist.md)｜[fuse-host](fuse-host.md)｜[top-to-bottom/01](top-to-bottom/01-top.md)

本篇是 [exec-run-async-time](exec-run-async-time.md) 的續篇。前篇把 async 說成子世界有自己的
時鐘；本篇接著記「誰讓這些時鐘走、怎麼一次停掉」。

**本檔無明說裁決。** 使用者說的是「會想」與「希望」，以下標為
**使用者傾向（未明說裁決）**；AI 觀察也都可以否決。

## 使用者原話（2026-09-04）

> 你說的兩個時鐘的問題，關於誰讓子時鐘走，我其實會想讓daemon處理，但在特定的稀少情況下保留fork。然後父時鐘掛了子時鐘還可以繼續走，只是說，我會希望所有時鐘都被登記於某處，由daemon管理，這樣當我想關機、停下所有時鐘的時候，可以一次性全都停掉

> 先不考慮fork吧。

## 使用者傾向（未明說裁決）

本檔先一律以「**所有時鐘都由 daemon 走**」為前提。父時鐘掛了，子時鐘仍可繼續；所有時鐘
都要登記，關機時才能一次全停。fork 這條，**使用者說先不考慮**，本檔不展開。

## AI 觀察（非裁決，可否決）

### 1. daemon ＝時鐘總管

它做三件事：**登記所有時鐘、幫時鐘走、關機時一次全停**。這與
[fuse-host](fuse-host.md) 的「daemon＝桌子本身」、[top-to-bottom/01](top-to-bottom/01-top.md)
的「頂層由使用者開，或由 daemon 代開」一致，只是把 daemon 的工作講得更具體。

### 2. 登記處就是 daemon 自己的資料夾

既然 daemon 也可看成一個資料夾，登記表就不必發明新機制：**daemon 資料夾本身就是一個
list，每個元素指向一個正在走時鐘的資料夾。** 仍然是「資料夾＝list」。

### 3. 這跟 Unix 長成同一個形狀

父死了、子繼續，再由 daemon 接手，像 Unix 把孤兒行程過繼給 PID 1；關機一次全停，像
systemd 用 cgroup 把一整組行程收掉。模型自然走到與 Unix 相同的地方，是沒有走歪的訊號。

### 4. 登記是出生的一部分

任何時鐘出生時，都要**先在 daemon 資料夾寫一筆，再開始走**；順序反過來會留下沒被總管
看見的時鐘，關機就會漏掉。fork 使用者說先不考慮，這裡不展開。

### 5. 今天已有一半，缺的是總表

今天每個資料夾各有一份 `.aos/run.pid`，算是**分散的登記**；`aos stop <folder>` 也已能靠它
停掉那個資料夾的無限 loop。缺的是列出所有時鐘的**總表**，以及「走過總表、一次全停」的
動作。daemon 重啟後，可以拿總表逐筆對照各資料夾的 `run.pid`，把已死的登記清掉。

### 6. 留給玩的兩題

1. **一筆登記長什麼樣**：至少可能有資料夾路徑、pid、時鐘規格（間隔／步數／條件）。
2. **daemon 自己掛了怎麼辦**：時鐘照走；daemon 重啟後再拿總表與各 `run.pid` 對帳。

昨天留過一題：「gaps 表要不要加 daemon 專屬一格？」現在 daemon 的角色已經具體到「時鐘
總管」，AI 認為可以加；**是否新增仍由使用者決定**。

## 現有 aos 對照

| 模型名稱 | 程式裡的名字 | 合不合 |
|---|---|---|
| daemon 管的資料夾清單 | `core/tick/src/tick_cli.cpp` 的 `dispatch()` 只取一個 folder；`core/tick/src/cli_common.cpp` 的 `load_context()` 只建立該 folder 的 layout | **沒有總清單**：一次只管命令指定或目前所在的一個資料夾 |
| 一個資料夾的定期與一次性事務 | `core/tick/src/paths.cpp` 的 `paths_of()` 指到該資料夾的 `.aos/heartbeat/routines.json`、`schedule.json`；`core/tick/src/tick.cpp` 的 `run_tick()` 讀兩表並 `loop::deliver()` | **已有，只有單一資料夾內** |
| 替一個資料夾裝心跳 | `core/tick/src/init.cpp` 的 `heartbeat_init()` 寫 `.aos/every/tick.json`，內容會呼叫 `aos tick` | **已有，仍靠該資料夾自己的 loop 推進** |
| 登記正在走的時鐘 | `core/loop/src/run.cpp` 的 `aos_run_cli_main()` 在所有 `--step 0`（含 `--daemon`）用 `RunPidFile::write()` 寫 `.aos/run.pid`，析構時刪除 | **已有分散登記，沒有跨資料夾總表** |
| 停一個時鐘 | `core/loop/src/stop_cli.cpp` 的 `aos_stop_cli_main()` 讀指定資料夾的 `run.pid`，先送 `SIGTERM`，最多等 5 秒，再送 `SIGKILL`，並刪 pid 檔 | **已有單個停止，沒有一次全停** |

## 相關清單

- `G06`（行程抽象）：出生時登記，總表讓時鐘可列舉、可終止。
- `G07`（程式／行程分界）：登記的是正在走的時鐘，不是靜態資料夾模板。
- `G09`（搶佔／自願返回）：一次全停需要明確的停止邊界與強制收尾。
- `G10`（排程器住在哪一層）：daemon 走總表，是跨資料夾排程的一個具體形狀。
- `G19`（資源不可靠與不確定）：daemon 掛掉、PID 過期，都要靠重啟對帳收斂。
- [play-watchlist](play-watchlist.md)——誰走子時鐘與資料夾壽命。
- [fuse-host](fuse-host.md)——daemon＝桌子本身；本篇再把桌上的時鐘登記成 list。
