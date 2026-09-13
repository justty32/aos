← [proto4-3](../proto4-3/README.md)（作業系統那層：aos-exec／aos-run／aos-daemon／aos-kernel）

# proto4-4 — 逐步 lisp（Janet）

## 是什麼

一個 `.janet` 檔就是一個行程；cpu 每叫它一次，它只跑下一個頂層 form，再把環境收好等下一格。

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
/abs/proto4-4/aos-step prog.janet       # 全做完了：成功，但什麼都不做
/abs/proto4-4/aos-step prog.janet --status
```

`--status` 只印一行 JDN：

```janet
{:pc 4 :n 4 :done true :error nil}
```

要從頭來：

```sh
/abs/proto4-4/aos-step prog.janet --reset
```

放到 cpu 上，先在行程資料夾寫 `inst.json`：

```json
{"argv": ["/abs/proto4-4/aos-step", "prog.janet"], "cwd": "/abs/那個資料夾", "stdout": "out.txt", "stderr": "err.txt"}
```

`argv[0]` 刻意用絕對路徑，不靠 PATH 找 `aos-step`；但它的 `#!/usr/bin/env janet` 仍需要執行時的 PATH 裡有 `janet`（這裡是 `~/.local/bin/janet`）。

```sh
/abs/proto4-3/aos-run /abs/行程/inst.json --interval-ms 100 --max-runs 5
```

一次 run 就是一格，一格只跑一個 form。要讓 kernel 排它，放進 kernel `procs/` 的也是同一形狀的 inst.json：

```json
{"argv": ["/abs/proto4-4/aos-step", "prog.janet"], "cwd": "/abs/那個資料夾", "stdout": "out.txt", "stderr": "err.txt"}
```

## 函式庫怎麼用

```janet
(import ./src/aos :as aos)

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

`:kind` 是 `"child"`、`"aos"` 或 `"usage"`。`(aos/ok? r)` 只在 `kind` 是 `child` 且 `code` 是 0 時為真。選項只有 `:dir-target` 與 `:timeout-ms`。

## 狀態資料夾長什麼樣

`prog.janet` 旁邊會出現：

```text
.aos-step/
  pc        # 下一個 form 的 0-based 索引
  env.img   # Janet make-image 存下的環境
  error     # 上次失敗的 form、錯誤與 stacktrace；下次成功就刪
  done      # 全部完成後出現的空檔
```

每格都重新讀整支程式。環境裡每次都會重綁 `aos/*`、`here`（程式資料夾的絕對路徑）與 `pc`（這一格的索引）。`env.img` 與 `pc` 都先寫暫存檔再 rename，不會露出寫一半的檔案。

## 檔案

- `README.md`：本頁，解釋逐步程式、cpu 接法與限制。
- `project.janet`：Janet 專案資料與 spork 依賴。
- `aos-step`：可執行的薄 CLI。
- `src/aos.janet`：透過 proto4-3 `aos-exec` 叫檔案、JSON 或資料夾。
- `src/step.janet`：切 form、eval、錯誤處理與 image 狀態持久化。
- `test/aos.janet`：函式庫、三種目標、逾時與錯誤分類測試。
- `test/step.janet`：每步真開新行程的持久化、重試、status 與 reset 測試。
- `test/cpu.janet`：真叫 `aos-run` 三格的整合測試。
- `test/fx/exit3.sh`：回 3 的普通檔案樣本。
- `test/fx/sleep.sh`：給 timeout 砍的慢程式樣本。
- `test/fx/step-prog.janet`：四個 form 的跨行程樣本。
- `test/fx/cpu-prog.janet`：三個 form 的 cpu 樣本。
- `notes/`：留給後續任務書與實驗筆記。

## 沒做什麼

- 一個資料夾只有一份 `.aos-step/`，所以只能放一支這種程式；同資料夾兩支 `.janet` 會互相蓋狀態。
- pc 數的是頂層 form 索引；程式跑一半後改掉前面的 form，之後就會錯位。
- form 失敗會一直重試同一個，不會自動跳過。
- 做完後 cpu 還是會一直來叫；`aos-step` 只會什麼都不做地回 0，因為 kernel v1 還沒有「行程結束」機制。
- 函式庫不切 cwd；相對 target 永遠是相對於目前行程 cwd，不是 proto4 舊 `runf` 的切資料夾語意。
- `kind` 是靠退出碼加 stderr 的 `aos-exec: ` 行猜的；子程式自己回 125 或 2 且印同樣開頭時無法分辨。
- image 存不進去的東西，例如還開著的檔案或 fiber，會讓這一格存檔失敗並留在原 pc。
- `aos-exec` 每次會截斷 inst.json 指定的 stdout/stderr 檔；要累積每格紀錄，請由 form 自己用 append 寫另一份 log。
- 沒有非同步 API、結果檔或投遞機制。
