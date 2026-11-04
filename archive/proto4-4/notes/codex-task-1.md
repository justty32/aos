# 任務書：proto4-4 — 逐步 lisp（Janet）：第一個跑在 cpu 上的程式

你在 repo `/home/lorkhan/repo/simple_tools/aos`。**只准新增／修改 `proto4-4/` 底下的檔案**，其他任何路徑都不要碰（包括 `proto4-3/`、`proto4/`、`wf/`）。**不要 git commit、不要 git push**，做完回報就好。不要開其他 agent。

## 先讀什麼（十分鐘內讀完，不要全 repo 亂逛）

1. `proto4-3/README.md` 第 1–330 行：aos-exec 的三種目標、inst.json 七欄、退出碼（125＝aos-exec 自己失敗、2＝用法錯、其餘原樣是子程式的碼）、aos-run 的旗標（`--interval-ms`／`--max-runs`／`--status-fd`）。你要**呼叫**這些程式，不是重做它們。
2. `proto4/README.md` 前 30 行與 `proto4/test/runf.janet` 前 20 行：Janet 專案的擺法與測試寫法（`check` 巨集、數第幾條、跑法 `janet test/xxx.janet`）。照這個風格。
3. Janet 語言參考（有需要再翻）：`~/repo/langs/janet-lab/docs/16-marshal-與自省.md`（`make-image`／`load-image`）、`~/repo/langs/janet-lab/docs/05e-import-與模組路徑.md`、`~/repo/langs/janet-lab/snippets/pipe-to-child/`（開子行程）。`janet` 在 `~/.local/bin/janet`，版本 1.41.2；spork 已裝。

## 要做出什麼

一句話：**一個 `.janet` 檔就是一個行程；cpu 每跑它一次，它就執行檔案裡「下一個」頂層 form（一個 list），把環境存起來，等下一次。** 這就是使用者說的「逐步 lisp」——inst 的行為是「逐一執行指定 .janet 檔案中的每個 list」。另外要一個 Janet 函式庫，把「檔案呼叫、資料夾呼叫」包起來，**完全遵循 proto4-3 的 inst 規則**（做法是叫 `proto4-3/aos-exec`，不自己解 inst.json）。

### 檔案配置

```
proto4-4/
  README.md              大白話說明（下面有規定要寫什麼）
  project.janet          照 proto4/project.janet 的樣子（name "aos-proto4-4"）
  aos-step               可執行檔，#!/usr/bin/env janet，薄薄一層，真東西在 src/step.janet
  src/aos.janet          函式庫：檔案／資料夾呼叫
  src/step.janet         逐步執行器本體
  test/aos.janet         函式庫的測試
  test/step.janet        逐步執行器的測試（真的開子行程跑 aos-step）
  test/cpu.janet         放到 cpu 上跑（真的叫 proto4-3/aos-run）
  test/fx/…              測試用樣本
  notes/                 空著也行（我之後放任務書副本）
```

### `src/aos.janet`：檔案／資料夾呼叫（遵循 inst）

- `(aos/exec-path)`：aos-exec 在哪。先看環境變數 `AOS_EXEC`，沒有就用 `<這個檔案所在資料夾>/../../proto4-3/aos-exec` 算出來的**絕對路徑**（用 `(dyn :current-file)` 在載入時算好、`os/realpath`）。找不到就 `error`。
- `(aos/call target &opt opts)`：**三種目標原封不動交給 aos-exec 判斷**（普通檔案／`.json`／資料夾），`opts` 是 table，認 `:dir-target`（字串）、`:timeout-ms`（整數），對應 aos-exec 的 `--dir-target`／`--timeout-ms`。用 `os/spawn` 開 `[aos-exec target …旗標]`，**把 aos-exec 自己的 stderr 用 pipe 接起來**、stdin／stdout 繼承。回一個 table：`@{:code 退出碼 :kind "child"|"aos"|"usage" :stderr "aos-exec 印的東西"}`。
  - `kind` 怎麼判：退出碼 125 而且 stderr 有一行以 `aos-exec: ` 開頭 → `"aos"`；退出碼 2 而且有那種行 → `"usage"`；其他一律 `"child"`。（子程式自己回 125 或 2 時分不出來的機率很小，README 的「沒做什麼」要寫一條。）
  - 相對路徑的 `target` 就是相對於**目前行程的 cwd**，函式庫不切目錄、不動 cwd（這跟 proto4 舊版 `runf` 會切目錄不一樣，README 要講）。
- `(aos/call-dir dir &opt opts)`：**資料夾呼叫**。先確認 `dir` 真的是資料夾（不是就 `error`），再 `call`。`:dir-target` 照傳。
- `(aos/call-json path &opt opts)`：確認以 `.json` 結尾（不用存在，aos-exec 收不存在的 .json），再 `call`。
- `(aos/ok? r)`：`kind` 是 `"child"` 而且 `code` 是 0。
- 不要做別的（不做非同步、不做結果檔、不做投遞）。

### `src/step.janet` ＋ `aos-step`：逐步執行器

命令列：

```
aos-step PROG.janet            跑「下一個」form，一次一個
aos-step PROG.janet --status   印一行狀態（JDN／`%q`）：{:pc N :n 總數 :done true/false :error "…"或nil}
aos-step PROG.janet --reset    把狀態資料夾整個刪掉，從頭來
```

退出碼：0＝這一步成功（或已經全部做完、這次什麼都沒做）；1＝這個 form 執行失敗；2＝用法錯（沒給檔、檔不存在、旗標不認得）。

- **狀態放在 PROG 所在資料夾的 `.aos-step/`**（一個資料夾一個程式；同資料夾放兩支 .janet 會互相蓋，README「沒做什麼」寫一條）：
  - `pc`：十進位整數＋換行，下一個要跑的 form 的索引（從 0 起）。沒有這個檔＝0。
  - `env.img`：`make-image` 出來的環境（bytes）。沒有＝第一次，用 `(make-env)` 開新的。
  - `error`：上一次失敗的紀錄（第幾個 form、錯誤訊息、stacktrace 文字）；成功一次就刪掉。
  - `done`：空檔，所有 form 都跑完時建立。
- **一次呼叫做的事（順序固定）**：
  1. 讀 PROG 整份，用 `parser/new`＋`parser/consume`＋`parser/eof`＋`parser/produce` 切成頂層 form 陣列。**每次都重新切**（檔案可能被改），parse 失敗＝當成這一步失敗（寫 `error`、退出 1、pc 不動）。
  2. 讀 `pc`。若 `pc >= form 數`：確保 `done` 存在、退出 0、不印東西。
  3. 準備環境：有 `env.img` 就 `load-image`，沒有就 `(make-env)`。**每次**都把函式庫綁進去（在環境裡 eval `(import <src/aos.janet 的絕對路徑> :as aos)`，或等價做法），並綁 `here`＝PROG 所在資料夾的絕對路徑、`pc`＝現在這個索引。這樣 form 裡可以直接寫 `(aos/call-dir "./xxx")`、`(spit (string here "/x.txt") …)`。
  4. 在一個 fiber 裡 `eval` 第 `pc` 個 form，接住錯誤。
  5. 成功：先把新環境 `make-image` 寫到 `env.img`、再寫 `pc+1`（兩個都用「寫暫存檔再 `os/rename`」，不能寫一半被看見）；刪掉 `error`（若有）；如果 `pc+1 == form 數` 就建 `done`；把 form 的回傳值用 `(printf "%q" v)` 印一行到 stdout；退出 0。
  6. 失敗：寫 `error`（含第幾個 form、`(describe err)`、stacktrace），`env.img` 與 `pc` **都不動**（下一次會再試同一個 form），印一行 `aos-step: form N 失敗：…` 到 stderr，退出 1。
- **image 裡有函式沒問題**（`make-image` 會用 `make-image-dict` 把核心的東西用名字記，自訂的 `defn` 會整個包進去）。若你發現 import 進來的函式庫在 image 裡存不好，改成「image 裡不存函式庫、每次重新 import 綁上去」也可以，但**使用者自己 `def`／`defn` 的東西一定要跨進程存活**——這是整件事的重點。
- 放到 cpu 上跑的 inst.json 長這樣（測試與 README 都用這個形狀）：
  ```json
  {"argv": ["/abs/proto4-4/aos-step", "prog.janet"], "cwd": "/abs/那個資料夾", "stdout": "out.txt", "stderr": "err.txt"}
  ```
  `argv[0]` 一律寫絕對路徑（跟 proto4-3 kernel 的決定一樣，不靠 PATH）。`aos-step` 自己的 shebang 是 `#!/usr/bin/env janet`，所以跑它的人 PATH 裡要有 `janet`（`~/.local/bin`），README 要提。

### 測試（Janet，照 proto4 的 `check` 巨集風格；每支最後印「N 條通過 ✓」；跑法 `janet test/xxx.janet`，在哪個目錄跑都要對）

暫存都開在 `/tmp` 底下自己的資料夾（用 pid 或 `os/time` 命名），跑完刪掉。

1. `test/aos.janet`（至少 8 條）：
   - `call-dir` 一個樣本資料夾（裡面 `.aos/inst.json` 寫一個檔出來）：`kind` 是 `child`、`code` 0、那個檔真的出現。
   - `call-dir` 加 `:dir-target` 指另一份。
   - `call-json` 直接指一份 inst.json。
   - `call` 普通可執行檔（例如一支 sh 腳本回 3）：`code` 3、`kind` `child`。
   - 不存在的 `.json`：`code` 125、`kind` `aos`。
   - 不存在的普通路徑：`code` 2、`kind` `usage`。
   - `:timeout-ms` 讓一支 `sleep 5` 被砍：`code` 143 或 137、`kind` `child`。
   - `call-dir` 給一個不是資料夾的東西會 `error`；`ok?` 對上面幾個結果的真假。
2. `test/step.janet`（至少 12 條）：**每一步都用 `os/execute` 另開一個 `aos-step` 進程**，不能在同一個進程裡連跑（重點是跨進程存活）。
   - 樣本 prog 四個 form：`(def x 10)`、`(defn f [a] (* a x))`、`(spit (string here "/side.txt") (string (f 2)))`、`(aos/call-dir (string here "/child"))`（child 資料夾的 inst.json 寫一個 `child-ran.txt`）。
   - 跑第 1 次：退出 0、`pc`＝1、stdout 印了一行；第 2 次：pc 2；第 3 次：`side.txt` 內容 `20`（證明 `x` 與 `f` 跨進程活著）；第 4 次：`child-ran.txt` 出現；第 5 次：退出 0、`done` 存在、stdout 空。
   - `--status` 每個階段回的 `:pc`／`:n`／`:done` 對。
   - 錯誤 prog：第 2 個 form `(error "boom")`：第 2 次跑退出 1、`pc` 還是 1、`error` 檔有 `boom`；把檔案改成好的（覆寫 prog）再跑一次：退出 0、`pc` 2、`error` 消失。
   - parse 壞掉的 prog（少括號）：退出 1、`pc` 不動。
   - `--reset` 後 `--status` 回 `:pc 0`。
   - 用法錯（沒給檔／檔不存在）退出 2。
3. `test/cpu.janet`（至少 3 條）：做一個行程資料夾（prog 三個 form，各 `spit` 一行進 `log.txt` 用 append），寫上面形狀的 inst.json，**真的叫** `proto4-3/aos-run <inst.json> --interval-ms 100 --max-runs 3`（`os/execute`，等它結束），然後檢查：`pc`＝3、`done` 存在、`log.txt` 三行、`out.txt` 三行。這證明「cpu 一格＝一個 form」。

全部要綠：
```
cd /home/lorkhan/repo/simple_tools/aos/proto4-4 && for t in test/*.janet; do janet "$t" || echo "FAIL $t"; done
```
順便確認 `proto4-3` 的測試沒被你弄壞（你不該碰它，跑一次確認就好）：`cd ../proto4-3 && python3 -m unittest discover -s test 2>&1 | tail -3`（約 30 秒，185 條）。

### README.md（大白話，繁體中文，200 行以內）

開頭一行 `← [proto4-3](../proto4-3/README.md)（作業系統那層：aos-exec／aos-run／aos-daemon／aos-kernel）`。段落：**是什麼**（一句話＋使用者那句「逐一執行指定 .janet 檔案中的每個 list」）、**怎麼跑**（手動跑五次看 pc 走、放到 cpu 上用 aos-run、放進 kernel 的 `procs/` 的 inst.json 形狀）、**函式庫怎麼用**（三個 call 與回傳 table）、**狀態資料夾長什麼樣**、**檔案**（每個檔一行）、**沒做什麼**（至少：一個資料夾只能一支程式；按索引數 form、改了前面的 form 會錯位；失敗會一直重試同一個 form、不會往前跳；做完後 cpu 還是會一直來叫、只是什麼都不做，因為 kernel v1 沒有「行程結束」機制；函式庫不切 cwd；kind 靠退出碼＋stderr 猜；image 裡放不進去的東西（開著的檔案、fiber）會讓存檔失敗）。

## 回報格式（十五行以內，大白話）

- 做了哪些檔（一行一個）。
- 三支測試各幾條、全綠與否（貼最後一行）；proto4-3 那 185 條還綠嗎。
- 你自己決定的事（任務書沒寫、你補的），一條一句。
- 撞到的坑，一條一句。
- 沒做到的，說清楚哪一條、為什麼。
