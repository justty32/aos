← [kernel](README.md)｜[spec 總導航](../README.md)

# 6. 命令列

```sh
aos-kernel init  [--target K] [--config FILE] [--daemon D]      # 建家，info 照 FILE 寫；拒絕覆蓋
aos-kernel boot  [--target K] [--wait-ms N]                     # 寫帳本、向 daemon 登記開 tick（boot.md）；平常用 aos up
aos-kernel halt  [--target K] [--wait-ms N] [--no-wait]         # 停機，預設等停好（cli-ops.md）
aos-kernel cpu add [--target K] --pool P [--count N] [--env KEY=VALUE]... [--daemon D] [--dpool NAME]   # cli-cpu.md
aos-kernel cpu rm  [--target K] (P/<i> | --pool P --count N)
aos-kernel cpu ls  [--target K] [--pool P] [--json]
aos-kernel ls    [--target K] [--pool P] [--procs] [--json] [-v] # 偷看、不放單（cli-ls.md）
aos-kernel add   INST [--target K] [--name NAME] [--once] [--pool P] [--dir-target R] [--interval-ms N] [--timeout-ms N] [--park-ms N] [--wait-ms N] [-- ARG...]
aos-kernel rm    NAME [--target K]
aos-kernel proc  NAME [--target K] [--json]                     # （one-boot）查一筆行程，給程式讀帳本（下面 proc）
aos-kernel wake  NAME [--target K]                              # （09-24 停車）叫醒停著的行程（syscall.md 的 wake）
aos-kernel ack   NAME [--target K]                              # 替 K/responses/NAME 放 ack
aos-kernel check [--target K] [--daemon-target D] [--probe]     # 啟動前檢查；agent 的在 aos-agent check
aos-kernel tick  [--target K]                                   # 一格；正常由 daemon 開（tick.md）
aos-kernel -h ／ aos-kernel <子命令> -h
```

（2026-09-24 proto5-2 池式納入：`init` 改成池表、`--config` 可省、加 `--daemon`；新增 `cpu add／rm／ls`；`ls` 按池、加 `--pool`／`--procs`；
`boot` 不再收 `--daemon-target`（daemon 家寫在池表裡）。2026-09-24 one-boot：`tick` 不再收 `--chain`／`--seq`（舊格帶了就退 0）、新增 `proc`；開機停機平常用 `aos up`／`aos down`，見 [daemon §11](../daemon/up.md)。）

**K 一律用 `--target K` 給**，沒有位置參數。省略時找環境變數 `AOS_KERNEL_HOME`，再沒有就用目前資料夾；
`--target ""`＝用法錯 2。退 1 的錯誤行尾巴附 `（K＝<絕對路徑>，取自 --target｜AOS_KERNEL_HOME｜目前資料夾（沒給 --target、也沒設 AOS_KERNEL_HOME））`，
講清楚這次用了哪個 K、從哪來。`check` 的 `--daemon-target D` 只是多查一個 daemon 家（省略時照池表）。
`add` 的位置參數 `INST` 是要跑的目標（§2 的 `target`），跟 `--target`（kernel 家）是兩回事。
舊版的 `aos-kernel stop` 改名 `halt`；kernel 的 syscall method 仍叫 `stop`（§2），不變。
換版後 `aos up`（或重 `boot`）一次：帳本格式、登記給 daemon 的參數都照新版重寫。

## init

- `--config FILE`：一份 JSON，內容就是 [§1.1](info.md) 的格式（`_metainfo` 可省，會補上；有寫就必須是 kernel 第 2 版）。
  **只放 kernel 參數＋池定義，cpu 可以一顆都沒有**（`pools` 可以是 `{}`，或每池 `count: 0`）。讀驗照 §1.1；不過＝退 1、**什麼都不建**。
  FILE 讀不到、不是 JSON、頂層不是字面物件（含 JSON `null`）同樣退 1。
- 沒給 `--config`：預設 `{"pools": {}}`（一個工作池都沒有），其他全用預設。之後用 `cpu add` 加。
  （one-boot）不再補 kernel 池；`pools` 寫了 `kernel`＝`FieldTypeMismatch` 退 1（保留名，[§1.1](info.md)）。
- `daemon`：`--daemon D` 優先，否則 config 裡的，否則 `AOS_DAEMON_HOME`（轉絕對路徑），都沒有就不寫——boot 時才報 `NoDaemon`。
- `tick_ms`…`bad_after` 五格照預設寫進去；`cpu`、`sweep`、`park_ms`、`tick_timeout_ms` 不寫（讀時補）。
- 建 `requests/`、`responses/`、`pools/`；不建任何 cpu 的家（boot／tick 建）。`K/info.json` 已在就拒絕；K 資料夾在但沒有 info（上次建到一半）就補齊。
- 印 `initialized <K 絕對路徑>`。

第 1 版的 `--cpu`、`--env NAME:KEY=VALUE` 拿掉，改用 `cpu add`。最小例子（一個一般池兩顆＋一個 llm 池一顆）：

```json
{"daemon": "/abs/D",
 "pools": {"default": {"count": 2},
           "llm": {"count": 1, "envs": {"AOS_LLM_CONFIG": "/abs/llm.json"}}}}
```

`aos-kernel init --target K --config kernel.json`。

## proc

（2026-09-24 one-boot 新增）`aos-kernel proc NAME [--target K] [--json]` 查一筆行程——**給程式讀帳本的正式入口**。
只讀帳本 `procs` 那一列、`busy` 按行程查一列（O(1)），不整份讀帳本、不放單、不拿鎖。aos-agent 用的是同一支 lib（`lib/aos_kernel_store.py`）。
- 文字版：`<NAME>  反覆｜once  <status>  runs N  fails N`，正在某顆 cpu 上再加 `  在 P/<i>`（已被 `rm`、跑完就丟的加 `（已 rm，跑完就丟）`）；下一行 `  target <路徑>`。
- `--json`：stdout 一個物件加換行：

```json
{"_metainfo": {"_type": "aos_kernel_proc", "_version": 1}, "name": "agent-bob", "found": true,
 "proc": {"request": "cli-1790000000000000000-77.json", "target": "/abs/agent-bob/tick.json", "once": false, "pool": "default",
          "interval_ms": 1000, "timeout_ms": 0, "status": "running", "runs": 7, "fails": 0, "not_before": 1790000001.2, "pending": null},
 "cpu": "default/1", "discard": false}
```

| 欄 | 型別與意思 |
|---|---|
| `_metainfo` | 固定 `{"_type": "aos_kernel_proc", "_version": 1}`。承諾同 ls `--json`：版本內只加鍵、不改名、不刪、不改型別 |
| `name` | 問的名字（原樣） |
| `found` | bool：帳本有沒有這個行程 |
| `proc` | 帳本那筆原樣（[§1.2](ledger-keys.md) 的 `procs.<NAME>`，鍵隨行程而異）；沒有＝`null` |
| `cpu` | 正在哪顆（`P/<i>`，`busy` 有它）；沒在跑＝`null` |
| `discard` | bool：那顆上的工作已被 `rm`、回音到了就丟 |

- 退出碼：找到＝0；沒這個行程（含 K 從沒 boot 過）＝1，`--json` 照樣印 `found: false` 那份，文字版 stderr `aos-kernel: NotFound: 沒有這個行程：NAME`；
  帳本還是舊的 `state.json`＝`LedgerVersion` 退 1；帳本讀不到＝`ReadFailed` 退 1（這兩種 stdout 空）；用法錯＝2。
