← [daemon／kernel 調查報告（astra）](../2026-09-22-daemon-kernel-report-astra.md)（分檔 3/6）｜[上一份](02-aos-daemon.md)｜[下一份](04-aos-kernel-崩潰到llm介面.md)

**3. aos-kernel**

**3.1 程式入口與命令列**

沒有 `aos-kernel status`、`aos-kernel module`、`aos-kernel syscall` 或 `aos-kernel schedule` 這些通用子命令；相關 Python 檔是內部實作。狀態命令是 `ls`，module 直接使用它的 `NAME` 當子命令。

| 命令 | 參數／旗標 | 成功 | 已處理失敗／用法錯 |
|---|---|---:|---|
| `aos-kernel-init DIR` | 必填 `--ncpu N`；其餘見 config 表；`--module PATH` 可重複 | 0 | DIR 已存在 1；解析／範圍錯 2 |
| `aos-kernel-boot K` | `--home H` 或 `--home=H` | 0 | 非家／缺 inst／daemon 不活／add 失敗 1；參數數量錯 2 |
| `aos-kernel-tick` | 不收任何參數；cwd=K | 0 | 非家 1；有參數 2 |
| `aos-kernel add [K] INST` | `--name NAME` | 0 | 家／檔案／inst／名稱／寫入錯 1；參數形狀錯 2 |
| `aos-kernel rm [K] NAME` | 無旗標，固定等回音 | 0 | 找不到／回音失敗／超時 1；參數或 NAME 錯 2 |
| `aos-kernel ls [K]` | 無旗標 | 0 | 非家／chdir 失敗 1；超過一個參數 2 |
| `aos-kernel <NAME> ...` | module CLI 自訂 | module 回碼 | hook 例外 1；找不到子命令通常 2 |
| `aos-kernel init/tick` | 舊子命令 | — | 2，提示使用獨立執行檔 |
| `aos-kernel -h/--help/help` | 頂層 help | 0 | — |
| `aos-kernel` 無參數 | — | — | 2 |

補充：

- init、add 把 argparse 的所有 `SystemExit` 都轉成 2，因此它們的 `--help` **印完 help 也回 2**。
- tick 的 `--help` 是「有參數」，回 2。
- boot 沒有專門 help 分支。
- 未知 module 命令若連 K 都不是有效家，先回 1，而不是最後的未知命令 2。
- tick/init 等仍有未捕捉的 filesystem／資料形狀例外；不能把表中的正常處理分支理解成完整防炸保證。

來源：[aos_kernel.py:151](../../../../proto4-3/aos_kernel.py)、[aos_kernel.py:198](../../../../proto4-3/aos_kernel.py)、[aos_kernel_init.py:24](../../../../proto4-3/aos_kernel_init.py)、[aos_kernel_tick.py:140](../../../../proto4-3/aos_kernel_tick.py)。

**3.2 家目錄逐檔**

| 路徑 | 格式／初值 | 誰寫／誰讀 | rename／刪除 |
|---|---|---|---|
| `K/` | `abspath(DIR)` | init 建；全部 kernel 工具用 | init 要求整個路徑不存在，不覆寫現有家 |
| `K/inst.json` | `{"argv":["<絕對路徑>/aos-kernel-tick"],"cwd":"."}` | init 寫；boot 查；daemon 的 aos-run 執行 | `.tmp`→replace；kernel 不定期改寫 |
| `K/config.json` | 後表八個欄位 | init 寫；各 kernel CLI、tick 讀 | `.tmp`→replace；後續修改只能由外部進行 |
| `K/state.json` | `cpus`、`queue`、`waiting` | init／tick 寫；tick/add/ls/rm 讀 | `.tmp`→replace |
| `K/kernel.log` | 純文字 append | init／tick 寫；ls、人讀 | 不輪替、不自動刪 |
| `K/procs/` | 就緒指令檔目錄 | init 建；add、scheduler 寫；tick 掃 | 不自動刪目錄 |
| `K/procs/<pid>.json` | inst JSON；未知欄位保留 | add 複製正規化後內容；scheduler 換下時 hard-link | 上 CPU 時 replace；壞檔 replace 到 bad；rm unlink |
| `K/procs/.<pid>.json.tmp` | add 暫存 inst | add 寫、驗 | 驗過才 replace；失敗嘗試刪 |
| `K/procs/bad/<pid>.json` | 退件原檔；**可能不是合法 JSON** | tick 退件 | 明確同名 add、rm，或同名 park 覆蓋時清除 |
| `K/procs/done/<pid>.json` | 完成行程的 inst 原內容 | scheduler hard-link 保存 | 同名 add／rm／再次 park 可清除 |
| `K/cpus/` | CPU 指令目錄 | init 建 | init 時裡面尚無 CPU 指令檔 |
| `K/cpus/<n>.json` | idle inst 或當前行程 inst | tick、scheduler、rm 改 | 原子 replace；swap 前先為旧行程建立 hard-link |
| `K/cpus/<n>.json.tmp` | 要換上的 idle inst | poll／park／rm 寫 | replace 到 CPU 檔 |
| `K/syscalls/` | syscall 收件匣 | init 建；CLI／外部投單；tick 讀 | 每張處理後嘗試 unlink |
| `K/syscalls/<ticket>.json` | syscall 物件 | rm CLI／module CLI／外部 | 各 writer 先暫存再 replace |
| `K/syscalls/done/` | 回音目錄 | init／tick 建 | 不自動刪資料夾 |
| `K/syscalls/done/<ticket>.json` | `{"ok":boolean,"msg":string}` | tick 寫；對應 CLI 讀 | `.tmp`→replace；rm／llm CLI 讀完會刪 |
| `K/<module NAME>/` | module 自管的慣例位置 | module 自管 | 核心沒有通用建立／清理規則 |

核心 JSON writer 是同一支 `aos_home.write_json()`，因此只有 rename 發佈，沒有 fsync 交易。

來源：[aos_kernel.py:61](../../../../proto4-3/aos_kernel.py)、[aos_kernel_init.py:43](../../../../proto4-3/aos_kernel_init.py)、[aos_kernel_schedule.py:94](../../../../proto4-3/aos_kernel_schedule.py)。

**3.3 `config.json` 全欄位**

| 欄位 | 正常型別 | init 旗標／預設 | 意思與驗證 |
|---|---|---|---|
| `ncpu` | 整數 | `--ncpu` 必填 | 工作 CPU 數；init 要 ≥1；不包含 kernel 自己那支 aos-run |
| `interval_ms` | 整數 | `--interval-ms 1000` | boot kernel 及新插工作 CPU 時給 aos-run 的 interval；init 要 ≥0 |
| `timeout_ms` | 整數 | `--timeout-ms 0` | boot kernel 及新插 CPU 的單次 timeout；0 不傳旗標；init 要 ≥0 |
| `quantum` | 整數 | `--quantum 5` | 有人排隊時，按 CPU 的完成 runs 差值決定輪替；init 要 ≥1 |
| `done_exit` | 整數 | `--done-exit 100` | 完成碼；0 關閉完成判定；init 不限制範圍 |
| `wait_exit` | 整數 | `--wait-exit 101` | 等待碼；init 不限制範圍，也不限制不能與其他碼相同 |
| `bad_after` | 整數 | `--bad-after 10` | 一般非零結果累計門檻；0 關閉此退件條件；init 要 ≥0 |
| `modules` | 字串陣列 | 重複 `--module PATH`；預設 `[]` | init 轉為絕對路徑；不在 init 時載入或驗存在 |

**讀取 config 比 init 驗證寬鬆：**

- 只要頂層是物件且 `ncpu` 是 Python `int` 就認為是家；`bool` 也是 int，會被接受。
- 其他所有值為 int 的 key 都併入 cfg，**包含未知 key**。
- 已知數值欄若是非 int，被忽略並用預設；`ncpu` 非 int 則整家無效。
- 不重新驗證數值範圍，手改負數／零與 bool 會進入後續邏輯。
- `modules` 不是完整 `list[str]` 就靜默變 `[]`。
- 每次 tick 重新讀 config；已存在 daemon CPU 不會因此更新 aos-run 的 flags。
- 修改 `ncpu` 沒有完整熱拔除流程：縮小時不主動刪除額外 CPU 或 daemon entries。

來源：[aos_kernel.py:86](../../../../proto4-3/aos_kernel.py)、[aos_kernel_init.py:27](../../../../proto4-3/aos_kernel_init.py)、[aos_kernel_boot.py:37](../../../../proto4-3/aos_kernel_boot.py)。

**3.4 inst 檔的欄位與 kernel 額外限制**

`K/inst.json`、`procs/*.json`、`cpus/*.json` 使用相同 posix inst 格式；不是另外一份「process metadata」格式。

| 欄位 | 執行器正常接受型別 | 缺省值 | kernel 特別處理 |
|---|---|---|---|
| `_metainfo` | 物件：`_type` 字串、`_version` 整數 | posix v1 | 完整 inst validator 驗；proto4 也把 null 當沒寫 |
| `argv` | 非空字串陣列，允許指示詞解析 | 必填 | add 在解析前要求 raw list 且 raw argv[0] 為字串 |
| `cwd` | 字串／指示詞／mkdir 選項物件 | inst 的 base | add 與 queue 檢查先要求 raw 字串；手放 queue 必須有此 key |
| `stdin` | 字串或 inherit 選項 | `/dev/null` | kernel 不改 |
| `stdout` | 字串或 append/mkdir/inherit 選項 | `/dev/null` | kernel 不改 |
| `stderr` | 同 stdout，另可 merge | `/dev/null` | add 未寫時印提醒；仍可加入 |
| `exit` | 字串或 append/mkdir 選項 | 不寫 | kernel 不讀它排程 |
| `envs` | 物件／指示詞／clear 選項 | `{}`，疊加繼承環境 | kernel 不改 |
| 其他頂層欄位 | 任意 | 無 | add 複製保留；aos-exec 不執行、不因普通未知欄位拒絕 |

相對 stream／exit／`$ref` 路徑由 aos-exec 以解析後 cwd 為中心處理。kernel 沒有替它們全部轉成絕對路徑。

來源：[aos_inst.py:92](../../../../proto4-3/aos_inst.py)、[aos_kernel_add.py:86](../../../../proto4-3/aos_kernel_add.py)、[aos_kernel_tick.py:104](../../../../proto4-3/aos_kernel_tick.py)。

**3.5 `state.json` 與一個行程的完整欄位**

頂層：

| 欄位 | 型別 | 初值 | 意思／讀取容錯 |
|---|---|---|---|
| `cpus` | 物件 | `{"0":null,...}` | CPU 編號字串→當前行程紀錄；不是物件則用 `{}` |
| `queue` | 字串陣列 | `[]` | FIFO；讀取只保留字串元素 |
| `waiting` | 物件 | `{}` | **排隊中** pid→等待計數；只保留字串 key、正 int 值，bool 也符合 int |

`cpus["n"]` 為 null 或：

| 欄位 | 正常型別 | 初值／缺省讀法 | 意思 |
|---|---|---|---|
| `pid` | 字串 | 上 CPU 的檔名 stem | 邏輯行程名稱 |
| `since` | number | 本次 tick 的 `time.time()` | 最近這次上 CPU 的時間 |
| `runs_at` | 整數 | 當時 daemon entry 的 runs | 本次 CPU 配置起點 |
| `seen_runs` | 整數 | 同 `runs_at` | kernel 已觀察過的最新 runs；舊紀錄缺少時退回 runs_at |
| `waiting` | 布林 | 缺少代表非 waiting | 最新觀察到 wait_exit 時設 true |
| `wait_runs` | 整數 | 首次從 0 累加 | 被歸為等待的新增 runs；輪替時可保存到頂層 waiting |
| `bad_runs` | 整數 | 首次從 0 累加 | 一般非零結果計數 |
| `bad_exit` | 整數 | 與 bad_runs 同時寫入 | 最近的一般非零退出碼 |
| `aos_ticks` | 整數 | 0／缺少 | 連續 tick 看到符合條件的 `kind=aos` 次數 |

沒有持久化的 proc Linux PID、每次 invocation ID、完整退出歷史、等待檔案清單、優先級、總執行次數或獨立 `state:"running"` 欄位。

狀態讀取只清理頂層容器，**不驗 `cpus` 每個 cur 的完整形狀**。壞 cur 可能讓 scheduler 或 status 丟例外。未知頂層欄位不由 `KHome.state()` 保留。

來源：[aos_kernel.py:102](../../../../proto4-3/aos_kernel.py)、[aos_kernel_schedule.py:26](../../../../proto4-3/aos_kernel_schedule.py)、[aos_kernel_schedule.py:94](../../../../proto4-3/aos_kernel_schedule.py)。

**3.6 行程狀態與檔案轉換**

| 狀態 | 實際表示 | 進入／離開 |
|---|---|---|
| queued | `procs/<pid>.json`；排程時進 queue | add／手放／CPU 換下；take 後檔移去 CPU |
| running | `cpus/<n>.json`＋`state.cpus[n]` | take/swap 上 CPU；不等於此刻有 POSIX child 正在跑 |
| waiting on CPU | cur 的 `waiting:true` | 最新可觀察結果是 wait_exit；有人排隊且 ran≥1 可讓位 |
| waiting in queue | `state.waiting[pid]` | waiting 行程換下時保存；再次上 CPU 移回 cur |
| done | `procs/done/<pid>.json` | done_exit 條件成立；不再排程 |
| bad | `procs/bad/<pid>.json` | queue 格式錯、aos_ticks 達門檻或 bad_runs 達門檻 |
| removed | 指令檔刪掉，或 CPU 換 idle | rm；不留 done、bad 或 removal tombstone |
| idle CPU | cur=null；CPU 檔為 `{"argv":["true"],"cwd":"."}` | 初建、檔案遺失、done/bad/rm |

等待不是阻塞式睡眠狀態：kernel 不監看結果檔，也不把 waiting 行程移到不可執行集合。它仍會被反覆排回 CPU。

**3.7 init、boot、add**

| 動作 | 精確流程 |
|---|---|
| init | 驗 flags → DIR 已存在就拒絕 → 建目錄 → 寫 kernel inst/config/state → append init log |
| init 的 CPU | 只建 `cpus/`，不先建立 `0.json...` |
| boot | 驗 cfg 與 K/inst 是檔 → 驗 daemon PID 活 → 讀 daemon state |
| boot 冪等 | key 已有 dict entry，且 state 為 `running` 或 `paused` 就回成功；不 resume paused，不要求 ready |
| boot 其他既有態 | 仍嘗試 add，通常被 daemon 以重複 key 拒絕 |
| boot 新掛載 | 對 `K/inst.json` 投 add；傳 interval，timeout 非零時也傳；不等待第一個 kernel tick |
| add 的路徑 | INST 相對於**呼叫時 cwd**解析；給 K 不會把 INST 改成相對於 K |
| add raw 驗證 | JSON 物件；cwd 字串；argv 非空 list、argv[0] 字串 |
| add cwd | 沒寫→來源 INST 所在目錄；相對→以來源目錄轉絕對；必須已是資料夾 |
| add argv[0] | 含 `/` 且相對→以正規化 cwd 轉絕對；含 `/` 但不存在→拒絕；純 PATH 名不預查 |
| add 自動名稱 | 所有活躍＋done＋bad 的純數字名，取最大值＋1；沒有則 `"1"` |
| add 指定名稱 | 只拒絕空字串及 `/`；沒有 LLM id 那套英數限制 |
| 活躍名稱來源 | procs 現有檔＋state queue＋state cpus；舊 state 也可能占名 |
| 指定名撞 done/bad | 完整驗證通過後先清同名舊紀錄，再發佈新檔 |
| add 最後驗證 | 寫 `procs/.<name>.json.tmp` → `aos_inst.load()` → 清舊紀錄 → replace 正式 procs 檔 |
| add 的 state | 不直接修改 queue/state；下一 tick 才收進表 |

来源：[aos_kernel_init.py:24](../../../../proto4-3/aos_kernel_init.py)、[aos_kernel_boot.py:11](../../../../proto4-3/aos_kernel_boot.py)、[aos_kernel_add.py:46](../../../../proto4-3/aos_kernel_add.py)。

**3.8 一格 tick 的完整順序**

| 次序 | 行為與邊界 |
|---|---|
| 1 | 讀 state；為 config 指定的 CPU 補上缺少的 null key |
| 2 | 讀 daemon 的 `state.runs`；讀不到視為空表 |
| 3 | 各 CPU 指令檔若不存在，先補 idle；若原 cur 有行程，直接清成 null |
| 4 | CPU realpath key 已在 daemon 表上就放進本輪 ready；**不檢查 alive、ready、state 或 running** |
| 5 | 缺少的 key 呼叫 ctl add；每顆 subprocess timeout 20 秒；成功或失敗都記 note；**新 add 成功的 CPU 當輪仍不進 ready** |
| 6 | 依 config 順序重新載入 modules，收載入 notes |
| 7 | 按檔名字典序處理 syscalls；**每張**先辨識是否內建 rm，其他才找 module；不是先處理整批所有 rm |
| 8 | 依順序跑每個 module 的 tick |
| 9 | 檢查 procs 頂層指令檔，壞的 replace 到 bad |
| 10 | 重建 FIFO，按 CPU 編號依序排 ready CPUs |
| 11 | 原子寫 state |
| 12 | append 一行 kernel.log，正常返回 0 |

queue 基本檢查：可讀 JSON 物件、raw 有 argv、raw 有 cwd、cwd 是字串，再呼叫完整 inst validator。**沒有要求 cwd 必須為絕對路徑，也沒有在這階段執行 aos-exec 的所有 filesystem 前置檢查。**

來源：[aos_kernel_tick.py:41](../../../../proto4-3/aos_kernel_tick.py)、[aos_kernel_tick.py:69](../../../../proto4-3/aos_kernel_tick.py)、[aos_kernel_tick.py:104](../../../../proto4-3/aos_kernel_tick.py)。

**3.9 FIFO 與選下一個行程**

| 項目 | 算法 |
|---|---|
| present | `procs/` 頂層以 `.json` 結尾的普通檔案，去副檔名為 pid |
| 新 pid 順序 | 純數字按數值排；非數字按字串排在數字之後 |
| 相同數值名稱 | 如 `1`、`01`，沒有額外 tie-break key |
| 保留原 queue | 只保留仍 present 且不在任何 cur 的 pid |
| 加新檔 | present 裡尚未在 queue/on_cpu 的，依上述順序排尾 |
| CPU 順序 | `0..ncpu-1` |
| idle CPU | 有 queue 就取隊首；replace 到 CPU，記當前 runs 為 runs_at/seen_runs |
| 量子用完 | 只有 queue 非空且 `runs-runs_at >= quantum` 才換人 |
| waiting 讓位 | 只有 queue 非空、cur waiting、`ran>=1` 才換人 |
| 沒人排隊 | 原行程續跑，即使 waiting 或量子已超過 |
| 換人 | `link(cpu, procs/old)` → `replace(procs/new,cpu)` → 新者離隊、旧者排尾 |
| 換人失敗 | 保留原排程或嘗試撤銷 hard-link，寫 note |
| 計數保存 | waiting 計數跨 swap 保存；bad_runs/bad_exit/aos_ticks **不跨 swap 保存** |

來源：[aos_kernel.py:56](../../../../proto4-3/aos_kernel.py)、[aos_kernel_schedule.py:9](../../../../proto4-3/aos_kernel_schedule.py)、[aos_kernel_schedule.py:111](../../../../proto4-3/aos_kernel_schedule.py)。

**3.10 退出碼判定的精確順序**

每個非 idle cur 先算：

```text
ran      = daemon.runs - cur.runs_at
new_runs = max(0, daemon.runs - cur.seen_runs)
```

若 daemon runs 比 seen_runs 小，先把 runs_at/seen_runs 重設成現值，並清 waiting、wait_runs、bad_runs、bad_exit、aos_ticks。

| 優先序 | 條件 | 動作 |
|---|---|---|
| 1：完成 | `done_exit != 0`、last_kind=`child`、last_exit=done_exit、`ran>=2` | park 到 done、CPU idle、cur=null；**當輪直接 return，不補下一人** |
| 2：觀察新結果 | `new_runs>0` | 更新 seen_runs，依最新 last_kind/last_exit 更新 waiting 與 bad 計數 |
| 3：執行器失敗 | last_kind=`aos` 且 `ran>=2` | 每個 kernel tick `aos_ticks += 1`；否則清為 0 |
| 4：aos 退件 | `aos_ticks>=2` | park 到 bad；當輪 return |
| 5：一般連敗 | bad_after 非零且 bad_runs≥bad_after | park 到 bad；當輪 return |
| 6：waiting | cur waiting、ran≥1、queue 非空 | swap |
| 7：量子 | ran≥quantum、queue 非空 | swap |

`_observe_exit()`：

| 最新結果 | waiting 計數 | bad 計數 |
|---|---|---|
| `child`＋wait_exit | waiting=true；wait_runs += new_runs | 清 bad_runs/bad_exit |
| `child`＋0 | 清 waiting/wait_runs | 清 bad |
| `child`＋done_exit | 清 waiting | 清 bad；完成判定在前面另做 |
| `child`＋125 | 預設下清 waiting | 清 bad；**不是 kind=aos，不走 aos_ticks** |
| `child`＋其他碼 | 清 waiting | bad_runs += new_runs；bad_exit=最新碼 |
| `aos`／`usage` | 清 waiting | 清 bad |

重要的可觀察含義：

| 事項 | 現況 |
|---|---|
| 100／101 | 只是 done_exit／wait_exit 的預設，可改 |
| done_exit=0 | 關閉完成；此時子程式的 100 會成為一般非零，仍可能因 bad_after 退件 |
| bad_after=0 | 只關閉一般非零退件；不關閉格式退件或 aos_ticks 退件 |
| 不同非零碼 | 例如 1→2→3，bad_runs 仍累加；log 最後會用最新 bad_exit 描述整串 |
| 漏看中間結果 | kernel 只看到最新碼；若 runs 一次增加 5，會把 5 次全歸到最新碼 |
| aos_ticks | 同一份未變的 `kind=aos` 快照也能連續兩個 tick 累加；不要求又完成新一次執行 |
| done | `ran>=2` 是防舊回報的門檻，不是精確 invocation 歸屬；行程退 100 仍可能再執行 |
| waiting | 不要求 ran≥2 才觀察；一般 bad 計數也沒有這道門 |
| runner 重啟辨識 | 只看 runs 是否倒退，沒有比對 daemon entry PID 或 generation |
| 退件原因 | 寫在 kernel.log；bad 指令檔沒有追加 error 欄位 |

來源：[aos_kernel_schedule.py:26](../../../../proto4-3/aos_kernel_schedule.py)、[aos_kernel_schedule.py:75](../../../../proto4-3/aos_kernel_schedule.py)。

