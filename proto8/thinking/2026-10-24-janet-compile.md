# 2026-10-24 Janet 編成 aos（嘗試）

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)｜程式 [proto8/langs/janet](../extras/langs/janet/README.md)｜測試 `proto8/tests/test_janet.py`

## 使用者原文（10-24，逐字）

- 前文：「然後我這邊有不少想法，都麻煩你試着去思考去實作。我隨便說，你隨便做，反正只是嘗試」「我現在沒空管這些小事，都按建議做」
- 本題：「再來是lisp/lua編譯成我們這套的方式。去看看~/repo/langs/janet-lab，我想試試看janet編譯成這套。但其實lua也不錯，可以的話接入nvim也挺好，可以去看看~/notes」（lua＋nvim 那半另一個 agent 做；這份只記 Janet）
- 這題的根是 10-19 的 C-43：「意思是我們要做這樣一套程式，要一個一個mkdir, vim修改檔案，等於是一個元素一個元素去堆疊出一個table，那不如直接用lua/lisp生成這麼一套資料夾佈局」（[ideas § 12](2026-10-19-ideas.md)）。

## 決定（照推薦定、可翻案；使用者 10-24「都按建議做」）

1. **編譯＝在 Janet 裡把整套資料夾描述成一個值，再寫到磁碟**：原始檔是普通 Janet，最後 `(def program (dir …))`；`aos-janet [--force] 原始檔.janet 輸出資料夾` 把它寫出來。Janet 的函數就是範本（`agent` 是一個普通函數，回一個資料夾）；巨集只用在要把名字當字面的地方（`aos-fsm` 的狀態名、`janet-main` 的程式碼）。編譯器直接用 Janet 寫（`~/.local` 已裝 Janet、jpm）；janet-lab 裡上一代的 `modules/aos/` 綁定跟 proto8 對不上，不用。
2. **輸出就是手寫會寫的那套**（資料夾、JSON、短腳本），可以直接看、手改、`aos-exec`；不另加標記檔或中間格式。JSON 中文不跳脫、短的擠一行（100 位元組）、key 有固定順序（`obj` 照寫的順序；一般 struct 照 `_entry`、`argv`…、`exec`、`max`、`start`、`states`、`next`… 再照字母）。
3. **key 照字面**（`:timeout_ms` 就是 `timeout_ms`，不偷偷把 `-` 換 `_`；C-56 寫什麼就做什麼）。Janet 的 table 存不了 nil，所以 `obj` 裡值 `nil`＝不寫那個 key，要 JSON 的 null 寫 `null`。
4. **長大成資料夾**（接 C-55）：JSON 裡某格寫成 `(dir …)`，就長成同一層的子資料夾，那格換成它的名字（名字取那格的 key；key 是 `exec` 取上一層，所以 fsm 的 `idle` 格→`idle/`）。單子留在原地（內嵌）。
5. **組合子 seq／par／if 編成 shell 入口**：每個是一個資料夾，`_entry` 是幾行 shell，每一步 `aos-exec` 一次、各給一個小格 `$AOS_STACK/<步名>`（P-17）；單子放 `steps.json`、資料夾長成 `s1/`、`p1/`、`cond/`…。seq 哪步非 0 就以它的碼結束；par 全部等完、有非 0 就以最後等到的非 0 碼結束；if 是 cond 0 跑 then、非 0 跑 else（沒 else＝0）。
6. **入口能不用 sh 就不用**（少用 sh）：agent 的 `_entry` 寫成 argv 陣列 `["aos-loop", "loop.json"]`（C-73 第三種），跟 `exec aos-loop loop.json` 的 sh 跑起來一樣。
7. **葉子**：Python 等別的語言的葉子用 `(copy 路徑)` 照抄；Janet 寫的葉子用 `(janet-main [_ & args] …)` 生成 `#!/usr/bin/env janet` 的可執行檔（自己印原始碼，中文不變成 `\xE5…`）。
8. **`_metainfo`**：不做特別的東西。`(obj … "_metainfo" {…})` 照寫就在（C-48 不認得的 key 忽略）；資料夾層級的 metainfo 等那邊規劃好再接（一個 dir 裡多放一個檔就行）。
9. 名字（C-54）：程式放 `proto8/langs/janet/`、命令列 `aos-janet`；組合子叫 `aos-seq`／`aos-par`／`aos-if`、loop／fsm 叫 `aos-loop`／`aos-fsm`（跟指令同名，也避開 Janet 內建的 `loop`、`seq`、`if`）。錯誤一行「aos-janet: 代號 原因」、退 1（P-21）。

寫法與編出來的 JSON 一對一對照在 [langs/janet README](../extras/langs/janet/README.md#寫法--編出來的東西)。寫 Janet import 時：相對路徑相對寫 import 的那支檔、不要寫 `.janet`。

## 已知限制（還沒問使用者）

- **重編會蓋掉手改**：`--force` 只蓋這次要寫的檔、不刪別的；手改過的檔會被蓋回去，Janet 裡拿掉的檔會留在輸出裡（舊檔殘留）。
- **編到一半出錯會留半份**：例如長子資料夾撞名（`NameTaken`）時，前面的檔已經寫了。
- **長出的子資料夾用相對名字**：fsm 的字串目標從 cwd 算（N-36）；JSON 檔放在子資料夾、但從別處跑 fsm 時，長出來的名字會對不上。慣例下（入口、fsm.json 同一層）沒事。
- **編出來的東西預設 `AOS_ENTRY` 是 `_entry`**：外面把 `AOS_ENTRY` 改掉，長出來的子資料夾、組合子的步就找不到入口。
- **組合子的 shell**：par 不轉訊號（父 shell 被殺，背景的步可能留著，靠 aos-exec 打整群才收得掉）；if 分不出「條件為假」和「條件那步壞掉」（都是非 0）；步數多時每一步多起一個 aos-exec。
- **`copy` 在編的時候讀**：被抄的檔之後改了，要重編才會跟上；抄的是內容不是連結。
- **Janet 數字是浮點**：超過 2^53 的整數會失準；`janet-main` 印回原始碼時長字串（反引號）會變成一般字串、註解不留。
- `.env` 的值只收不用引號的（有空白、`#`、引號、`$`＝`ValueBad`）。

## 未決（選項，沒做）

- **反編譯（JSON → Janet）**：甲、逐檔照抄成 `(dir "fsm.json" {…})`（簡單、但看不出 fsm 結構）；乙、認得 loop／fsm／單子／指示詞的形狀就還原成 `aos-loop`／`aos-fsm`／`inst`／`env`（好讀、要維護一張形狀表）；丙、只做「看得懂的 diff」（編一次跟磁碟上的比，告訴你手改了哪裡），不還原。頂層傾向丙先、乙後。
- **組合子要不要改用 fsm 表達**：seq 可以是一串格接到一個退 10 的 `done` 格；但 fsm 的 state 留在 stack，做完一次再跑會停在 done（要換小格或清 state）。
- **單子太大要不要自動長成檔**（C-55「檔太大就長成資料夾」那條的 JSON 版）：現在一律留在原地，要長就自己寫 `(dir …)`。
- 要不要做成 jpm 套件、放進 janet-lab（那邊是獨立 repo）。
