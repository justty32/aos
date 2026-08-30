# home daemon spec：`aos daemon` 一個行程管多個世界的 loop

← [home-world](home-world.md)（場景與裁決）｜[nested-worlds](nested-worlds.md)｜隊 Y [proto-Y-improve](../dispatch/proto/proto-Y-improve.md)｜[PROTOCOL](../dispatch/proto/PROTOCOL.md)

2026-08-30，Fable 規劃者。**純規劃。** 前提：LLM PU 世界不做、systemd 不做、初期手動 `aos daemon start`。
事實（讀碼確認）：`aos run` 沒有鎖（`core/loop/README` 已知不管）；`AOS_HOME`＝`$AOS_HOME` 否則 `~/.aos`（`core/llm/src/slot.cpp:227`），
裡面已有 `cpus.json`、`slots/`、`say/`、`log.md`；隊 Y 要做的是單世界 `aos run --daemon`＋`.aos/` pid 檔＋`aos stop`＋投遞即喚醒。

## 1. `~/.aos/daemon.json`

```json
{"interval_ms": 100,
 "targets": [
  {"path": "~/agents/botA", "mode": "sync", "enabled": true},
  {"path": "~/pus/lm-local", "mode": "own", "interval_ms": 500, "enabled": true}]}
```

| 欄位 | 意義 |
|---|---|
| `interval_ms` | 主世界 `~` 的回合間隔；`~` **不列在 targets**，永遠是第一個、`own` 模式 |
| `path` | 世界資料夾；`~` 展開、相對路徑相對 `$HOME`；沒有 `.aos/` 就由 `aos run` 建 |
| `mode` | `sync`＝跟主世界同 tick（見 §3）；`own`＝自己一條 loop、自己的 `interval_ms`（缺＝沿用頂層） |
| `enabled` | `false`＝留在清單、不起 loop；status 仍列出 |

登記：`aos daemon add <folder> [--own 500ms | --sync] [--disabled]`（同 path 再 add＝更新欄位，原子寫 `.tmp`＋rename）、
`aos daemon rm <folder>`、`aos daemon ls`。時間字面只收 `<N>ms`／`<N>s`（tick 的 `parse_duration` 沒有 ms 單位，不共用）。

## 2. `aos daemon start / stop / status`

**一個行程怎麼管多個 loop**：
thread——一顆行程、一個 thread 一個 `run_turn` 迴圈；代價：任一世界的例外或 abort 帶走全部，且 `find_folder`／cwd 類輔助在多 thread 下不可用。
子行程——daemon 是 supervisor，每個 `own` 目標 `fork+exec` 一條 `aos run <path> --step 0 --interval N`；代價：N+1 個行程、要 `waitpid` 與重啟。
**建議子行程**：隔離是真的，且直接重用隊 Y 的 `aos run`，daemon 本身不含回合邏輯。

**互不拖累的定義**：目標 A 一回合的長短只影響 A 自己的下一回合開始時間；B 在同一段牆鐘裡完成的回合數 ≈ 時間 ÷ `interval_B`，
與 A 無關。驗收：A 放一條 `sleep 30`，B `interval 100`，30 秒內 B 的 `turn` 前進 ≥ 200。`sync` 目標依定義例外（它就是主世界回合的一部分）。

**pid／鎖**：daemon 在 `~/.aos/daemon/lock` 上 `flock`（真相，行程死了自動放）、`~/.aos/daemon/pid` 給人看；
每條子 loop 的 pid 沿用隊 Y 的 `<world>/.aos/` pid 檔，所以 `aos stop <folder>` 對 daemon 起的 loop 一樣有效。

**重複 start**：拿不到 flock → 印 `already running (pid N)`＋一行 status，exit 1；不殺、不接管。
目標世界已有別人起的 `aos run`（pid 檔被鎖住）→ 不起第二條，status 標 `external`，不搶。

**子 loop 死了**：以 1,2,4…60 s 退避重啟，不放棄；status 記 `restarts`、`last_exit`。
**stop**：`aos daemon stop`＝對 pid 發 SIGTERM；daemon 收到後對每個子 loop 發 SIGTERM（＝各自 `aos stop`），等 ≤ 5 s 後 SIGKILL，放 flock。
**改清單**：daemon 每 1 s 重讀 `daemon.json`，多出來的起、拿掉或 `enabled:false` 的停；`add`／`rm` 不用重啟。

**status 印什麼**（只讀檔、不 IPC）：第一行 daemon pid／uptime／設定檔；之後每目標一行——

```text
~                 own   100ms  pid 4123  turn 812  running  unread 0  ok
~/agents/botA     sync  -      (in ~)    turn 812  idle     unread 2  ok
~/pus/lm-local    own   500ms  pid 4130  turn 160  idle     unread 0  last_error: waiting-llm  restarts 1
```

來源：`<world>/.aos/state.json` 的 `turn`／`phase`／`agents.*.unread`／`agents.*.last_error`（後兩欄是隊 Y 新增）；
`sync` 目標的 turn 讀它自己的 `state.json`（被推一步就 +1）。活著＝pid 檔的 flock 還被持有；`state.json` 超過 10×interval 沒更新標 `stale`。

## 3. `sync` 跟 `every/` 推子世界

是**同一件事的兩種寫法**：`sync` 的實作就是主世界 `~/.aos/every/daemon-<stem>.json` 一條 `aos run <path> --step 1`。
`aos daemon add --sync` 寫這條 every 檔＋在 `daemon.json` 記一列（為了 `ls`／`status`／`rm` 能對帳）；`rm` 兩邊都刪。
**建議留 `every/` 當機制、`daemon add` 當登記入口**；手寫 `every/` 的仍然能跑，只是 status 看不到。
代價：`sync` 子世界慢會拖住主世界那回合——這正是 `sync` 的定義；不想被拖就改 `own`。

## 4. 跟隊 Y `aos run --daemon` 的相容路徑

Y 的產物＝**N=1 特例**：`cd ~ && aos run --daemon` ≡ `daemon.json` 沒有任何 target 的 `aos daemon start`。
為了能長出來，請 Y 把兩件事放對位置：① pid 檔的寫入與 `aos stop` 的辨識住在 `aos run` 的迴圈裡，**不只在 `--daemon` 分支**
（daemon 起的子 loop 是前景子行程，不用 `--daemon` 卻要能被 `aos stop`）；② `--daemon` 只多做「脫離終端＋stdout 導到 `<world>/.aos/run.log`」。
CLI 收斂：`aos run --daemon`／`aos stop [folder]` 留作單世界用；`aos daemon start|stop|status|add|rm|ls` 管清單。不合併、不改名。

## 5. 手動啟用的日常

開機後：`aos daemon start`（背景化，印每目標一行）。確認活著：`aos daemon status`，或在任一世界 `aos state`。
停：`aos daemon stop`；只停一個世界：`aos stop ~/pus/lm-local`（daemon 會重啟它——要真的停就 `aos daemon rm` 或 `enabled:false`）。
記錄：daemon 自己的事件（起、停、重啟）寫 `~/.aos/daemon/log.md`；各世界的回合輸出在各自 `.aos/run.log`。
**之後怎麼包 systemd**（不展開）：加 `aos daemon start --foreground`（不 fork、不自己寫 pid），user unit `~/.config/systemd/user/aos.service`
`Type=simple`／`ExecStart=aos daemon start --foreground`／`ExecStop=aos daemon stop`，配 `loginctl enable-linger`。

## 6. 要使用者拍板的清單

| # | 問題 | 選項 | 建議 | 代價 |
|---|---|---|---|---|
| 1 | 多 loop 用什麼 | ① thread ② 子行程 supervisor | **②** | N+1 個行程；要寫 waitpid＋退避重啟（約 150 行） |
| 2 | `sync` 怎麼做 | ① 就是 `every/` 一條 `aos run --step 1` ② daemon 同拍觸發但不阻塞主世界 | **①** | sync 子世界慢會拖主世界；② 才是「同拍不拖」但要新機制 |
| 3 | `aos daemon add` 的預設模式 | ① `own` ② `sync` | **①**（互不拖累是這個 daemon 的存在理由） | 「一同 tick」要多打 `--sync` |
| 4 | `~` 在清單裡怎麼表達 | ① 隱含第一個、頂層 `interval_ms` ② 也是 targets 一列 | **①** | 想不跑 `~` 只跑子世界做不到 |
| 5 | 重複 start | ① exit 1 印 status ② 接管既有 loop ③ 殺掉重來 | **①** | 想重啟要兩句（stop、start） |
| 6 | 子 loop 死了 | ① 退避重啟到 60 s 不放棄 ② 十次後放棄標 `dead` | **①** | 壞掉的世界會一直重啟，只在 status 看得到 |
| 7 | 改清單要不要重啟 | ① daemon 每秒重讀 ② `add` 印「請 restart」 | **①** | 多一段 diff 邏輯；`rm` 立刻殺 loop，沒有確認 |
| 8 | 跟 Y 的邊界 | ① Y 只做單世界，pid 寫在 run 迴圈（§4 ①②）② Y 順手做 daemon.json | **①** | 之後 daemon 隊要等 Y 落地才能開 |
