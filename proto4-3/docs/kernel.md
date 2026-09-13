# proto4-3／aos-kernel
← [README](../README.md)

以下指令假設你已把 `proto4-3` 的絕對路徑加進 `PATH`。

## aos-kernel：作業系統的第一個程序，管「哪顆 cpu 上是哪個行程」

[proto4 筆記第 16～18 節](../../proto4/notes/2026-09-08-ideas.md)的原型。名詞先對齊：

- **daemon ＝硬體**。`aos-daemon-ctl add foo.json` ＝**插一顆 cpu**，`rm` ＝拔掉。一份
  inst.json 就是那顆 cpu 的「指令暫存器」，aos-run 每隔 interval 讀它一次、跑一次。
- **kernel ＝第一個程序**。它是**唯一**會叫 `aos-daemon-ctl` 的人（cpu 的存在與使用權），
  也是**唯一**會改 cpu 那份 inst.json 的人（cpu 下一次去跑誰）。
- kernel 自己也是被 daemon 跑著的一個 proc：它的家裡有一份 `inst.json`，
  `aos-kernel-boot /tmp/K` 把它放上 daemon，之後 kernel 每隔一段時間自己跑一次 `aos-kernel-tick`。

### 家長什麼樣

```
K/inst.json         kernel 自己那顆 cpu 的指令：{"argv":["…/aos-kernel-tick"],"cwd":"."}
K/config.json       上述整數設定，另可有 "modules":["/abs/xxx_module.py"]
K/procs/<pid>.json  就緒佇列：等著上 cpu 的行程，檔名去掉 .json ＝ pid
K/procs/bad/        退件（格式壞、連續回 125，或一般非零退出達 bad_after 次）
K/procs/done/       回 done_exit（預設 100）收工的行程；rm 拿掉的不會進來
K/cpus/<n>.json     每顆 cpu 一份 inst.json，這個路徑就是 daemon 表上的 key
K/syscalls/         行程給 kernel 的單子；內建 rm，module 可增加 op
K/syscalls/done/    kernel 處理完的回音
K/state.json        kernel 自己的表：cpu n → pid、上去的時間、上去時的 runs、佇列
K/kernel.log        每回合 append 一行
K/llm/              llm module 自己的家；慣例是 module 住 K/<NAME>/
```

`aos-kernel-init` 寫進 `inst.json` 的 `argv[0]` 是 **`aos-kernel-tick` 的絕對路徑**——
daemon→aos-run→aos-exec 的 PATH 是使用者開 daemon 時那一份，未必找得到 proto4-3；寫死絕對
路徑就不用管 PATH。串流三條都不寫（aos-exec 開 `stdout` 是清空重寫，當不了 log，要看流水帳
就看 `kernel.log`）；`envs` 也不寫，`AOS_DAEMON_HOME` 從 daemon 一路繼承下來。

### 指令：一支系列，各管各的壽命

`init`（重灌作業系統、很久一次）跟 `tick`（心跳、每回合）不是同一種壽命的東西，`ls`
（給人看）也不是心跳的一部分，所以三個都是各自獨立的指令，不擠在一支程式的子命令裡
（[proto4 筆記 §19.4／§19.7](../../proto4/notes/2026-09-08-ideas.md)）：

```sh
aos-kernel-init DIR --ncpu N [--interval-ms X] [--timeout-ms Y] [--quantum Q] [--done-exit N] [--wait-exit N] [--bad-after N] [--module PATH]...
aos-kernel-boot DIR [--home H] # 開機：只把已初始化的 kernel 放上正在跑的 daemon
aos-kernel-tick         # 心跳：在家裡（cwd ＝ K）跑一回合，不吃參數
aos-kernel add [DIR] INST.json [--name NAME] # 檢查、轉路徑、配名後排進佇列
aos-kernel rm [DIR] NAME # 投一張單，等 kernel 拿掉佇列或 cpu 上的行程
aos-kernel ls [DIR]     # 印給人看：每顆 cpu 上是誰、上去多久、跑了幾次、誰在等
```

| 指令 | 做什麼 | 退出碼 |
|---|---|---|
| `aos-kernel-init` | 建家與四個檔；`--interval-ms`／`--timeout-ms` 是**每顆 cpu** `ctl add` 時給 aos-run 的旗標（預設 1000／0），`--quantum` 是時間片（預設 5），`--wait-exit` 預設 101，`--bad-after` 預設 10 | 0；**DIR 已經存在＝1**（不動它） |
| `aos-kernel-boot` | 看 daemon 上有沒有 kernel 的 `inst.json`；沒有就 add，重複跑無害。**不開 daemon、不 init** | 0；還沒 init 或 daemon 沒跑＝1 |
| `aos-kernel-tick` | 跑一回合，見下面七步 | **一律 0**；cwd 不是家（沒有 `config.json`）＝1 |
| `aos-kernel add` | 一個參數時 DIR＝cwd，兩個時第一個是 DIR；檢查 inst，轉 cwd／argv[0]，自動配數字名或吃 `--name`，再原子排進 `procs/` | 0；不是家、inst 不合格或撞名＝1 |
| `aos-kernel rm` | 一個參數時 DIR＝cwd，兩個時第一個是 DIR；只寫 `syscalls/` 單子，等 tick 回音 | 成功＝0；找不到、家不對或 kernel 沒回應＝1 |
| `aos-kernel ls [DIR]` | 給 DIR 就先進去，否則用 cwd；讀 kernel ＋ daemon 的 `state.json` 印存活狀態、cpu、佇列、bad 與 done | 0；不是家＝1 |

### kernel module

`config.json` 可有選填的 `"modules":["/絕對路徑/xxx_module.py", ...]`；省略等於空陣列。
初始化時用可重複的 `--module PATH`，寫入時會轉成絕對路徑。載不到檔、語法壞掉或約定不合，
都只在當回合留一句 note，kernel 照常完成。

module 要在 init 時就用 `--module` 掛。家已經存在時，init 不會覆寫；之後要補只能手改
`config.json` 的 `modules`。

一個 module 是一支 Python 檔。`NAME` 是子命令名，`OPS` 是它認得的 syscall op tuple；其餘
hook 缺了就表示沒有那項能力：

```python
handle(h, cfg, st, ticket) -> (ok: bool, msg: str)
tick(h, cfg, st) -> list[str]
status(h, cfg) -> str | None
cli(h, cfg, argv) -> int
```

module 的 `handle`／`tick`／`status`／`cli` 丟例外也不會打死 kernel：syscall 會收到失敗回音，
tick 與 ls 留一句 note，CLI 則退出 1。每回合在原第 3 步處理 syscall：內建 `rm` 先處理，
其他 op 交給 `OPS` 認得它的 module（第 2.5 步）；接著每個 module 跑一格（第 2.6 步），才檢查
普通行程佇列。`aos-kernel <NAME> [K] ...` 會轉給同名 module 的 `cli`；第一個參數是含
`config.json` 的資料夾才當 K，否則 K 是 cwd。

第一個 module 是 [`llm_cpu_module.py`](../../proto4-5/llm_cpu_module.py)：排程家在 `K/llm/`，
由 kernel 每回合順手跑一格；使用方式見 [proto4-5 README](../../proto4-5/README.md)。

`aos-kernel init`／`aos-kernel tick`（舊的子命令）都拿掉了：退出碼 2，stderr 提示改用
`aos-kernel-init`／`aos-kernel-tick`。

`add` 讀原始 JSON，只幫兩個地方轉絕對：沒寫 cwd 就用 INST.json 所在資料夾，相對 cwd 也
從那裡算；`argv[0]` 含 `/` 且是相對路徑時，再從轉好的 cwd 算。它會先拒絕不存在的 cwd、
空 argv、以及含 `/` 但不存在的 argv[0]；寫進暫存檔後還會用 aos-exec 的完整規則驗一次，
未知欄位也會擋。沒寫 stderr 仍可排，但會提醒你出錯可能看不到。

### aos-kernel-tick 每回合七步（順序固定）

1. **讀自己的表**（`state.json`，沒有＝空表）。
2. **點 cpu**：直接讀 daemon 的 `state.json`（不開 ctl 進程），看 `cpus/0.json`…
   `cpus/N-1.json` 這 N 個 key 哪些在 daemon 表上。不在表上的：檔案不見了就先寫一份 idle
   指令（`{"argv":["true"],"cwd":"."}`），再 `aos-daemon-ctl add <絕對路徑> --interval-ms X`
   把它插上去（**不開 `--stop-on-error`**）。所以 aos-run 被 `ctl rm` 掉、或 daemon 重開過，
   下一回合就自己補回來。add 失敗（daemon 沒在跑之類）＝記一行 log、**那顆 cpu 這回合不排程**，
   退出仍是 0——kernel 不會因為外面的事死掉。
3. **處理 syscall**：按檔名讀 `syscalls/*.json`；內建 `rm`，其餘交給 module。佇列裡的直接刪；cpu 上的
   原子換成 idle，兩種都不進 `procs/done/`。看不懂的單也會留下失敗回音。
4. **跑 modules**：每個已載入 module 的 `tick` 跑一次；例外只記 note。
5. **檢查佇列**：`procs/*.json`（不含 `bad/`）逐個讀，不是 JSON 物件、缺必要欄位，或
   過不了 aos-exec 的完整驗證 → 搬去 `procs/bad/` 同名並記精確原因。**cwd 一定要寫死**：檔案會被搬到
   `cpus/n.json`，沒寫 cwd 的話預設 cwd 會跟著變成 cpu 的資料夾，行程就跑錯地方了。
   （這道檢查**只有 kernel 做**，daemon／aos-run／aos-exec 維持原本行為。）
6. **排程**：每顆 cpu 看一次——
   - 先看做完沒：`last_kind=child` 且 `last_exit=done_exit` 且 `runs−runs_at≥2` → 搬進
     `procs/done/`、換成 idle；再看 quantum 要不要換人。
   - `last_kind=aos` 且已跨過換人時的舊回報，連續兩個 tick 都看到 125 → 搬進
     `procs/bad/`、換成 idle；詳細原因用 `aos-exec /tmp/K/procs/bad/NAME.json --stderr -` 看。
   - `last_kind=child` 且 `last_exit=wait_exit`（預設 101）→ 在 state 標 `waiting:true`，並用
     `wait_runs` 記連續等了幾回合。有人排隊就把它換回隊尾；沒人排隊就繼續留在 cpu。
     排隊中的 `ls` 仍會標 `waiting`，退出碼變成別的就清掉等待狀態。
   - `last_kind=child` 的其他非零退出若連續達 `bad_after` 次（預設 10）→ 搬進
     `procs/bad/`，原因會寫「連續 N 次退 CODE」。0、`done_exit`、`wait_exit` 與 125 都會
     打斷這個計數；`bad_after:0` 會關掉這條，保留永遠重跑的做法。125 的兩次觀察規則不變。
   - 上面是 idle（或沒記錄）而且有人在等 → 把隊首那位 `rename` 上去。
   - 上面有人，而且「daemon 現在的 `runs` － 它上去時記的 `runs` ≥ quantum」，而且**還有人在等**
     → 換人。**沒人在等就讓它續跑**（v1 的行程不會自己結束）。
   - **換檔不留空窗**：先 `os.link(cpus/n.json, procs/<舊>.json)`（舊的先在 `procs/` 有一個
     名字），再 `os.rename(procs/<新>.json, cpus/n.json)`（原子蓋過去）。任何時刻
     `cpus/n.json` 都存在、內容不是完整的舊檔就是完整的新檔，所以 aos-run 剛好開跑也吃不到
     125。要換成 idle（例如 cpu 那個檔被人刪了）就寫 `.tmp` 再 rename。
   - **佇列是 FIFO**：新出現在 `procs/` 的排尾巴、被換下來的也排尾巴、檔案不見的（人手動刪）
     從佇列拿掉。純照 pid 大小挑的話小 pid 會永遠優先，所以 `state.json` 自己記一個
     `queue` 陣列；同一回合新冒出來的照 pid 順序排（數字比數字、非數字排在數字後面）。
7. **寫表寫 log**：`state.json` 先 `.tmp` 再 rename、`kernel.log` append 一行，退出 0。

`state.json` 長這樣：

```json
{"cpus": {"0": {"pid": "3", "since": 1788999123.4, "runs_at": 12,
                  "waiting": true, "wait_runs": 3},
          "1": null},
 "queue": ["5", "7"],
 "waiting": {"7": 2}}
```

`runs_at` 是「這位上 cpu 那一刻，那顆 cpu 的 aos-run 總共跑過幾次」，時間片就是拿它跟現在
的 `runs` 相減。cpu 被 `ctl rm` 過再插回來時 `runs` 會從 0 重數，kernel 看到「現在的比記的
還小」就把 `runs_at` 重設，不會卡住不換人。

### 開機順序

`my-proc.json` 可以是：

```json
{"argv":["/abs/程式"],"cwd":"/abs/資料夾","stdout":"out.txt","stderr":"err.txt"}
```

```sh
aos-daemon &                                             # 硬體上電
aos-kernel-init /tmp/K --ncpu 2 --interval-ms 1000 --quantum 5 # module 也要在 init 時掛
aos-kernel-boot /tmp/K                                  # 把 kernel 放上 daemon
aos-kernel add /tmp/K /abs/my-proc.json                 # 檢查、轉路徑後排進佇列
aos-kernel ls /tmp/K                                    # 看誰在哪顆 cpu 上
```

`AOS_DAEMON_HOME` 那三支要對得上：kernel 是從 daemon 繼承下來的，所以 daemon 用
`AOS_DAEMON_HOME=…` 開比用 `--home` 保險（`--home` 不會傳給子孫）。
`ls` 若沒有這個環境變數、家不存在或沒有 state，會印「找不到 daemon 的家」；只有找到 state
和 pid、但 pid 已不活著時才印 `daemon dead`。

### kernel 這一版沒做什麼

- **行程做完是應急版**：保留退出碼 100，行程回這個碼就會被收進 `procs/done/`；這裡不會
  自動清，做完行程的 cwd 也不動。
- **沒有優先級、沒有 nice**，時間片一律 quantum 次，佇列純 FIFO。
- **內建 syscall 目前只有 rm**；module 可增加其他 op。不改 cpu 的韌體設定（`ctl add` 給的 interval／timeout 定死不改）、
  **沒有 daemon↔kernel 專用通道**（每回合只看
  `state.json`，中間的退出碼看不到）。
- **`procs/` 裡仍是 inst.json**，add 只先正規化下面兩個路徑，kernel 再直接搬上 cpu。以後那裡
  會多權限、優先級之類的欄位，到時就得由 kernel 轉一手。
- **add 只轉 cwd／argv[0]**；stdin／stdout／stderr／`$ref` 的相對路徑不轉，那些本來就是以
  cwd 為中心。
- **kernel 只做格式檢查，不做權限檢查**：能寫 `procs/` 的人就能用你的身分跑任何東西。
- **搶佔與 rm 都不會殺正在跑的那一次**：rename 只影響「下一次」開跑讀到誰，手上那次會跑完。
- **一個家只該有一個 kernel 在 tick**：兩個 tick 同時跑會搶同一批檔案，v1 沒有鎖。
