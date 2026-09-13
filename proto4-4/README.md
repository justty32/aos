← [proto4-3](../proto4-3/README.md)（作業系統那層：aos-exec／aos-run／aos-daemon／aos-kernel）

# proto4-4 — 逐步 lisp（Janet）

## 是什麼

一個 `.janet` 檔就是一個行程；cpu 每叫它一次，它只跑下一個頂層 form，再把環境收好等下一格。
每一格都會把那個 form 的值印到 stdout。

使用者的說法是：**「逐一執行指定 `.janet` 檔案中的每個 list」**。`def`、`defn`與閉包會藉 Janet image 跨行程留下來。

## 怎麼跑

`aos-step` 是 shebang 執行檔：

```sh
export PATH="$HOME/.local/bin:$PATH"   # /usr/bin/env 才找得到 janet
cd /tmp/my-proc
/abs/proto4-4/aos-step prog.janet
/abs/proto4-4/aos-step prog.janet
/abs/proto4-4/aos-step prog.janet
/abs/proto4-4/aos-step prog.janet
/abs/proto4-4/aos-step prog.janet       # 全做完了：不做事，回 100
echo $?                                 # 全部跑完那次回 100
/abs/proto4-4/aos-step prog.janet --status
```

做完回 100，這個號碼跟 kernel 的 `done_exit` 預設一致；要改就改 kernel 那邊
（`aos-kernel-init --done-exit`），程式端不給改。

`--status` 只印一行 JDN：

```janet
{:pc 4 :n 4 :done true :changed false :error nil}
```

`:changed` 表示現在的程式跟上次成功那格時不同。

要從頭來：

```sh
/abs/proto4-4/aos-step prog.janet --reset
```

放到 cpu 上，先在行程資料夾寫 `inst.json`：

```json
{"argv": ["/abs/proto4-4/aos-step", "prog.janet"], "cwd": "/abs/那個資料夾", "stdout": "out.txt", "stderr": "err.txt"}
```

`stdout`／`stderr` 每格會被清空，要留紀錄自己 append 到別的檔。

`argv[0]` 刻意用絕對路徑，不靠 PATH 找 `aos-step`；但它的 `#!/usr/bin/env janet` 仍需要執行時的 PATH 裡有 `janet`（這裡是 `~/.local/bin/janet`）。

```sh
/abs/proto4-3/aos-run /abs/行程/inst.json --interval-ms 100 --max-runs 5
```

一次 run 就是一格，一格只跑一個 form。

### 放進 kernel

放進 kernel `procs/` 的也是同一形狀的 inst.json：

```json
{"argv": ["/abs/proto4-4/aos-step", "prog.janet"], "cwd": "/abs/那個資料夾", "stdout": "out.txt", "stderr": "err.txt"}
```

存成 `my-step.json` 後用 `../proto4-3/aos-kernel add K my-step.json` 排進去；它會配名字，
也會幫你把 cwd 與含 `/` 的相對 argv[0] 轉成絕對路徑。

最後一個 form 跑完的那格仍回 0；下一格開始回 100，kernel 會自己把它收進 `procs/done/`。

## 函式庫怎麼用

在 `aos-step` 跑的 form 裡，`aos/*`（函式庫的每個公開名字）、`here`、`pc` 已經綁好，直接用。
要在別的 Janet 程式裡用這個函式庫，Janet 的 `import` 吃不了絕對路徑，先把資料夾加進搜尋路徑：
`(array/push module/paths ["<proto4-4>/src/:all:.janet" :source])` 再 `(import aos :as aos)`；
或者在 proto4-4 目錄裡 `(import ./src/aos :as aos)`。

```janet
(aos/call "./tool")
(aos/call-json "./job.json" @{:timeout-ms 500})
(aos/call-dir "./child" @{:dir-target ".aos/other.json"})
```

- `call` 不判斷目標種類，普通檔案、`.json`、資料夾原樣交給 proto4-3 `aos-exec`。
- `call-dir` 先確認目標是資料夾，再叫它。
- `call-json` 先確認名字以 `.json` 結尾；檔案可以還沒出現。
- `exec-path` 回 aos-exec 的絕對路徑；環境變數 `AOS_EXEC` 可以覆蓋預設值。

三種 call 都回：

```janet
@{:code 0 :kind "child" :stderr ""}
```

`:kind` 是 `"child"`、`"aos"` 或 `"usage"`。`(aos/ok? r)` 只在 `kind` 是 `child` 且 `code` 是 0 時為真。
`:dir-target` 與 `:timeout-ms` 語意照舊；下面是這輪新增的選項。

### 接住三條流

```janet
(aos/call "./cat.sh" @{:stdin "hello\n"})                 # 字串或 buffer 餵給 stdin
(aos/call "./tool" @{:capture true})                      # stdout 變成結果的 :out
(aos/call-dir "./child" @{:read "./child/out.txt"})       # 跑完讀檔進 :out
(aos/call-dir "./child" @{:read-err "./child/err.txt"})   # 跑完讀檔進 :err
(aos/call "./json-tool" @{:capture true :json true})      # 解 :out，值放 :value

(def r (aos/pipe @["./echo.sh" ["./upper.sh" @{:timeout-ms 500}] "./count.sh"]
                 @{:json false}))
```

`:read` 與 `:capture` 同時給時是 `:read` 贏；檔不存在時 `:out` 是 nil。沒給
`:capture` 或 `:read` 時結果沒有 `:out`，所以取值也是 nil。`:json true` 的輸出是 nil 或空字串時
`:value` 是 nil；解出來的 key 是字串，要用 `(get v "count")` 取。解碼失敗不拋 error，而是
放 `:json-error`。`(aos/value r)` 有 `:value`
就回它，否則回 `:out`。

`pipe` 的每段是 target 字串或 `[target opts]`，回最後一段的結果，`:steps` 留全部結果。
只接受普通可執行檔；最外層 opts 的 `:json` 只對最後一段生效。

### 叫 LLM

```janet
(def r
  (aos/llm "endpoints.json#local"
           @{:messages [@{:role "user" :content "你好"}]}
           "result.json"
           @{:timeout-ms 60000}))
(aos/llm-text r) # 成功是文字，失敗是 nil
(get-in r [:value "text"])
```

`aos/llm` 用 spork 把請求寫到 `result.json.req.json` 留著對帳，再同步呼叫
`../proto4-5/aos-llm`，結果 table 仍有 `:code`、`:kind`、`:out`、`:value`；`:value`
是解好的結果 dict。endpoint 與其他相對路徑都以呼叫者 cwd 為中心，跟 `:read` 一樣。
環境變數 `AOS_LLM` 可覆蓋預設的 `aos-llm` 路徑。

這是同步的：那一格會等到回應回來，幾十秒也等；要不等就走排程層。`:timeout-ms` 是
整個 `aos-llm` 子行程的上限，交給 `aos/call` 處理。

## 狀態資料夾長什麼樣

`prog.janet` 旁邊會出現：

```text
.aos-step/
  pc        # 下一個 form 的 0-based 索引
  env.img   # Janet make-image 存下的環境
  src       # 上次成功那格的 form 數、程式 bytes／mtime 與內容 checksum
  error     # 上次失敗的 form、錯誤與 stacktrace；下次成功就刪
  done      # 全部完成後出現的空檔
```

每格都重新讀整支程式。環境裡每次都會重綁 `aos/*`、`here`（程式資料夾的絕對路徑）與 `pc`（這一格的索引）。`env.img`、`pc` 與 `src` 都先寫暫存檔再 rename，不會露出寫一半的檔案。

## 卡住了怎麼看

跑 `aos-step prog.janet --status`，`:error` 裡有錯誤與 stacktrace 全文；畫面上的失敗訊息只留
第一行。行程若跑在 kernel 上，用 `aos-exec 你的.json --stderr -` 直接看它為什麼起不來。

## 檔案

- `README.md`：本頁，解釋逐步程式、cpu 接法與限制。
- `project.janet`：Janet 專案資料與 spork 依賴。
- `aos-step`：可執行的薄 CLI。
- `src/aos.janet`：透過 proto4-3 `aos-exec` 叫目標、接流、讀檔、解 JSON、串接與同步叫 LLM。
- `src/step.janet`：切 form、eval、錯誤處理與 image 狀態持久化。
- `test/aos.janet`：函式庫、三種目標、逾時與錯誤分類測試。
- `test/step.janet`：每步真開新行程的持久化、重試、status 與 reset 測試。
- `test/cpu.janet`：真叫 `aos-run` 三格的整合測試。
- `test/fx/exit3.sh`：回 3 的普通檔案樣本。
- `test/fx/sleep.sh`：給 timeout 砍的慢程式樣本。
- `test/fx/step-prog.janet`：六個 form 的跨行程樣本，包含 call 結果持久化。
- `test/fx/cpu-prog.janet`：三個 form 的 cpu 樣本。
- `test/fx/*.sh`：退出碼、逾時、三條流、JSON 與三段串接樣本。
- `notes/`：留給後續任務書與實驗筆記。

## 沒做什麼

- 一個資料夾只有一份 `.aos-step/`，所以只能放一支這種程式；同資料夾兩支 `.janet` 會互相蓋狀態。
- `form N` 的 N 是 0 起算的頂層 form 序號，不是行號。程式跑一半後改過，
  `aos-step` 會警告 pc 可能錯位，但仍照跑；要對新程式從頭跑就 `--reset`。
- form 失敗會一直重試同一個，不會自動跳過。
- 放進 kernel 時，做完回 100 就會被收走；直接用 `aos-run` 跑時還是會一直來叫，只是每次都不做事並回 100。
- 函式庫不切 cwd；相對 target 永遠是相對於目前行程 cwd，不是 proto4 舊 `runf` 的切資料夾語意。
- `:read`／`:read-err` 的相對路徑也以呼叫者 cwd 為中心；inst 裡的流則是相對 inst 的 cwd，呼叫者要自己對上。
- `:capture` 對資料夾／`.json` inst 目標抓的是 aos-exec 自己的 stdout（通常為空）；inst 目標請用 `:read`。
- `pipe` 是一段跑完才開下一段的「串接」，不是同時執行的真 OS pipe，中間資料全部進記憶體。
- `kind` 是靠退出碼加 stderr 的 `aos-exec: ` 行猜的；子程式自己回 125 或 2 且印同樣開頭時無法分辨。
- image 存不進去的東西，例如還開著的檔案或 fiber，會讓這一格存檔失敗並留在原 pc。
- `aos-exec` 每次會截斷 inst.json 指定的 stdout/stderr 檔；要累積每格紀錄，請由 form 自己用 append 寫另一份 log。
- 沒有非同步 API、結果檔或投遞機制。
