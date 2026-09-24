← [kernel](README.md)｜[spec 總導航](../README.md)

# 6. 命令列

```sh
aos-kernel init  [--target K] [--config FILE] [--daemon D]      # 建家，info 照 FILE 寫；拒絕覆蓋
aos-kernel boot  [--target K] [--wait-ms N]                     # 交接、拉 kernel 池、放第 1 格（boot.md）
aos-kernel halt  [--target K] [--wait-ms N] [--no-wait]         # 停機，預設等停好（cli-ops.md）
aos-kernel cpu add [--target K] --pool P [--count N] [--env KEY=VALUE]... [--daemon D] [--dpool NAME]   # cli-cpu.md
aos-kernel cpu rm  [--target K] (P/<i> | --pool P --count N)
aos-kernel cpu ls  [--target K] [--pool P] [--json]
aos-kernel ls    [--target K] [--pool P] [--procs] [--json] [-v] # 偷看、不放單（cli-ls.md）
aos-kernel add   INST [--target K] [--name NAME] [--once] [--pool P] [--dir-target R] [--interval-ms N] [--timeout-ms N] [--wait-ms N] [-- ARG...]
aos-kernel rm    NAME [--target K]
aos-kernel ack   NAME [--target K]                              # 替 K/responses/NAME 放 ack
aos-kernel check [--target K] [--daemon-target D] [--probe]     # 啟動前檢查；agent 的在 aos-agent check
aos-kernel tick  [--target K] --chain C --seq N                 # 一格；正常只有鏈自己會叫
aos-kernel -h ／ aos-kernel <子命令> -h
```

（2026-09-24 proto5-2 池式納入：`init` 改成池表、`--config` 可省、加 `--daemon`；新增 `cpu add／rm／ls`；`ls` 按池、加 `--pool`／`--procs`；
`boot` 不再收 `--daemon-target`（daemon 家寫在池表裡）。）

**K 一律用 `--target K` 給**，沒有位置參數。省略時找環境變數 `AOS_KERNEL_HOME`，再沒有就用目前資料夾；
`--target ""`＝用法錯 2。退 1 的錯誤行尾巴附 `（K＝<絕對路徑>，取自 --target｜AOS_KERNEL_HOME｜目前資料夾（沒給 --target、也沒設 AOS_KERNEL_HOME））`，
講清楚這次用了哪個 K、從哪來。`check` 的 `--daemon-target D` 只是多查一個 daemon 家（省略時照池表）。
`add` 的位置參數 `INST` 是要跑的目標（§2 的 `target`），跟 `--target`（kernel 家）是兩回事。
舊版的 `aos-kernel stop` 改名 `halt`；kernel 的 syscall method 仍叫 `stop`（§2），不變。
換版後舊鏈下一格的 args 格式可能跑不起來（`ls` 會看到 `tick 停住`）：換版後重 `boot` 一次。

## init

- `--config FILE`：一份 JSON，內容就是 [§1.1](info.md) 的格式（`_metainfo` 可省，會補上；有寫就必須是 kernel 第 2 版）。
  **只放 kernel 參數＋池定義，cpu 可以一顆都沒有**（`pools` 可以是 `{}`，或每池 `count: 0`）。讀驗照 §1.1；不過＝退 1、**什麼都不建**。
  FILE 讀不到、不是 JSON、頂層不是字面物件（含 JSON `null`）同樣退 1。
- 沒給 `--config`：預設 `{"pools": {"kernel": {"count": 1}}}`，其他全用預設。之後用 `cpu add` 加。
  「cpu 可空」指的是**工作池**可以一顆都沒有；跑 tick 的那顆 kernel cpu 永遠在。`kernel` 池沒寫就補 `{"count": 1}`。
- `daemon`：`--daemon D` 優先，否則 config 裡的，否則 `AOS_DAEMON_HOME`（轉絕對路徑），都沒有就不寫——boot 時才報 `NoDaemon`。
- `tick_ms`…`bad_after` 五格照預設寫進去；`cpu`、`sweep` 不寫（讀時補）。
- 建 `requests/`、`responses/`、`pools/`；不建任何 cpu 的家（boot／tick 建）。`K/info.json` 已在就拒絕；K 資料夾在但沒有 info（上次建到一半）就補齊。
- 印 `initialized <K 絕對路徑>`。

第 1 版的 `--cpu`、`--env NAME:KEY=VALUE` 拿掉，改用 `cpu add`。最小例子（一個一般池兩顆＋一個 llm 池一顆；kernel 池自動加）：

```json
{"daemon": "/abs/D",
 "pools": {"default": {"count": 2},
           "llm": {"count": 1, "envs": {"AOS_LLM_CONFIG": "/abs/llm.json"}}}}
```

`aos-kernel init --target K --config kernel.json`。
