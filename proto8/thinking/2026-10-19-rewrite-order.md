# 2026-10-19 重寫順序：daemon、kernel、tasks、tick、工具呼叫

← [討論紀錄](README.md)｜原則：[CONCEPTS](../docs/CONCEPTS.md)、[NORMS](../docs/NORMS.md)、[CONVENTION](../docs/CONVENTION.md)｜待定：[NORMS/08](../docs/NORMS/08-待定.md)｜程式：[bin](../bin/README.md)、[demo](../demo/README.md)｜舊實作：git 5546be29（`git show 5546be29:proto8/lib/README.md`）

使用者原話（10-19）：「請 fable 先讀過 proto8 的原則，再排出重寫順序（daemon、kernel、tasks、tick、工具呼叫），只把衝突帶給我。」

fable 通讀 CONCEPTS、NORMS、CONVENTION、bin／demo 說明之後排的順序；前一節是要使用者裁定的，後面各塊照原則定。

## 要你看的（衝突與方向問題）

### 1. 「跑幾圈」「身體」這兩個 key 各有兩個名字（原則之間的衝突）

N-28、N-06、N-07 用 `times`（跑幾次）和 `inst`（身體），aos-loop（P-06）叫 `max` 和 `run`；C-54 要同一個詞全體系同義。

→ **已定（10-19 晚，[ideas § 22](2026-10-19-ideas.md)）**：使用者「那就用到最新的吧」＝`run`／`max`；N-06、N-07、N-11、N-28 用這兩個名字，`interval_ms` 等日後當 loop 的選填 key 長出來（④）。

### 2. tasks（seq／par／if）在新做法下還要不要做（方向問題）

10-15 你說 tasks「地位等同於 C 語言的 stdlib」（CONCEPTS § tasks、N-34）。10-19 之後入口和格可以是 shell 檔，而 shell 本來就有這三樣：`aos-exec a && aos-exec b` 是 seq、`aos-exec a & aos-exec b & wait` 是 par、`if aos-exec c; then …; fi` 是 if。你 10-12 也說過「aos seq 那些流程控制的東西，很多其實都是不必要的」。C-56 最後一步要把多餘的清掉。

剩下的價值只有一樣：單子是資料、能內嵌進 fsm.json（你 10-19 說這塊「很好用」）。想在一格裡寫「先跑這兩張單子、再跑那張」，用 shell 就得開資料夾。

後果：做，就是三支幾十行的 bin 指令，只收 JSON 格清單（格的寫法跟 fsm 的 `val` 一樣）；資料夾程式之間的組合一律寫 shell。不做，N-34 和 C-41 那段改成「shell 就是 stdlib」。

推薦：做，但只做 JSON 版。

→ **未決**：使用者還沒答。

### 3. LLM kernel 要看 token 用量，但它看不到（需求跟原則的衝突）

你 10-15 定 LLM kernel「根據 token 消耗量是否見底來看看說要不要擋」；kernel 跑一封信只看到結束碼（C-52 不偷看下層），腦拿到的 `usage` 在腦的程式裡。

→ **已定（10-24，[LLM kernel](2026-10-24-llm-kernel.md)）**：使用者「都按建議做」＝開通道——kernel 跑信時給環境變數 `AOS_KERNEL_REPORT`，指向這封信小格裡的一個檔；腦願意的話把 `usage` 寫進去，沒寫就只算次數；額度同時認 `calls` 和 `tokens` 兩個上限。

### 4. 工具呼叫被 NORMS 待定「方向問題甲」擋住一半（待定點名）

→ 工具呼叫 10-23 照 [10-23 工具呼叫](2026-10-23-tool-calls.md) 做了：每個工具資料夾放 `tool.json`（給模型看的 `description`、`parameters`），範本只定參數從 stdin 進、結果從 stdout 出。本題提的 `input` key（`stdin`／`inbox` 兩種）沒做；agent 當工具時題目怎麼交仍在[待定](../docs/NORMS/08-待定.md)（使用者「inbox 先不管」）。

### 5. NORMS/08 兩條舊帳，daemon 動工時順手結（不擋）

→ **已定（10-20，[ideas § 25](2026-10-19-ideas.md)）**：使用者「照預設」＝「argv[0] 程式不自己 setsid」那條結案刪掉、ctl `seq`／state `ctl_seq` 回音保留；kernel 的三條待定（公告、`_metainfo` 通用寫法、錯誤路徑評估）第一版用不到，不擋。

## 順序（一行）

tick → 腦的工具呼叫 → tasks → daemon → LLM kernel → 通用 kernel。前兩塊只靠現有的 bin、各自幾十行、各有能跑的 demo，使用者最快能試；tasks 跟 daemon 共用「整群收」那段程式；兩種 kernel 要 daemon 把 agent 和 kernel 同時跑起來才有東西看，所以最後。①②④⑤ 已做。

## 各塊

### ① tick

已做（`aos-tick`，見 [bin](../bin/README.md)）。

### ② 腦的工具呼叫

已做，形狀照 [10-23 工具呼叫](2026-10-23-tool-calls.md)（本稿的「三態變四態」不採用）。

### ③ tasks

做什麼：`aos-seq FILE`、`aos-par FILE`、`aos-if FILE`。FILE 是 JSON：seq／par 是 `{"items": [格…]}`，if 是 `{"cond": 格, "then": 格, "else": 格}`（else 選填）；格＝字串（子資料夾，`aos-exec` 它）或物件（單子，行程內 `aos_inst.run()`），跟 fsm 的 `val` 同一套（C-48 沿用格式族、不開新格式）。只看結束碼（N-34）：seq 第一個非 0 就停、以那個碼退；par 全起、等全部、任一非 0 就以第一個非 0 退，還在跑的整群收掉（P-36）；if 看 cond 的碼，0 走 then、非 0 走 else，退分支的碼。10 一律原樣往上（透明轉交，N-43）。自己的錯退 1。

依據：C-41、N-34、N-43、C-48、P-36；第 2 題。從舊程式拿：`aos_seq`／`aos_par`／`aos_if` 的流程（各三十行）。

完成的樣子：`demo/tasks/`（fsm.json 一格內嵌 `aos-seq`、一格 `aos-par`）跑通；測試六個。做 par 時把 aos_inst「起子程式、整群收」那段拆成 `start()`（不阻塞、回句柄），④ 直接用。

### ④ daemon

已做（[impls/aos-daemon](../impls/aos-daemon/README.md)；五點裁定見 [ideas § 25](2026-10-19-ideas.md)）。

### ⑤ LLM kernel

已做（10-24，[LLM kernel](2026-10-24-llm-kernel.md)、[impls](../impls/README.md)）。

### ⑥ 通用 kernel

做什麼：`aos-kernel-general KERNEL.json`，身體骨架同 ⑤，排序那步換成問判官。判官＝表上一格（資料夾程式；預設 agent-bob 範本）：kernel 把局面（queue、running、slots、budget）寫成一題放進判官小格的 `ws/inbox/`（P-32）、`aos-exec` 它、從 `ws/out/` 讀 `{"run", "defer", "reject"}`（不讀 stdout，N-37 作廢後就是這條路）；判官非 0、逾時、形狀不對，這拍退回 ⑤ 的規則，state 記 `judge_fails`。資源種類＝信裡 `_metainfo.resource` 一個字、`slots` 每種幾格（[10-15 通用 kernel 稿](2026-10-15-general-kernel.md)已定）。兩支不併（N-42），程式共用 lib（C-50）。

依據：C-15、C-29、N-42、N-20、C-52、P-11、P-32；10-15 通用 kernel 稿已定的六條照用。從舊程式拿：`aos_kernel_general.py`、`aos_kernel_judge*.py`。

完成的樣子：`demo/kernel-general/`——規則判官先把形狀、後援、省判官跑通；再換 agent 判官（假腦照規則回 JSON）。測試約八個。

## 寫到哪

還沒做的是 ③ tasks、⑥ 通用 kernel。每做完一塊：程式的 README 一段、demo README 一段、CONVENTION 若動到當批改、NORMS 把那塊的「現無實作」拿掉並照使用者的裁定改字（條文由 fable 改）、code map 同步、測試全綠。
