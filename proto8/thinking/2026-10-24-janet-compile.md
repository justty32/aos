# 2026-10-24 Janet 編成 aos（嘗試）

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)｜程式 [proto8/langs/janet](../extras/langs/janet/README.md)｜測試 `proto8/tests/test_janet.py`

## 使用者原文（10-24，逐字）

- 前文：「然後我這邊有不少想法，都麻煩你試着去思考去實作。我隨便說，你隨便做，反正只是嘗試」「我現在沒空管這些小事，都按建議做」
- 本題：「再來是lisp/lua編譯成我們這套的方式。去看看~/repo/langs/janet-lab，我想試試看janet編譯成這套。但其實lua也不錯，可以的話接入nvim也挺好，可以去看看~/notes」（lua＋nvim 那半另一個 agent 做；這份只記 Janet）
- 這題的根是 10-19 的 C-43：「意思是我們要做這樣一套程式，要一個一個mkdir, vim修改檔案，等於是一個元素一個元素去堆疊出一個table，那不如直接用lua/lisp生成這麼一套資料夾佈局」（[ideas § 12](2026-10-19-ideas.md)）。

## janet-lab 與 notes 裡有什麼（唯讀看過）

- Janet 1.41.2、jpm、spork、janet-lsp 都已裝在 `~/.local`（原始碼編譯、沒用 sudo）。所以編譯器直接用 Janet 寫，不用另外建置。
- `janet-lab/modules/aos/`（9 月 AI 寫的）是**上一代**的綁定：認 `.aos/` 的「地」、shell 出去叫 `proto/aos.py`、`AOS_HOME` 登記表——跟 proto8（資料夾＝程式、`_entry`、六個環境變數、`aos-exec`）對不上，沒拿來用。
- janet-lab 另有 llm-http、agent（Janet 寫的 agent loop）、pi-shell 三個模組與一整套中文教學；import 的坑（相對路徑相對寫 import 的那支檔、不要寫 `.janet`）照它的筆記避開。
- `~/notes` 跟 Janet 有關的只有 nvim 的 janet-lsp 修補（開檔分析時會執行 `def` 初始化式，已修）；沒找到 Janet 編 aos 的既有想法。

## 決定（照推薦定、可翻案；使用者 10-24「都按建議做」）

1. **編譯＝在 Janet 裡把整套資料夾描述成一個值，再寫到磁碟**：原始檔是普通 Janet，最後 `(def program (dir …))`；`aos-janet [--force] 原始檔.janet 輸出資料夾` 把它寫出來。Janet 的函數就是範本（`agent` 是一個普通函數，回一個資料夾）；巨集只用在要把名字當字面的地方（`aos-fsm` 的狀態名、`janet-main` 的程式碼）。
2. **輸出就是手寫會寫的那套**（資料夾、JSON、短腳本），可以直接看、手改、`aos-exec`；不另加標記檔或中間格式。JSON 中文不跳脫、短的擠一行（100 位元組）、key 有固定順序（`obj` 照寫的順序；一般 struct 照 `_entry`、`argv`…、`exec`、`max`、`start`、`states`、`next`… 再照字母）。
3. **key 照字面**（`:timeout_ms` 就是 `timeout_ms`，不偷偷把 `-` 換 `_`；C-56 寫什麼就做什麼）。Janet 的 table 存不了 nil，所以 `obj` 裡值 `nil`＝不寫那個 key，要 JSON 的 null 寫 `null`。
4. **長大成資料夾**（接 C-55）：JSON 裡某格寫成 `(dir …)`，就長成同一層的子資料夾，那格換成它的名字（名字取那格的 key；key 是 `exec` 取上一層，所以 fsm 的 `idle` 格→`idle/`）。單子留在原地（內嵌，10-24 exec 可放單子）。
5. **組合子 seq／par／if 編成 shell 入口**：每個是一個資料夾，`_entry` 是幾行 shell，每一步 `aos-exec` 一次、各給一個小格 `$AOS_STACK/<步名>`（P-17）；單子放 `steps.json`、資料夾長成 `s1/`、`p1/`、`cond/`…。seq 哪步非 0 就以它的碼結束；par 全部等完、有非 0 就以最後等到的非 0 碼結束；if 是 cond 0 跑 then、非 0 跑 else（沒 else＝0）。用 shell 是因為「依序／同時／看結束碼」shell 本來就會，fsm 版留作選項（見未決）。
6. **入口能不用 sh 就不用**（少用 sh）：agent 的 `_entry` 寫成 argv 陣列 `["aos-loop", "loop.json"]`（C-73 第三種），手寫版是 `exec aos-loop loop.json` 的 sh；兩者跑起來一樣。
7. **葉子**：Python 等別的語言的葉子用 `(copy 路徑)` 照抄；Janet 寫的葉子用 `(janet-main [_ & args] …)` 生成 `#!/usr/bin/env janet` 的可執行檔（自己印原始碼，中文不變成 `\xE5…`）。
8. **`_metainfo`**：不做特別的東西。JSON 物件本來就能多放 key（C-48 不認得的 key 忽略），`(obj … "_metainfo" {…})` 照寫就在；資料夾層級的 metainfo 等那邊規劃好再接（一個 dir 裡多放一個檔就行）。
9. 名字（C-54）：程式放 `proto8/langs/janet/`、命令列 `aos-janet`；組合子叫 `aos-seq`／`aos-par`／`aos-if`、loop／fsm 叫 `aos-loop`／`aos-fsm`（跟指令同名，也避開 Janet 內建的 `loop`、`seq`、`if`）。錯誤一行「aos-janet: 代號 原因」、退 1（P-21）。

## 對照表：Janet 寫法 ↔ 編出來的 JSON

```janet
(aos-fsm :entry (self-entry "aos-fsm")
  (idle  (dir "_entry" (sh "…"))                         -> think)
  (think (inst ["python3" "brain.py"] :timeout_ms 120000) -> act)
  (act   (inst ["python3" "act.py"] :timeout_ms 60000)    -> idle))
```

```json
{
  "_entry": ["aos-fsm", {"$env": "AOS_CF"}],
  "start": "idle",
  "states": {
    "idle": {"exec": "idle", "next": "think"},
    "think": {"exec": {"argv": ["python3", "brain.py"], "timeout_ms": 120000}, "next": "act"},
    "act": {"exec": {"argv": ["python3", "act.py"], "timeout_ms": 60000}, "next": "idle"}
  }
}
```
（外加子資料夾 `idle/_entry`。）其他一對一的對照在 [langs/janet README](../extras/langs/janet/README.md#寫法--編出來的東西)。

## 實跑結果（10-24）

- `examples/agent_dan.janet` 編出來：檔一樣多（12 個）；`fsm.json`、`loop.json`、兩份 `tool.json` 的 JSON 內容跟手寫的 [demo/agent-dan](../demo/README.md) 相同；brain.py、act.py、system.txt、math 位元組相同；`_entry`、`.env`、`idle/_entry`、`clock/_entry` 只差寫法與註解。假腦（叫 clock 再答）兩版跑：工作區的檔、history、答案、走過的格、最後的 state 都一樣（只有 clock 的時間差一秒）。LiteLLM 沒開，沒接真腦。
- `count.janet`（loop＋fsm，葉子是 Janet）：tick 數到 3、第 4 次退 10，loop 以 0 結束、印三次 tock。
- `steps.janet`：seq→par→if，沒有 flag 走 else、放了 flag 走 then；每一步的小格都開了。
- 試驗場 `~/code/try/janet-aos/`：三個例子編出來的資料夾與跑過的工作區（`ws-dan`、`ws-count`、`ws-steps`）。
- 測試 `proto8/tests/test_janet.py` 6 個（沒裝 janet 就 skip）。

## 挖出的邊緣狀況（還沒問使用者）

- **重編會蓋掉手改**：`--force` 只蓋這次要寫的檔、不刪別的；手改過的檔會被蓋回去，Janet 裡拿掉的檔會留在輸出裡（舊檔殘留）。
- **編到一半出錯會留半份**：例如長子資料夾撞名（`NameTaken`）時，前面的檔已經寫了。
- **長出的子資料夾用相對名字**：fsm 的字串目標從 cwd 算（N-36）；JSON 檔放在子資料夾、但從別處跑 fsm 時，長出來的名字會對不上。慣例下（入口、fsm.json 同一層）沒事。
- **編出來的東西預設 `AOS_ENTRY` 是 `_entry`**：外面把 `AOS_ENTRY` 改掉，長出來的子資料夾、組合子的步就找不到入口。
- **組合子的 shell**：par 不轉訊號（父 shell 被殺，背景的步可能留著，靠 aos-exec 打整群才收得掉）；if 分不出「條件為假」和「條件那步壞掉」（都是非 0）；步數多時每一步多起一個 aos-exec。
- **`copy` 在編的時候讀**：被抄的檔之後改了，要重編才會跟上；抄的是內容不是連結。
- **Janet 數字是浮點**：超過 2^53 的整數會失準；`janet-main` 印回原始碼時長字串（反引號）會變成一般字串、註解不留。
- `.env` 的值只收不用引號的（有空白、`#`、引號、`$`＝`ValueBad`）。

## 未決（選項，沒做）

- **反編譯（JSON → Janet）**：甲、逐檔照抄成 `(dir "fsm.json" {…})`（簡單、但看不出 fsm 結構）；乙、認得 loop／fsm／單子／指示詞的形狀就還原成 `aos-loop`／`aos-fsm`／`inst`／`env`（好讀、要維護一張形狀表）；丙、只做「看得懂的 diff」（編一次跟磁碟上的比，告訴你手改了哪裡），不還原。頂層傾向丙先、乙後，未做。
- **組合子要不要改用 fsm 表達**：seq 可以是一串格接到一個退 10 的 `done` 格；但 fsm 的 state 留在 stack，做完一次再跑會停在 done（要換小格或清 state），所以先用 shell。
- **單子太大要不要自動長成檔**（C-55「檔太大就長成資料夾」那條的 JSON 版）：現在一律留在原地，要長就自己寫 `(dir …)`。
- 要不要做成 jpm 套件、放進 janet-lab（那邊是獨立 repo，這次唯讀沒動）。
