# proto5-2

← [INDEX](../wf/INDEX.md)｜上一版 [proto5](../proto5/README.md)

**狀態：規範草稿，未實作**（第 1 版，2026-09-24）。沒有程式、沒有測試；要不要照這份做、先做哪段，等使用者拍。

## 這是什麼

proto5 之上的一輪改版：**kernel 和 daemon 改成以「池」為單位、宣告式**。起因是使用者 2026-09-24 的方向——
kernel 將來要管上千上萬顆 cpu、很多個池；開一顆 cpu 很便宜（模型另算），所以 `init` 時把 cpu 一顆顆寫死不對，要能隨時加；
daemon 要帶上萬個孩子，指令會變多，但一律按池管。六點定案逐條落在哪，見 [spec/choices.md](spec/choices.md)。

白話講三件事：
1. **kernel 只說「池 P 要 N 顆」**，daemon 自己補到 N、死了自己拉（會越等越久，不會狂拉）、多了自己收。kernel 不記 pid。
2. **加 cpu 就是改一個數字**：`aos-kernel cpu add --pool default --count 100`，下一格生效，不用 boot。
3. **kernel 每格只碰有事的 cpu**：cpu 回完音往 kernel 家丟一張通知，kernel 只看通知、剛派的、輪到巡檢的那幾顆；派工從閒著的號碼裡直接拿。

## 跟 proto5 的關係

規範在 [spec/](spec/README.md)，一個主題一檔、每檔 ≤ 8 KB；**只寫跟 proto5 不一樣的**，每檔開頭寫明取代 proto5 哪一節。
其他照 proto5 現行規範，直接連過去、不複製：

| 不變 | 連到 |
|---|---|
| cpu 範式與 exec cpu（**只多一個 `notify` 欄位**，見 [spec/cpu-notify.md](spec/cpu-notify.md)） | [proto5/spec/cpu.md](../proto5/spec/cpu.md) |
| agent 資料夾 | [proto5/spec/agent.md](../proto5/spec/agent.md) |
| `aos-agent` | [proto5/spec/aos-agent.md](../proto5/spec/aos-agent.md) |
| 問模型（`aos-llm call`） | [proto5/spec/aos-llm-call.md](../proto5/spec/aos-llm-call.md) |
| `aos-exec`、inst、指示詞 | [aos-exec.md](../proto5/spec/aos-exec.md)、[inst-posix.md](../proto5/spec/inst-posix.md)、[directives.md](../proto5/spec/directives.md) |
| kernel 的 syscall、回音判定、鏈 | [proto5/spec/kernel.md](../proto5/spec/kernel.md) §2、§4、§7 |
| daemon 怎麼拉一個孩子（`go` 握手、process group） | [proto5/spec/daemon.md](../proto5/spec/daemon.md) §2 |

fix-r4 正在落地的慣例這裡直接沿用：三支指令的家一律 `--target`（省略找 `AOS_DAEMON_HOME`／`AOS_KERNEL_HOME` 再 `./`）；
daemon 是 `boot／halt`，kernel 停機是 `halt`；agent 的 `say --wait`、`listen`、`pause／continue`；`aos-llm call`。

## 新舊指令對照

| proto5 | proto5-2 | 差在哪 |
|---|---|---|
| `aos-daemon --home D` | `aos-daemon boot --target D` | 重開時照上次的宣告把池拉回來 |
| `aos-daemon stop --home D` | `aos-daemon halt --target D` | 批次停；宣告留著 |
| （偷看 `D/state.json`） | `aos-daemon ls [--pool P]` | 每池一行：活／忙／dead／重拉中；`--pool` 才一顆一行 |
| （沒有） | `aos-daemon scale --pool P --count N` | 手動池用；kernel 的池要 `--force` |
| （放 `kill` 單） | `aos-daemon kill --pool P NAME…｜--all` | 砍掉重來（宣告不變） |
| `aos-kernel init K --cpu 0 --cpu llm:llm --env llm:K=V` | `aos-kernel init --target K --config k.json` | config 只有 kernel 參數＋池；cpu 可空 |
| （改 info 的 `cpus`、boot） | `aos-kernel cpu add --pool P [--count N] [--env K=V]` | 改池的數字，下一格生效 |
| （同上） | `aos-kernel cpu rm P/<i>`／`cpu rm --pool P --count N` | 先做完手上那件才收 |
| （沒有） | `aos-kernel cpu ls [--pool P]` | 每池：要幾顆、確認幾顆、忙／閒／收掉中、daemon 摘要 |
| `aos-kernel boot K --daemon D` | `aos-kernel boot --target K` | daemon 從池表拿；交接改成 kernel 池縮到 0 再拉 1 |
| `aos-kernel stop K` | `aos-kernel halt --target K` | 停機時每池縮到 0，不再往每顆放 stop 檔 |
| `aos-kernel ls K` | `aos-kernel ls --target K [--pool P] [--procs]` | 按池摘要；行程預設只印各狀態數量 |
| `aos-kernel add／rm／ack／check K …` | 同，K 改 `--target` | `check` 改看池表 |

「每天重開機」會變短：`aos-daemon boot` 會把池拉回來，kernel 的鏈多半自己接上；`aos-kernel ls` 的 health 不是 ok 再 `aos-kernel boot`（[spec/handoff.md §2](spec/handoff.md)）。

## 筆記

- [notes/](notes/)：審查任務書與回報。

## 要使用者拍的

（審查後補齊，見下一節之後的更新。）
