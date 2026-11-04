# 任務書 2：proto4-4 函式庫「接住三條流」——把呼叫結果讀進 lisp、順路解 JSON、接 pipe

你在 repo `/home/lorkhan/repo/simple_tools/aos`。**只准修改 `proto4-4/` 底下的檔案**（主要是 `src/aos.janet`、`test/aos.janet`、`test/fx/`、`README.md`），其他路徑一律不碰。**不要 git commit、不要 push**。不要開其他 agent。

## 先讀

1. `proto4-4/README.md`、`proto4-4/src/aos.janet`、`proto4-4/test/aos.janet`（你上一輪做的；風格照舊）。
2. `proto4-3/README.md` 第 63–130 行（三種目標、inst.json 的 `stdin`／`stdout`／`stderr` 欄位語意：沒寫＝`/dev/null`、寫了＝檔案、`stdout` 每次建立並清空、普通檔案目標的三條流是**繼承** aos-exec 的）。
3. spork 的 JSON：`(import spork/json)`，`(json/decode s)`／`(json/encode v)`；參考 `~/repo/langs/janet-lab/snippets/json-and-marshal.janet`。子行程 pipe 參考 `~/repo/langs/janet-lab/snippets/pipe-to-child/`。

## 背景（使用者原話）

> lisp 呼叫檔案，以我們的 inst 作為呼叫慣例，所以照理來說會有 stdin/out/err 等東西，一開始最原始的版本就是都不接住，就跑完結束，後續可以幫忙接住，把檔案內容讀進 lisp，乃至於順路解析成 json 之類，還可以接上 pipe 等，快速弄。

第一版（你做的）＝都不接住。這一輪做「接住」的三小步。**規則不變：函式庫不解 inst.json、不切 cwd，一律叫 `proto4-3/aos-exec`。**

## 要加的東西（都是 `opts` 裡的新 key，舊用法一個字都不變、舊測試照樣要綠）

### A. 接住（capture）

- `:stdin`（字串或 buffer）：把它餵給子行程的標準輸入。做法：`os/spawn` 時 `:in :pipe`，寫進去、關掉。
- `:capture true`：把子行程的 stdout 接進來，結果 table 多 `:out`（字串）。**stderr 那條本來就接著**（判 kind 用的），照舊放 `:stderr`。
- 這兩個對**普通檔案目標**才真的有用（它的三條流是繼承的）。對 `.json`／資料夾目標，子行程的流照 inst.json 走，`:capture` 抓到的是 aos-exec 自己的 stdout（通常空）——**照實回，不報錯**，README 寫清楚「inst 目標請用 B」。

### B. 讀檔（read）

- `:read PATH`：跑完之後把 `PATH` 這個檔讀進來放 `:out`。PATH 相對路徑以**呼叫者的 cwd**為中心（函式庫不切 cwd，這是唯一說得通的中心）；呼叫者要自己跟 inst.json 的 `stdout` 對上（inst 那邊是相對 inst 的 cwd）。檔不存在＝`:out nil`，不報錯。
- `:read-err PATH`：同上，讀進 `:err`。
- `:capture` 與 `:read` 同時給時 `:read` 贏（後者是 inst 目標的正途）。

### C. 解 JSON

- `:json true`：把 `:out` 用 `json/decode` 解成 Janet 值放 `:value`。`:out` 是 nil 或空字串＝`:value nil`；解失敗＝**不丟 error**，`:value nil`、多一個 `:json-error "訊息"`。
- 加一個小幫手 `(aos/value r)`：有 `:value` 回 `:value`，不然回 `:out`。

### D. pipe（只給普通檔案目標）

- `(aos/pipe targets &opt opts)`：`targets` 是一個陣列，每個元素是 `target` 字串或 `[target opts]`；把前一個的 stdout 接成後一個的 stdin，**全部都是普通可執行檔才行**（`.json`／資料夾目標會讓這條鏈斷掉，所以遇到就 `error`，訊息說明原因）。最簡做法：一個接一個跑、把前一個的 `:out` 當後一個的 `:stdin`（不用真的開 OS pipe 同時跑，這版先串接）。回最後一個的結果 table，另外多 `:steps`（每一段的結果陣列）。`opts` 裡的 `:json` 只對最後一段生效。
- README 明講：這是「串接」不是真 pipe（前一個跑完才開後一個），資料全進記憶體。

### E. `aos-step` 那邊順手一件

form 裡呼叫 `(aos/call …)` 回來的 table 會留在環境裡；`make-image` 存不了什麼奇怪的東西才對（都是字串／數字／table），但你要**實測**一次：`test/step.janet` 加 2 條——某個 form `(def r (aos/call-dir (string here "/child") {:read (string here "/child/out.txt") :json true}))`，下一個 form 用 `(get r :value)`，兩格是兩個進程，值要正確。child 的 inst.json 讓 stdout 寫一份 JSON 到 `out.txt`。

## 測試（`test/aos.janet` 至少再加 12 條，全部照 `check` 風格）

- `:stdin` 餵給 `cat` 之類的腳本（自己放 `test/fx/cat.sh`），`:capture true` 拿回同樣內容。
- `:capture` 拿到多行輸出；沒給 `:capture` 時結果沒有 `:out`（或是 nil，選一種寫在 README）。
- `:read` 對 inst 目標：inst.json 寫 `stdout` 到 `out.txt`，`:read` 那個檔拿到內容；檔不存在 `:out nil`。
- `:read-err`。
- `:json true` 解 `{"a":1,"b":[1,2]}` → `(get-in r [:value "b" 1])` 是 2；壞 JSON → `:value nil` 且有 `:json-error`；空輸出 → `:value nil` 沒有 `:json-error`。
- `aos/value` 兩種情況。
- `aos/pipe` 三段：`echo`→`tr`→`wc -l` 那類（腳本自己放 fx），`:steps` 長度 3、最後 `:out` 對；鏈裡放一個資料夾目標會 `error`。
- 舊的 15 條一條都不能壞。

全部要綠：
```
cd /home/lorkhan/repo/simple_tools/aos/proto4-4 && for t in test/*.janet; do janet "$t" || echo "FAIL $t"; done
```

## README

「函式庫怎麼用」那節加一小節「接住三條流」：四個 opts 各一行例子、`pipe` 一個例子、「沒做什麼」補：pipe 是串接不是真 pipe、`:capture` 對 inst 目標抓的是 aos-exec 自己的流、`:read` 的相對路徑中心是呼叫者的 cwd。控制在 README 總長 170 行以內。

## 回報（十行以內，大白話）

- 改了哪些檔。
- 三支測試各幾條、最後一行原文。
- 自己決定的事、撞到的坑，一條一句。
- 沒做到的。
