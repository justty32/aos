← [kernel](README.md)｜[spec 總導航](../README.md)

# 6. 命令列

```sh
aos-kernel init  [--target K] --config FILE      # 建家，info 照 FILE 寫；拒絕覆蓋（09-24 fix-r4 改：--cpu／--env 拿掉）
aos-kernel boot  [--target K] [--daemon-target D] [--wait-ms N]   # 見下；不跑整格
aos-kernel tick  [--target K] --chain C --seq N   # 一格；正常只有鏈自己會叫
aos-kernel add   INST [--target K] [--name NAME] [--once] [--pool P] [--dir-target R] [--interval-ms N] [--timeout-ms N] [--wait-ms N] [-- ARG...]
aos-kernel rm    NAME [--target K]
aos-kernel ack   NAME [--target K]              # （09-24 補）替 K/responses/NAME 放 ack
aos-kernel ls    [--target K] [--json]          # 偷看 K/state.json、D/state.json、kernel cpu 的 state.json 與 requests/；不放單，鏈斷了也能看
aos-kernel halt  [--target K] [--wait-ms N] [--no-wait]   # （09-24 試玩 r1 補；fix-r4 從 stop 改名）預設等停好
aos-kernel check [--target K] [--agent DIR] [--daemon-target D]   # （09-24 試玩 r1 補）啟動前檢查
aos-kernel -h ／ aos-kernel <子命令> -h    # （09-24 補）用法
```

（09-24 fix-r4 改）**K 一律用 `--target K` 給**，沒有位置參數。省略時找環境變數 `AOS_KERNEL_HOME`，再沒有就用目前資料夾；
`--target ""`＝用法錯 2。退 1 的錯誤行尾巴附 `（K＝<絕對路徑>，取自 --target｜AOS_KERNEL_HOME｜目前資料夾（沒給 --target、也沒設 AOS_KERNEL_HOME））`，
講清楚這次用了哪個 K、從哪來。**`--daemon-target D`**（boot、check）省略時跟 daemon 自己一樣：`AOS_DAEMON_HOME`，再沒有就目前資料夾（[daemon §1](../daemon/home.md)）。
`add` 的位置參數 `INST` 是要跑的目標（§2 的 `target`），跟 `--target`（kernel 家）是兩回事。
（09-24 fix-r4 改）舊版的 `aos-kernel stop` 改名 `halt`；kernel 的 syscall method 仍叫 `stop`（§2），不變。
改版前 boot 的鏈，下一格的 args 還是舊的位置參數格式、新版跑不起來（`ls` 會看到 `tick 停住`）：換版後重 `boot` 一次。

（09-24 fix-r4 改）**init `--config FILE`**：FILE 是一份 JSON，**就是 info.json 要寫的那幾格**（§1.1）：
`cpus` 必填（每顆 `pool`、`envs` 照 §1.1）；`tick_ms`／`interval_ms`／`timeout_ms`／`done_exit`／`bad_after` 可省（省＝預設）；
`_metainfo` 可省，有寫就必須是 kernel 第 1 版；寫了 `daemon`＝`FieldTypeMismatch`（那格是 boot 寫的）；其他不認得的鍵照 §1.1 原樣抄、不管。
沒有任何一顆 pool 是 `kernel` 就自動加 `k`（pool kernel）；`k` 已被別的池佔了＝`FieldTypeMismatch`。
寫之前用跟 info 同一套讀驗（中心 K）驗過：FILE 讀不到、不是 JSON、頂層不是字面物件（含 JSON `null`）、驗不過＝退 1、**什麼都不建**。要不要補 `k` 看的是**解完指示詞**的 pool（`pool` 寫 `$env` 也照解）；`cpus` 本身要是字面物件（補 `k` 要改它）。
**`--config` 沒給＝用法錯 2**（訊息講要給什麼、附最小例子；不去猜 `./kernel.json`）。`K/info.json` 已在才拒絕；K 資料夾在但沒有 info（上次建到一半）就補齊。
最小例子（一顆一般 cpu＋一顆 llm cpu；kernel 池的 `k` 自動加）：

```json
{"cpus": {"0": {}, "1": {},
          "llm": {"pool": "llm", "envs": {"AOS_LLM_CONFIG": "/abs/llm.json"}}}}
```

`aos-kernel init --target K --config kernel.json`。成功印一行 `initialized <K 絕對路徑>`。
