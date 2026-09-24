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
| cpu 範式與 exec cpu（**只多一個 `notify` 欄位**，見 [spec/cpu-notify.md](spec/cpu-notify.md)） | [proto5/spec/cpu.md](../proto5/spec/cpu/README.md) |
| agent 資料夾 | [proto5/spec/agent.md](../proto5/spec/agent/README.md) |
| `aos-agent` | [proto5/spec/aos-agent.md](../proto5/spec/aos-agent/README.md) |
| 問模型（`aos-llm call`） | [proto5/spec/aos-llm-call.md](../proto5/spec/aos-llm/README.md) |
| `aos-exec`、inst、指示詞 | [aos-exec.md](../proto5/spec/aos-exec/README.md)、[inst-posix.md](../proto5/spec/inst-posix/README.md)、[directives.md](../proto5/spec/directives/README.md) |
| kernel 的 syscall、回音判定、鏈 | [proto5/spec/kernel.md](../proto5/spec/kernel/README.md) §2、§4、§7 |
| daemon 怎麼拉一個孩子（`go` 握手、process group） | [proto5/spec/daemon.md](../proto5/spec/daemon/README.md) §2 |

**「不變」那幾份裡仍有幾句要跟著換**（審查 R16；proto5 那邊的字不動，逐句記在 [spec/proto5-diffs.md](spec/proto5-diffs.md)）。

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

- [notes/2026-09-24-spec-review-astra-task.md](notes/2026-09-24-spec-review-astra-task.md)／[report](notes/2026-09-24-spec-review-astra-report.md)：astra 唯讀審一輪，挑出 28 條（R1～R28），全部已改進規範（改法標在各檔「審查 Rn」處）；三題轉成下面的要使用者拍的。

## 要使用者拍的

1. **kernel 帳本仍是整份讀寫，要不要接受？** 這一版做到「不逐顆查檔、不逐顆找閒的」，但每格仍要讀、寫一份跟 cpu 數成比例的 `K/state.json`（上萬顆約數 MB）。
   要做到 (f) 的全部，得把帳本拆開——而 aos-agent 現在直接偷看 `K/state.json` 的 `procs`，拆了就要一起改 aos-agent（[spec/scale.md §2](spec/scale.md)）。
2. **aos-agent 每格偷看整份帳本**：上萬個 agent 時是全系統最大的負擔（[spec/scale.md §3](spec/scale.md) 第 4 點）。要不要讓 kernel 另外維護「一行程一個小檔」，agent 改看它？（要改 aos-agent.md）
3. **一顆 cpu＝一支 Python 行程**：1 萬顆約 100～200 GB 記憶體，而且每顆每 0.2 秒掃一次資料夾。「開一顆 cpu 很便宜」以現在的 `aos-cpu` 不成立。要不要改（一支行程管多個家、換語言），還是先以千顆為目標？
4. **`cpu rm NAME` 的意思**：草稿定成 `NAME`＝`P/<i>`、**永久退休那個號**（寫進 `skip`，之後擴池也不再用它）。如果你的意思只是「這次收掉哪一顆」，要改。
5. **既有池的 `cpu add --env`**：草稿直接拒絕（改環境請編 info）。要不要允許「改池環境、之後拉的 cpu 繼承」？活著的要不要一起重拉？
6. **縮小要不要有 `--now`**：現在一律等被收的那顆把手上的工作做完；沒設 timeout 的工作可能等很久（[spec/kernel-pools.md §3](spec/kernel-pools.md)）。
7. **拉不起來的號卡住的工作**：家壞了、cpu 永遠起不來時，派給它的那件只能靠把家修好來解開。要不要訂一個「確認沒人會跑這張單就放棄它」的協定？
8. **daemon `halt` 後再 `boot` 要不要自動把池拉回來**：草稿選「要」（宣告留在 `pool.json`），所以 daemon 重開後通常不用 `aos-kernel boot`；代價是想「乾淨重來」得先讓 kernel 把池縮到 0。
9. **退休的 cpu 家要不要有清理指令**：家從不刪，磁碟上的家數＝池曾經到過的最大號（[spec/kernel-home.md §4](spec/kernel-home.md)）。
