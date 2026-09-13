# proto4-3／aos-kernel
← [README](../README.md)

## aos-kernel：作業系統的第一個程序，管「哪顆 cpu 上是哪個行程」

[proto4 筆記第 16～18 節](../../proto4/notes/2026-09-08-ideas.md)的原型。名詞先對齊：

- **daemon ＝硬體**。`aos-daemon-ctl add foo.json` ＝**插一顆 cpu**，`rm` ＝拔掉。一份
  inst.json 就是那顆 cpu 的「指令暫存器」，aos-run 每隔 interval 讀它一次、跑一次。
- **kernel ＝第一個程序**。它是**唯一**會叫 `aos-daemon-ctl` 的人（cpu 的存在與使用權），
  也是**唯一**會改 cpu 那份 inst.json 的人（cpu 下一次去跑誰）。
- kernel 自己也是被 daemon 跑著的一個 proc：它的家裡有一份 `inst.json`，使用者手動
  `ctl add` 它＝**上電**，之後 kernel 每隔一段時間自己跑一次 `aos-kernel-tick`。

### 家長什麼樣

```
K/inst.json         kernel 自己那顆 cpu 的指令：{"argv":["…/aos-kernel-tick"],"cwd":"."}
K/config.json       {"ncpu":2,"interval_ms":1000,"timeout_ms":0,"quantum":5,"done_exit":100}
K/procs/<pid>.json  就緒佇列：等著上 cpu 的行程，檔名去掉 .json ＝ pid
K/procs/bad/        退件（不是 JSON 物件／沒有 argv／沒寫 cwd 的都搬來這裡）
K/procs/done/       用保留退出碼表示做完的行程
K/cpus/<n>.json     每顆 cpu 一份 inst.json，這個路徑就是 daemon 表上的 key
K/state.json        kernel 自己的表：cpu n → pid、上去的時間、上去時的 runs、佇列
K/kernel.log        每回合 append 一行
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
aos-kernel-init DIR --ncpu N [--interval-ms X] [--timeout-ms Y] [--quantum Q] [--done-exit N]
aos-kernel-tick         # 心跳：在家裡（cwd ＝ K）跑一回合，不吃參數
aos-kernel ls [DIR]     # 印給人看：每顆 cpu 上是誰、上去多久、跑了幾次、誰在等
```

| 指令 | 做什麼 | 退出碼 |
|---|---|---|
| `aos-kernel-init` | 建家與四個檔；`--interval-ms`／`--timeout-ms` 是**每顆 cpu** `ctl add` 時給 aos-run 的旗標（預設 1000／0），`--quantum` 是時間片（預設 5，單位是「cpu 跑了幾次」） | 0；**DIR 已經存在＝1**（不動它） |
| `aos-kernel-tick` | 跑一回合，見下面五步 | **一律 0**；cwd 不是家（沒有 `config.json`）＝1 |
| `aos-kernel ls [DIR]` | 給 DIR 就先進去，否則用 cwd；讀 kernel ＋ daemon 的 `state.json` 印存活狀態、cpu、佇列、bad 與 done | 0；不是家＝1 |

`aos-kernel init`／`aos-kernel tick`（舊的子命令）都拿掉了：退出碼 2，stderr 提示改用
`aos-kernel-init`／`aos-kernel-tick`。以後 `aos-kernel-boot`（§19.3，一條指令做完「開
daemon → kernel init → ctl add kernel 的 inst.json」）也會是同一系列的獨立指令。

### aos-kernel-tick 每回合五步（順序固定）

1. **讀自己的表**（`state.json`，沒有＝空表）。
2. **點 cpu**：直接讀 daemon 的 `state.json`（不開 ctl 進程），看 `cpus/0.json`…
   `cpus/N-1.json` 這 N 個 key 哪些在 daemon 表上。不在表上的：檔案不見了就先寫一份 idle
   指令（`{"argv":["true"],"cwd":"."}`），再 `aos-daemon-ctl add <絕對路徑> --interval-ms X`
   把它插上去（**不開 `--stop-on-error`**）。所以 aos-run 被 `ctl rm` 掉、或 daemon 重開過，
   下一回合就自己補回來。add 失敗（daemon 沒在跑之類）＝記一行 log、**那顆 cpu 這回合不排程**，
   退出仍是 0——kernel 不會因為外面的事死掉。
3. **檢查佇列**：`procs/*.json`（不含 `bad/`）逐個讀，不是 JSON 物件／沒有 `argv`／`cwd`
   沒寫或不是字串 → 搬去 `procs/bad/` 同名並記 log。**cwd 一定要寫死**：檔案會被搬到
   `cpus/n.json`，沒寫 cwd 的話預設 cwd 會跟著變成 cpu 的資料夾，行程就跑錯地方了。
   （這道檢查**只有 kernel 做**，daemon／aos-run／aos-exec 維持原本行為。）
4. **排程**：每顆 cpu 看一次——
   - 先看做完沒：`last_kind=child` 且 `last_exit=done_exit` 且 `runs−runs_at≥2` → 搬進
     `procs/done/`、換成 idle；再看 quantum 要不要換人。
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
5. **寫表寫 log**：`state.json` 先 `.tmp` 再 rename、`kernel.log` append 一行，退出 0。

`state.json` 長這樣：

```json
{"cpus": {"0": {"pid": "3", "since": 1788999123.4, "runs_at": 12},
          "1": null},
 "queue": ["5", "7"]}
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
./aos-daemon &                                          # 硬體上電
./aos-kernel-init K --ncpu 2 --interval-ms 1000 --quantum 5
./aos-daemon-ctl add K/inst.json --interval-ms 1000     # 插上第一顆 cpu ＝ 跑 aos-kernel-tick
cp my-proc.json K/procs/3.json                          # 把行程丟進就緒佇列（cwd 要寫死）
./aos-kernel ls K                                       # 看誰在哪顆 cpu 上
```

`AOS_DAEMON_HOME` 那三支要對得上：kernel 是從 daemon 繼承下來的，所以 daemon 用
`AOS_DAEMON_HOME=…` 開比用 `--home` 保險（`--home` 不會傳給子孫）。

### kernel 這一版沒做什麼

- **行程做完是應急版**：保留退出碼 100，行程回這個碼就會被收進 `procs/done/`；還沒有行程
  主動叫 kernel 的 syscall，`procs/done/` 不會自動清，做完行程的 cwd 也不動。
- **沒有優先級、沒有 nice**，時間片一律 quantum 次，佇列純 FIFO。
- **沒有 syscall 收件匣**（行程不能 fork、不能自己丟東西進 `procs/`）、**不改 cpu 的韌體設定**
  （`ctl add` 給的 interval／timeout 定死不改）、**沒有 daemon↔kernel 專用通道**（每回合只看
  `state.json`，中間的退出碼看不到）。
- **`procs/` 裡就是原封不動的 inst.json**，直接搬上 cpu。以後那裡會多權限、優先級之類的欄位，
  到時就得由 kernel 轉一手。
- **kernel 只做格式檢查，不做權限檢查**：能寫 `procs/` 的人就能用你的身分跑任何東西。
- **搶佔不了正在跑的那一次**：rename 只影響「下一次」開跑讀到誰，手上那次會跑完。
- **一個家只該有一個 kernel 在 tick**：兩個 tick 同時跑會搶同一批檔案，v1 沒有鎖。
