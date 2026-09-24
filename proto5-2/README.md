# proto5-2

← [INDEX](../wf/INDEX.md)｜上一版 [proto5](../proto5/README.md)

**狀態：已實作（第 1 版），2026-09-24**。程式在 [lib/](lib/README.md)＋[cli/](cli/)；測試 1277 條全綠（`cd proto5-2/lib && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s test`，約 89 秒）；實作筆記在 [notes/2026-09-24-impl/](notes/README.md)。

## 這是什麼

proto5 之上的一輪改版：**kernel 和 daemon 改成以「池」為單位、宣告式**。起因是使用者 2026-09-24 的方向——
kernel 將來要管上千上萬顆 cpu、很多個池；開一顆 cpu 很便宜（模型另算），所以 `init` 時把 cpu 一顆顆寫死不對，要能隨時加；
daemon 要帶上萬個孩子，指令會變多，但一律按池管。六點定案逐條落在哪，見 [spec/choices.md](spec/choices.md)。

白話講三件事：
1. **kernel 只說「池 P 要 N 顆」**，daemon 自己補到 N、死了自己拉（會越等越久，不會狂拉）、多了自己收。kernel 不記 pid。
2. **加 cpu 就是改一個數字**：`aos-kernel cpu add --pool default --count 100`，下一格生效，不用 boot。
3. **kernel 每格只碰有事的 cpu**：cpu 回完音往 kernel 家丟一張通知，kernel 只看通知、剛派的、輪到巡檢的那幾顆；派工從閒著的號碼裡直接拿。

## 十分鐘上手（2026-09-24 第 1 版）

從 repo 根目錄照抄，一段一段貼進 bash／zsh。需要 Python 3.12 以上；第 4 段起要一個 OpenAI 相容的模型端點，例：LiteLLM 的 `http://localhost:4000/v1`／`deepseek-chat`（換別的就改 `llm.json` 的 `endpoint`、`model`）。工作目錄 `W` 隨你放；重來一次先 `rm -rf $W`。跟 proto5 一樣，三支指令一律用 `--target DIR` 指家，省略時 daemon 找 `AOS_DAEMON_HOME`、kernel 找 `AOS_KERNEL_HOME`，再沒有用目前資料夾；agent 省略就是目前資料夾。下面先把兩個環境變數設好。

**1. PATH 與 daemon。**

```sh
export PATH=$PWD/proto5-2/cli:$PATH
W=/tmp/aos2-try; mkdir -p $W
export AOS_DAEMON_HOME=$W/D AOS_KERNEL_HOME=$W/K
setsid aos-daemon boot 2>>$W/daemon.log </dev/null &
```

daemon 是前景程式，一定要放背景；用 `setsid`（或 `nohup`）才不會跟著終端機被收掉，跟 proto5 一樣。

**2. kernel：池可以先 0 顆 init，之後再用 cpu add 補。** proto5-2 的 `init --config` 只收 kernel 參數＋池表（不像 proto5 逐顆列 cpu）。

```sh
cat > $W/llm.json <<'EOF'
{"_metainfo": {"_type": "llm_config", "_version": 1},
 "models": {"default": {"endpoint": "http://localhost:4000/v1", "model": "deepseek-chat"}}}
EOF
cat > $W/kernel.json <<EOF
{"pools": {"default": {"count": 0}}}
EOF
aos-kernel init --config $W/kernel.json
aos-kernel boot
```

`init` 印 `initialized <K>`；`boot` 印 `booted N pools, M cpus`（這裡只有 kernel 池那顆真的拉起來，`default` 還是 0 顆）。

**3. `cpu add`：把 `default`、`llm` 兩池加上去。**

```sh
aos-kernel cpu add --pool default --count 2
aos-kernel cpu add --pool llm --count 1 --env AOS_LLM_CONFIG=$W/llm.json
```

`cpu add` 只改 `K/info.json` 的池表，不放單、不用 `boot`——kernel 在跑的話下一格就照新數字補；上面兩行印 `pool default count 0 -> 2`、`pool llm count 0 -> 1`。等個一兩格（約 1 秒）再看：

```sh
aos-kernel ls              # health＋按池摘要＋行程數
aos-kernel cpu ls          # 只看池摘要
aos-daemon ls               # daemon 自己看到的活／忙／dead／重拉中，偷看檔案不用放單
```

**4. 最小 agent：生家、登記、說一句、等回話。**（這條線跟 proto5 完全一樣）

```sh
aos-agent init --target $W/bob
aos-kernel check --agent $W/bob
aos-agent start --target $W/bob
aos-agent say "現在幾點？請用工具查。" --target $W/bob --wait
```

`check --agent` 現在按池表查，不再假設有個叫 `llm` 的池；其餘（`llm.model` 是代號 `default`、`say --wait` 等回話）跟 proto5 一樣。

**5. 加減 cpu。**

```sh
aos-kernel cpu add --pool default --count 1         # 3 顆
aos-kernel cpu rm default/2                          # 永久退休 2 號（寫進 skip，之後不會再用它）
aos-kernel cpu rm --pool default --count 1           # 收最大的 1 號
aos-kernel cpu ls --pool default                     # 每顆的狀態
```

兩種 `cpu rm` 都是「手上工作做完才真的收」，沒有 `--now`；被收的號要重新啟用得先 `cpu add` 生新號。

**6. 每天重開機。** 關機、登出或關掉終端後 daemon 跟 cpu 都沒了，家還在：

```sh
export PATH=$PWD/proto5-2/cli:$PATH
W=/tmp/aos2-try; export AOS_DAEMON_HOME=$W/D AOS_KERNEL_HOME=$W/K
setsid aos-daemon boot 2>>$W/daemon.log </dev/null &
aos-kernel ls               # 第一行 health＝ok 就好
```

跟 proto5 最大的差別：`aos-daemon boot` 會照上次的宣告自己把池拉回來，kernel 的鏈多半自己接上，**通常不用再打 `aos-kernel boot`**。只有 `aos-kernel ls` 的 health 不是 `ok`（例如印「tick 停住」）才補一次 `aos-kernel boot`。agent 家要不要 `aos-agent start`，看昨天有沒有做過第 7 段的 `stop`。

**7. 全停。**

```sh
aos-agent stop --target $W/bob
aos-kernel halt
aos-daemon halt
```

`aos-kernel halt` 會把每個池（含 kernel 池）縮到 0，等 daemon 那邊全部消失才印 `stopped`；`aos-daemon halt` 停掉這批空池，`pool.json` 宣告留著，下次 `boot` 不會拉回任何東西（除非又 `cpu add`）。

其餘（`listen`／`status`／`pause`／`continue`、自訂工具、手動不用 `init` 的家）跟 proto5 完全一樣，見 [proto5 README 十分鐘上手](../proto5/README.md#十分鐘上手09-24-試玩-r1-補fix-r4-全文改成新指令)第 4～6 段。

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

九題已由隊長先代為拍板（全部照草稿；Q1～Q3 先不動、Q4～Q9 照草稿定案），細節與翻案要改哪裡見 [notes/2026-09-24-impl/decisions.md](notes/2026-09-24-impl/decisions.md) 開頭「Q1～Q9」那段。每題都可以翻案。

| 題 | 定成什麼 |
|---|---|
| Q1 kernel 帳本整份讀寫 | 先不動，照現況（一份 `K/state.json`），先以幾百到一千顆為準 |
| Q2 aos-agent 每格偷看整份帳本 | 先不動 |
| Q3 一顆 cpu＝一支 Python 行程 | 先不動，先以千顆為目標 |
| Q4 `cpu rm NAME` 的意思 | 照草稿：`NAME`＝`P/<i>`、永久退休那個號（寫進 `skip`） |
| Q5 既有池的 `cpu add --env` | 照草稿：拒絕，改環境請編 info |
| Q6 縮小要不要有 `--now` | 照草稿：沒有，一律等手上工作做完 |
| Q7 拉不起來的號卡住的工作 | 照草稿：不訂放棄協定，只能修好家 |
| Q8 daemon `halt` 後 `boot` 自動拉回池 | 照草稿：要 |
| Q9 退休 cpu 家要不要清理指令 | 照草稿：不做，家不刪 |
