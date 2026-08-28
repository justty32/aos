# aos M1 落地程式碼審查報告（B 隊）

- **審查點**：`b5cc35a`（branch `roadmap-run`），範圍 `cbdc50c..HEAD`：S1 `dfef513`、S2 `62bc8b6`、S3 `351b4e7`、S4 `23ed92b`、S5 `2fd5df7`、S6 `3fe0843`、S7 `bf12ff4`
- **建置與測試**：`cmake --preset default` → build → `ctest --preset default` = **4/4 全綠**（`aos_inst_tests` 6.92s）
- **repo 全程未動**：結束時 `git status --porcelain` 為空，未 commit、未 push。臨時測試一律在 scratchpad 進行，沒有改過 repo 內的 tests。
- **腳本**：本目錄 `scripts/`（57 份，三個鏡頭＋隊長的攻擊腳本，可直接當回歸測試素材）
- **注意**：我拿到的 worktree 一開始停在 `f2a802b`（M1 之前，沒有任何 M1 程式碼）。我把**自己的** worktree 分支 reset 到 `b5cc35a` 才開始審；`roadmap-run` 與 `main` 未動。

---

## 0. 總結

**28 條發現：27 CONFIRMED、1 PLAUSIBLE。嚴重度：高 5、中 12、低 11。**

> **數字更正**：我在口頭補篇裡說過「27 條」，那是把「27 條 CONFIRMED」誤植成總數。正確是**總數 28 條，其中 27 條 CONFIRMED、1 條 PLAUSIBLE（#23）**。本檔為準。

### 判斷：M1 不能算收工

三個獨立理由：

1. **有一條不需要崩潰、不需要併發、每天都會踩到的靜默資料遺失**（#1）。批被執行完之後 `inst-head.json` 的 id 永不失效，於是「同一組檔名＋內容」的**全新投遞**會被去重誤判成崩潰殘留：投遞被刪、什麼都不跑、退出碼 0、**stderr 一個字都沒有**、`turn` 也不動。從外面看跟「沒事可做」完全一樣。根因在設計層：verdicts 自己記過「隨機 id 需名冊＝manifest，與『manifest 留 v2』相撞」，於是選了內容導出的 id——而內容導出的 id 在原理上就分不出「殘留」與「重投」。SPEC §D-6 的「覆蓋範圍」段只誠實聲明了**漏放行**（重複執行）那一個方向，完全沒有描述**誤殺**這個方向。

2. **S3 的「header 先 rename 作提交點」論證本身成立，但射程只到「發布」為止。** LD_PRELOAD 取得的真實 syscall 序列證實彙整八步與 §D-5 一字不差；但**取件（`.runi` 的 rename）與釋放（unlink）完全沒有耐久性**（#2／#5），而那正是「同一批不會執行兩次」最後、也最致命的一段。M1 spec 驗收 3 只測了彙整那一段，所以全綠。

3. **驗收條件 1 與 6 明確未達成**：SPEC 還有 11 處 `(planned, M1)`、已知未決 #2／#3 未消；`docs/usage.md` 完全沒有 `deliver`；`aos-folder.md` 仍自稱「這份是規格」且第十節仍寫「整個 `.aos/` 都不進 git」，與它自己被 §E-4 取代的事實正面矛盾。這些落在 commit `299e4c4` 自承的「S8/審查/S9 明日續」範圍內——**是已知待辦，不是新 bug**，但驗收條件就是驗收條件。

### 另外兩條無聲故障（新增，強化上述判斷）

- **#25**：`.aos/inst.json` 是斷掉的 symlink → rc=0、stderr 全空、投遞無限堆積、世界永久卡死。
- **#26**：header 寫失敗 ＋ 投遞刪失敗同時發生 → 同一批**每回合重跑一次，永無止境**。

**無聲故障在 agent loop 裡最貴**——高嚴重度五條裡有三條（#1／#25／#26）是 rc=0 且零診斷輸出。建議修補優先序把這三條放最前面。

### 正面的部分要說清楚

彙整段的 fsync 順序、崩潰狀態機的五個狀態、§D-6 已宣告的覆蓋範圍、`deliver` 的四項規格、C ABI 的尾端追加規則、分層鐵律、ENOSPC 路徑、`aos init` 重跑保護、`.aos/version` 七種異常——**全部經得起打**。900 次並發 `aos deliver` 檔名零碰撞零殘留；1100 筆 deliver／exec 交錯**零遺失零重複**。這份實作的品質很高，問題集中在「提交點的射程」與「批 id 的語意」兩個設計判斷上，不是散落的粗心。

### 已依指示濾除

PATH 找不到執行檔回 126；`exec.cpp` 的 `kill(-pid,…)` 回傳值忽略；C API 失敗後 errno 被解構子 close() 蓋掉；逾時 `wait_until()` 出錯直接 return。`.runi` 不是鎖（TOCTOU）與 `--loop 0`／`did_work` 節流是已排 M2／M3 的 gotcha，**不列為新發現**，但已量化後果（見 §4）。

---

## 1. 逐條缺陷（依嚴重度排序，編號沿用發現順序）

### 【高】

---

#### #1｜高｜CONFIRMED｜`core/inst/src/handoff.cpp:186-207`（比對）＋ `handoff_header.cpp:55-63`（摘要）

**一句話**：批執行完之後 header 的 id 永不失效，導致「同名同內容的全新投遞」被靜默刪除、永不執行。

**證據**（`scripts/t3.sh`，固定檔名生產者連投三回合同一內容）：
```
round 1: exit=0 ticks=1 turn=1 inbox=[]
round 2: exit=0 ticks=1 turn=1 inbox=[]
round 3: exit=0 ticks=1 turn=1 inbox=[]
>>> 期望 ticks=3
```
第 2、3 回合：投遞被 unlink、批不發布、**退出碼 0、無任何 warning、turn 不動**。

`scripts/t1.sh`（走 `aos deliver` 產生的真實投遞）：
```
deliver #1 → {"delivery":"91351-0.json","count":1,"target":".aos/inst.tempd"}
exec #1    → header id=d21eef57db9ba9a1, ran.log=1 行, turn=1
[放回 91351-0.json，內容一字不差]
exec #2    → exit=0, ran.log 仍 1 行, inbox 清空, turn 仍 1
```
`scripts/t15e.sh` 確認**危險窗口是永久的**：批被取走、執行完、再空轉 5 回合，header 的 id 完全不變。

**機制**：去重判準是「（排序後投遞檔名＋內容）摘要 == 現任 header 的 id」，這個判準分不出「上一輪沒刪掉的殘留」與「恰好長得一模一樣的全新投遞」；而 `claim_instruction`／`release_instruction` 都不碰 header，窗口一直開著直到下一次成功發布。

**實務可達性**：`next_delivery_name()`（`handoff_fs.cpp:176-180`）的 `seq` 是 `static atomic`、**每個行程從 0 起算**，而 `aos deliver` 是一次性行程，所以 CLI 產生的名字永遠是 `<pid>-0.json`——只差一個 pid 重用。本機 `pid_max=4194304`（約 200 萬次投遞繞一圈），但**預設 `pid_max=32768` 的容器只要約 4.5 小時**；smoke-notes 自己記錄的 pid 是 694／697／699（WSL，pid 空間很小）。另一條更直接：§D-2／§D-3 明說投遞開放給外部生產者、只要求檔名唯一，任何用**內容定址或確定性命名**的生產者天天踩到。

**這是刻意行為，不是實作滑手**：`core/inst/tests/test_handoff_header.cpp:73` 把同一份投遞寫回去並斷言 `CHECK_FALSE(result.published)`；plan S3 的測試設計也明文要求。**問題是這個設計選擇的反向代價從來沒有被立法、也沒有被警告。**

**建議修法**（不需要 manifest，成本很低）：在 `remove_accepted_deliveries()` 全數成功且目錄 fsync 成功之後，把 header 改寫成帶 `"swept":true`（或直接刪掉 header）；去重比對時**只有 `swept` 不成立**才啟用。殘留（一定是 sweep 沒完成）照樣被擋，全新的同名同內容投遞會正常執行。最低限度：命中去重而刪投遞時 **MUST 噴 warning**。

**違反**：§D-6 只授權「同一組投遞殘留於 inbox 時 MUST NOT 二次發布」，沒有授權「刪掉沒發布過的投遞」；同時違背 §D-4「投遞 MUST 在發布成功之後才刪」的精神——這裡是**沒發布也刪**。

---

#### #2｜高｜CONFIRMED｜`core/inst/src/handoff.cpp:281`

**一句話**：取件的 `rename(inst.json → inst.json.runi)` 之後沒有目錄 fsync，斷電後整批第二次執行，且去重完全攔不到。

**證據**（`scripts/t4.sh` + `scripts/trace.c`，LD_PRELOAD 攔截；本機**沒有 strace／ltrace**）：
```
RENAME(.aos/inst-head.json.temp -> .aos/inst-head.json)   ← 提交點
open(.aos)[DIR] ; FSYNC(.aos)
RENAME(.aos/inst.json.temp -> .aos/inst.json)
open(.aos)[DIR] ; FSYNC(.aos)
UNLINK(.aos/inst.tempd/94552-0.json)
open(.aos/inst.tempd)[DIR] ; FSYNC(.aos/inst.tempd)
--- 以上完全符合 §D-5 ---
RENAME(.aos/inst.json -> .aos/inst.json.runi)   ← 之後沒有任何 FSYNC，接著就跑 side effect
```
後果鏈三段各自直接觀察到：(a) trace 證實缺 fsync；(b) POSIX 語意：rename 未落盤時斷電會回退；(c) 「`inst.json` 存在＋無 `.runi`」這個狀態會再跑一次——`scripts/t9.sh` 狀態 5 直接量到 `fires` 由 0 變 1。此時投遞早已在彙整階段被刪除，**去重只看收件匣，攔不到**；aggregate 因 `lstat(base)==0` 早退，claim 成功，整批重跑。

**建議修法**：`claim_instruction` 在 rename 成功後補 `detail::fsync_dir(parent_directory(paths.base))`，失敗比照 aggregate 記 issue 續行。

**違反**：§D-5（「所有寫檔 MUST fsync」的耐久性意圖）、§D-7（`.runi` 存在 ⟺ 有一回合沒跑完——這裡回合在跑但 `.runi` 可能不存在）。

---

#### #3｜高｜CONFIRMED｜`core/inst/src/handoff_fs.cpp:64-65`（`read_file` 的 `open`）＋ `handoff.cpp:155`

**一句話**：收件匣裡放一個 FIFO，`aos exec` 就永久卡死，鎖都沒拿到，整個世界停擺。

**證據**（`scripts/v7.sh`）：
```
inbox: [pipe.json zz-ok.json ]
exec 退出碼=124   耗時=10s     ← 124 = 被 timeout 砍掉
inbox 事後: [pipe.json zz-ok.json ]   ← 連正常的 zz-ok.json 都沒被處理
[把 FIFO 移除後]  exec 退出碼=0   inbox 事後: []
```
鏡頭 3 的加強版（`scripts/tx.sh`）：`stderr=[]`、`.aos` 連 `.runi` 都沒建（鎖沒拿到）、**後續 exec 一個個疊上去一起卡（實測 6 個卡住的行程）**、`deliver` 不受影響。

**機制**：`read_file()` 用 `open(path, O_RDONLY|O_CLOEXEC)`，對沒有寫端的 FIFO **無限阻塞在 open**。發生在 claim 之前，所以世界既沒被鎖、也沒有任何診斷輸出，`--loop` 直接凍住。收件匣是 §D-3 明定「唯一由外部生產者執行」的公開介面，任何生產者的 bug 或人手誤建就能永久癱瘓這台機器。

**同場已驗證沒問題的**：目錄 → `Is a directory` 隔離；斷連結 → `ENOENT` 隔離；指向 `/etc/passwd` 的連結 → `JsonSyntax` 隔離且**只改名連結本身、沒動到目標檔**。

**建議修法**：`read_file()` 開檔加 `O_NONBLOCK|O_NOFOLLOW`，開成功後 `fstat` 檢查 `S_ISREG`；非普通檔一律走既有的 `isolate_delivery` 隔離成 `.bad`，再清掉 `O_NONBLOCK` 讀。

**違反**：§D-4「無效投遞 MUST 隔離、噴 warning、**繼續處理其餘**」——這裡既沒隔離也沒 warning，而且沒有繼續處理其餘。

---

#### #25｜高｜CONFIRMED｜`core/inst/src/handoff.cpp:117`（`lstat`）vs `:275`（`read_file`／`open`）

**一句話**：`.aos/inst.json` 是斷掉的 symlink 時，世界被永久卡死，而且 rc=0、stderr 全空——完全無聲。

**證據**（`scripts/v11.sh`，隊長複驗；原始發現 `scripts/ty.sh`）：
```
exec#1 rc=0 stderr=[]
exec#2 rc=0 stderr=[]
exec#3 rc=0 stderr=[]
log 內容: []            ← 三份合法投遞，一筆都沒跑
inbox 堆積: 3 份
turn=0
[rm 掉壞 symlink 之後] log=[M1,M2,M3]
```
`timeout 3 aos exec --loop 100` 也是 rc=124、輸出 0 行的無聲空轉。

**機制**（讀碼確認）：兩層對「存在」的定義不一致，中間夾出一個規格沒定義的第三態。
- `aggregate_instructions:117` 用 **`lstat`**：斷掉的 symlink `lstat` **成功** → 判定「`inst.json` 已有一份沒被讀走」→ 依 §D-4 不發布 → `return HandoffState::Ok`。
- `claim_instruction:275` 用 **`read_file`／`open`**：**跟隨** symlink → `ENOENT` → `return HandoffState::NoInstruction` → CLI rc=0。

比 #3 更陰險：FIFO 至少會卡住讓人察覺；這個是 rc=0 ＋ 零輸出 ＋ `did_work=false`，`--loop` 會安安靜靜地以為自己閒著。

**建議修法**：兩邊對齊。最小改動是 `claim_instruction` 拿到 `ENOENT` 時先 `lstat(paths.base)`；`lstat` 成功（存在但讀不到）就回 `InstructionReadFailed` 而不是 `NoInstruction`，讓 CLI rc=1 噴出來。

**違反**：§D-1／§D-7 的狀態機隱含「`inst.json` 存在 ⟹ 有一批等著被取」，這裡出現「存在但永遠取不走」的第三態，規格沒有定義。

---

#### #26｜高｜CONFIRMED｜`core/inst/src/handoff.cpp:230-240` ＋ `:56-67`

**一句話**：header 寫失敗與投遞刪失敗同時發生時，同一批每回合重跑一次，永無止境。

**證據**（`scripts/v11.sh`：`.aos/inst-head.json.temp` 佔成目錄讓 header 寫入 EISDIR ＋ inbox `chmod 500` 讓投遞刪不掉）：
```
warning: .aos/inst-head.json.temp: HeaderWriteFailed: Is a directory
warning: .aos/inst.tempd/1000-0.json: DeliveryRemoveFailed: Permission denied
exec#1 後 log 行數=1
exec#2 後 log 行數=2
exec#3 後 log 行數=3     ← 沒有任何機制會讓它停
```
三回合 rc 全 0。

**機制**：`handoff.cpp:222-229` 的註解寫得很清楚：「header 寫不成不是致命傷：這一批照發，只是這一輪沒有去重保證」。這個取捨**單獨發生時是對的**——問題是去重保證要擋的正是「投遞沒刪掉」這個情境，而兩者成因高度相關（同一個唯讀／異常的 `.aos`）。兩個「各自可容忍」的降級疊在一起，就變成無上限的副作用重播。

**建議修法**：同一輪同時出現 `HeaderWriteFailed` 與 `DeliveryRemoveFailed` 時升級為致命（回非 Ok、rc=1）。更根本：投遞刪不掉就不該回 `Ok`——§D-4 隱含刪除是協定的一部分，刪不掉代表協定沒走完。

---
### 【中】

---

#### #4｜中｜CONFIRMED｜`core/inst/src/handoff_header.cpp:73-97`

**一句話**：`decode_header_id` 的定點解析會先吃到巢狀物件裡的 `"id"`，M2 填 `result` 時必爆。

**證據**（`scripts/v8.sh`，真 id = `83068ea820a5c575`）：
```
A. {"version":1,"result":{"id":"83068ea820a5c575"},"origin":"aggregated","id":"0000000000000000"}
   → exit=0  執行總數維持 1  inbox 被清空     ← 讀到巢狀 id，全新的批被靜默丟掉
B. {"version":1,"result":{"id":"0000000000000000"},"origin":"aggregated","id":"83068ea820a5c575"}
   → exit=0  執行總數變 2                      ← 讀到假 id，去重失效、重跑
C. M1 自己寫的版面（id 是第二個 key、result 是 null）→ 不受影響，執行總數維持 1
```
解析是「找第一個 `"id"`，後面接冒號就採用」。註解說「出現在別的位置就繼續往後找」，但那個 fallback 只在**後面沒有冒號**時才觸發；巢狀物件的 `"id":` 後面就是冒號，第一個匹配就贏。

**射程**：M1 現行版面不會觸發。但 §C-8 明寫 `result` 是「由 loop 於 writeback 寫回（值域於 M2 定義）」——M2 一旦把 `result` 填成含 `id` 的物件就會拿錯 id 比對。手改或第三方寫的 header 亦同。

**已查證沒問題的相鄰情況**：轉義字串 `"origin":"the \"id\" of a batch"` **不會**誤匹配（實際位元組是 `" i d \`，不構成 `"id"`）。鏡頭 3 測轉義版得到「沒被騙」，與本條不衝突——會被騙的是**裸位元組的巢狀物件**。

**建議修法**：改成只認自己寫出去的固定版面（比對前綴後取 16 位 hex），或限制只掃頂層第一層 key。

---

#### #5｜中｜CONFIRMED｜`core/inst/src/handoff.cpp:296`

**一句話**：釋放的 `unlink(.runi)` 沒有目錄 fsync，目前只是「剛好」被 `advance_turn` 的 `fsync(.aos)` 順帶落盤——M2 把 turn 搬走之後保護就消失。

**證據**：trace 顯示 `UNLINK(.aos/inst.json.runi)` 之後沒有直接 fsync，但緊接著 `advance_turn` 的最後一步是 `open(.aos)[DIR]; FSYNC(.aos)`，而 `.runi` 就住在 `.aos` 底下，目錄項一併落盤。

**這是巧合不是設計**，三種情況會失效：
1. `advance_turn` 提早失敗——turn 內容壞掉時 `parse_turn` 回 EINVAL 就直接 return，rename 與 `fsync_dir` 都不跑（見 #9，實測到這個狀態）；
2. 直接用 C++ API `release_instruction` 的呼叫端根本沒有 `advance_turn`；
3. **§B-3 明寫 turn 由 loop 持有、M2 要搬走**——搬走之後這條線上的 `fsync(.aos)` 就沒了。

失效後果：`.runi` 復活 → 每次 `aos exec` 都回 3，**世界永久卡死**，而 `aos recover` 排在 M3。

**建議修法**：`release_instruction` 自己補 `fsync_dir`，跟 #2 同一個修法，不要留這個巧合。

---

#### #6｜中｜CONFIRMED｜`core/inst/src/run_exec.cpp:243`（aggregate）vs `:253`（claim）

**一句話**：`.runi` 已存在時，`aos exec` 會先完成一整輪彙整（發布批＋寫 header＋刪投遞），才在取件那一步回 3。

**證據**（`scripts/v1.sh`）：
```
跑之前 .aos: [inst.json.runi inst.tempd turn version ]  inbox:[z.json]
aos exec: refusing v6: .aos/inst.json.runi already exists
exit=3
跑之後 .aos: [inst-head.json inst.json inst.json.runi inst.tempd turn version ]  inbox:[]
```
「拒絕啟動」之前已經做了三個不可逆動作，世界現在同時掛著 `inst.json` 與 `inst.json.runi` **兩批待處理**。結果本身不算壞，但這是條款沒說的行為。配合 #5 的卡死情境更難看：卡死期間新投遞會被持續吃進 `inst.json` 並更新 header，然後永遠不執行。

**建議修法**：把 `.runi` 檢查提到 `aggregate` 之前，或 §D-7 補一句「拒絕啟動不阻止彙整；彙整與取件是兩個獨立的守衛」。

**違反**：§D-7 的措辭（行為在條款之外）。

---
#### #7｜中｜CONFIRMED｜`core/inst/src/handoff.cpp:33`

**一句話**：隔離用的是覆蓋語意的 `rename`，第二份同名壞投遞會把第一份 `.bad` 的鑑識證據無聲銷毀。

**證據**（`scripts/v1.sh`）：
```
第一次隔離: [x.json.bad]  內容=[FIRST-BAD-EVIDENCE]
第二次隔離: [x.json.bad]  內容=[SECOND-BAD-EVIDENCE]   ← 第一份不見了
```
程式是 `rename(path, path + ".bad")`，覆寫式。撞名前提就是 §D-2 已知的 pid 重用（兩次都撞、且兩次都無效）。同一層 `handoff_fs.cpp:150` 已經有現成的 `publish_exclusive()` 排他 helper，`handoff_deliver.cpp` 也在用，這裡沒用。

**建議修法**：隔離改走 `publish_exclusive()`；`EEXIST` 時往後找 `.bad.1`、`.bad.2`…，或記 `IsolationFailed` issue 讓人處理。

**違反**：§D-8「彙整者 MUST NOT 自動刪 `.bad`」——覆寫等同刪除。

---

#### #8｜中｜CONFIRMED｜`core/inst/src/handoff.cpp:155-160`

**一句話**：讀取失敗（權限／IO）的投遞被貼上 `.bad`，但內容其實完全合法，而且從此永久出局。

**證據**（`scripts/v1.sh`，把一份合法投遞 chmod 000）：
```
aos exec: warning: .aos/inst.tempd/y.json: DeliveryReadFailed: Permission denied
exit=0
inbox: [y.json.bad]
被標 .bad 的內容其實是: [[{"argv":["/bin/true"]}]]
```
`.bad` 不進彙整（§D-4）且 MUST NOT 自動清（§D-8），所以一次暫時性的 EACCES／EIO 就把一份有效工作永久踢出佇列。鏡頭 3 併發測試也大量走到這條路徑（60 輪 13761 次 `DeliveryReadFailed` → `IsolationFailed`；該場景因檔已不存在所以無害，機制相同）。

**建議修法**：只在 `read_all()` 判定內容無效（`InvalidDelivery`）時隔離；`DeliveryReadFailed` 改成記 issue、跳過、下一輪再試（ENOENT 直接靜默跳過）。

**違反**：§B-1（`.bad` ＝「**內容無效**，已被隔離」）與 §D-4（「**無效投遞** MUST 隔離」——讀不到不是無效）。

---

#### #9｜中｜CONFIRMED｜`core/inst/src/run_exec.cpp:128-131` ＋ `:285-289`

**一句話**：`.aos/turn` 內容壞掉時，回合明明正常跑完卻回 1，而且世界從此每一輪都回 1、aos 自己救不回來。

**證據**（`scripts/v5.sh`）：
```
round1 exit=1 累計執行=1 turn=[abc]
round2 exit=1 累計執行=2 turn=[abc]
round3 exit=1 累計執行=3 turn=[abc]
```
批確實執行了、`.runi` 確實被刪了，回合完全正常收尾，退出碼卻說失敗；turn 也永遠修不回來。鏡頭 3 的完整壞內容表（`scripts/t11.sh`）：`abc`／26 個 9／`-5`／空檔／無 LF／只有 LF／前導空白／二進位垃圾 → 全部 rc=1 且批照跑；檔案不存在 → rc=0 建出 `1` 加 LF（§B-3 正確）；是目錄 → rc=1 `Is a directory`。

**建議修法**：主線裁一下 turn 壞掉的語意（我傾向：噴 warning、視為 0 重建，跟「讀不到」同款——PC 是便利設施，不該讓世界變磚），並在 §B-3 補一句。無論怎麼裁，退出碼都不該因為 PC 記帳失敗而說「回合沒跑完」。

**違反**：§D-9「退出碼只回答『回合有沒有正常跑完』」。也擦到 §B-3：條款只立法「讀不到＝視為 0」，對「讀到壞內容」完全沒立法。

---
#### #10｜中｜CONFIRMED｜`core/inst/src/handoff_fs.cpp:182-186`

**一句話**：投遞檔名只要含第二個點就被永久靜默忽略：不收、不隔離、不警告。

**證據**（`scripts/t6.sh` ＋ 鏡頭 3 `scripts/tz.sh`）：
```
[2026-08-28.report.json 連跑三回合]
run1 exit=0 / run2 exit=0 / run3 exit=0
inbox: [2026-08-28.report.json ]     ← 永遠躺在那裡，一句話都沒有

[第三方生產者用帶毫秒的時間戳命名，另加一份正常投遞]
exec x3 → log=[OK]                   ← 時間戳那份從沒跑過，零警告
```
程式取的是**第一個**點之後的整段，要求它正好等於 `.json`。實際接受集合：
- **收**：`1000-0.json`、`x.json`、`中文.json`、`has space.json`、含換行的檔名
- **不收**：`a.b.json`、`a..json`、`.hidden.json`、`.json`（`.temp`／`.bad`／`.runi` 不收是對的）

`aos deliver` 自己產的名字是純數字加連字號所以撞不到；但 §D-2／§D-3 明說投遞開放給外部生產者。另外 `handoff_fs.hpp:50-52` 的註解寫「**副檔名部分**正好是 `.json`」，讀起來是最後一個點，與程式不符。

**建議修法**：改成從**尾端**判定——以 `.json` 結尾、且不是狀況字收尾即收（§B-1 的狀況字是封閉清單，從尾端剝更貼合規格）。至少要對「以 `.json` 結尾但形狀不合」的檔噴一次 warning，不要靜默。

**違反**：§D-4「只收沒有狀況後綴的投遞」——`a.b.json` 沒有狀況後綴卻不收；靜默也違背 §D-8 的「留現場、給人看見」哲學。

---

#### #11｜中｜CONFIRMED（程式碼路徑明確；執行期證據由鏡頭 2 的故障注入器 `scripts/fault.c` 取得，我未獨立重跑注入器）｜`core/inst/src/handoff_fs.cpp:163-173` ＋ `handoff_deliver.cpp:97-105`

**一句話**：`publish_exclusive` 的 `link+unlink` 退路在 unlink 失敗時「回報失敗但其實已經成功」，生產者照著重投就多一份。

`link()` 的排他語意與 `RENAME_NOREPLACE` 等價，這點沒問題。問題在收尾：`link` 成功、`unlink(from)` 失敗時回 false 並把 unlink 的 errno 當成整體錯誤。此時**目的檔已經在收件匣裡、內容完整、aggregate 一定會收**，但 `deliver_instructions` 看到非 EEXIST 就回 `RenameFailed`、CLI 回 1。

**證據**（`FAULT_NO_RENAMEAT2=1` 逼走退路 ＋ `FAULT_UNLINK_TEMP=1` 讓收尾 unlink 回 EPERM）：
```
aos deliver: cannot deliver .../143718-0.json: RenameFailed: Operation not permitted
   deliver rc=1
   inbox: 143718-0.json 143718-0.json.temp     ← 投遞其實已經在裡面了
[生產者依失敗回報重投]
   inbox: ... 143722-0.json
   exec rc=0   ran.log: [A,A,]                 ← 重複執行
```
`handoff_deliver.cpp:106-110` 自己就寫下了正確的原則（「謊報投遞失敗會讓生產者重投，那才真的多出一份」），退路這裡違反了自己的原則。

**建議修法**：`link` 成功後 `unlink` 失敗改成「回 true ＋ errno 放進 `DeliverResult::sync_error`」，跟 `fsync_dir` 失敗同一套處理。

**違反**：§D-2／§D-3。

---

#### #12｜中｜CONFIRMED｜`core/inst/src/run_init.cpp:117-123`

**一句話**：`aos init` fsync 了 `.aos` 自己，但從未 fsync 父資料夾，所以 `.aos` 這個目錄項不保證落盤。

程式 fsync 了 `aos_fd`，然後直接 `close(folder_fd)`——`folder_fd` 從頭到尾沒有 fsync。`.aos` 的目錄項住在**父資料夾**裡；`version`／`turn` 的內容再怎麼 fsync 也救不了「`.aos` 這個目錄項沒落盤」。斷電後可能得到「`aos init` 回 0，但世界整個不存在」。失敗清理路徑（`unlinkat` 之後）同樣沒有 sync。

**建議修法**：在 fsync `aos_fd` 之後補 `fsync_retry(folder_fd)`。

**違反**：§D-5、§B-4（version 是崩潰後判斷世界能不能用的第一道關卡）。

---

#### #13｜中｜CONFIRMED（讀碼；時間窗未實跑複現）｜`core/inst/src/exec.cpp:64`

**一句話**：`exit` 檔的 `open` 少了 `O_CLOEXEC`，在 `parallel` 的多執行緒 fork 場景會把可寫 fd 洩漏給外部程式。

`run_batch.cpp:166-196` 用 `std::vector<std::thread>` 跑 `parallel` 指令。T1 在 `write_exit_status` 持有這個 fd 的同時 T2 `fork()`，子行程就繼承一個**可寫**的 fd 進到 `execve` 之後的外部程式。整個 repo 只有這一處 `open` 沒帶 `O_CLOEXEC`（`handoff_fs`／`capi_io`／`run_init`／`run_exec` 都有），而它偏偏是唯一活在「會 fork 的多執行緒行程」裡的那一處。

**建議修法**：加 `O_CLOEXEC`。

---

#### #14｜中｜CONFIRMED｜`core/inst/src/run_init.cpp`（全檔，無相關程式碼）

**一句話**：§E-4 的 gitignore 政策沒有任何實作者，`aos init` 建出來的世界從出生起就不滿足條款。

在 `core/inst/src/` 搜尋 gitignore 零命中；`aos init w1` 之後 `w1/` 底下只有 `.aos`。

§E-4 用的是 MUST：「**世界**的 gitignore **MUST** 排除 `*.temp`、`*.runi`、`*.tempd/`、`*.bad`；**MUST** 納入 `.aos/version` 與 `.aos/turn`」，而且 §E-3 的整個回滾論證（「回滾到含 `.runi` 的 commit ＝ 永久拒絕啟動的死鎖世界」）都靠這條擋。條款沒明說是誰的責任，於是就沒有人做。依 SPEC 自己的三向標記規則（§E-4 沒有 planned 標記），實作視為 bug。

**建議修法**：主線裁一句「`aos init` **MUST** 建立符合 §E-4 的 gitignore（已存在則不動）」補進條款；否則 §E-4 就是一條沒有執行者的法。

---

#### #21｜中｜CONFIRMED（原標 PLAUSIBLE，經鏡頭 3 重現後升級，隊長已複驗）｜`core/inst/src/handoff.cpp:92-101`、`:192-202`

**一句話**：去重命中時，一份與這批毫無關係的 `inst.json.temp` 殘骸會被當成「這一批」扶正並執行。

**證據**（`scripts/v11.sh`）：
```
exec1 → log=[GOOD]，header id=a60c70e4e4104d50
[放回同名同內容投遞觸發去重] + [手動塞一份無關的 .aos/inst.json.temp]
exec2 rc=0 → log=[GOOD, UNRELATED_GARBAGE]
```
`temp_holds_complete_batch()` **只檢查「解析得出非空批次」**，完全不驗證它是不是 header 那個 id 對應的批，接著就直接 rename 成 `inst.json` 執行掉。結果是**執行了未經任何驗證來源的批次**。

觸發需要「`.temp` 殘骸」與「去重命中」同時存在，路徑窄（正常發布會把 `.temp` rename 走，錯誤路徑也會 unlink），但一旦成立後果嚴重。注意 `test_handoff_header.cpp:104` 刻意讓 `.temp` 內容與重新彙整的結果不同——那是為了分辨 roll-forward 與二次發布，本身合理，但也正是這個漏洞被測試「保護」住的原因。

**建議修法**（便宜且精確）：去重分支裡把 `write_all(combined)` 的結果算出來，跟 `.temp` 的位元組**逐位元比對**，相同才 roll forward。canonical 位元組本來就是確定性的（§D-3），不需要任何額外 metadata。

**違反**：§D-6 說「批 `.temp` **完整存在**則 roll-forward」，「完整」在條款裡沒定義。

---
### 【低】

---

#### #15｜低｜CONFIRMED｜`core/inst/src/exec.cpp:71` ＋ `capi_io.cpp:152-159`

**一句話**：`exit` 檔與 `aos_instruction_write_file` 都有 `fsync(fd)` 但沒有父目錄 fsync，新建檔的目錄項不保證落盤。

崩潰後檔案可能整個不存在，而 `exit` 檔的註解自稱「崩潰後對帳的證據」、C API 已經回了 `AOS_INST_OK`。後者是**對外承諾**，比內部路徑更該補。

**建議修法**：補父目錄 fsync，或把承諾降級成「內容落盤，存在性不保證」並改寫註解與 `capi.md`。
**違反**：§D-5 的耐久性意圖。

---

#### #16｜低｜CONFIRMED｜`core/inst/src/handoff.cpp:179-184`（空批次）＋ `:205`（去重命中）

**一句話**：有兩條路徑會在「沒有發布」的情況下刪掉投遞，與 §D-4「投遞 MUST 在發布成功之後才刪」的字面衝突。

**證據**（`scripts/t6.sh`）：兩份 `[]` 投遞 → inbox 清空、批沒發布、header 沒寫、turn 維持 0、rc=0。

兩條都有好理由（不消化空投遞會被永遠重讀；去重命中就是要清殘留），程式碼註解也都寫了——問題純粹在條款是無條件 MUST。

**建議修法**：§D-4 改成「投遞 MUST 在**本輪處理完成**之後才刪；發布成功、整批為空、或去重命中都算完成」。
**違反**：§D-4 字面。

---

#### #17｜低｜CONFIRMED｜`core/inst/src/handoff.cpp:33`（隔離）＋ `:179-184`（早退）

**一句話**：隔離的 `.bad` rename 之後沒有目錄 fsync；而且「這一輪只有壞投遞」時會早退，整輪一次目錄 fsync 都沒有。

後果輕（崩潰後壞投遞回到收件匣，下一輪再隔離一次，冪等），但配合 #7 會蓋掉上一份 `.bad`。

**建議修法**：`isolate_delivery` 成功後無條件 `sync_directory(inbox)`。

---

#### #18｜低｜CONFIRMED（讀碼）｜`core/inst/src/handoff.cpp:124-140`

**一句話**：`opendir` 與 `closedir` 之間有可能 throw 的操作，例外穿出去時 `DIR*` 與其 fd 洩漏。

`std::string name = entry->d_name` 與 `names.push_back(...)` 都可能丟 `bad_alloc`／`length_error`，而 `aggregate_instructions` 不是 `noexcept`。CLI 在 `run.cpp` 接得住例外並繼續，`--loop` 模式下會反覆累積。

**建議修法**：用 `unique_ptr` 搭 `closedir` deleter。

---

#### #19｜低｜CONFIRMED｜`core/inst/src/run_exec.cpp:230` ＋ `run_deliver.cpp:119`

**一句話**：版面版本檢查是全等比對，比 §B-4 立法的範圍嚴。

`version=0`（比自己舊）與 `version=1` 無 LF 都被拒絕（實測 exec 與 deliver 皆 rc=1），而 §B-4 只立法了「讀不到」與「不認得（**比自己新**）」兩條。行為本身我認為是對的（保守優於猜），落差在條款把範圍寫窄了。

**建議修法**：§B-4 改成「版本不等於現行版面版本 ＝ MUST 拒絕」，並明定 `.aos/version` 的位元組格式是「十進位整數＋單一 LF」。

---

#### #20｜低｜CONFIRMED｜`core/inst/src/run_exec.cpp:26` ＋ `handoff_header.cpp:51`

**一句話**：兩個中間檔不在 §B-2 的版面樹裡，且 `turn.temp` 不合 §B-1 的命名文法。

`.aos/turn.temp` 與 `.aos/inst-head.json.temp` 都沒列進 §B-2（樹裡只有 `inst.json.temp / .runi`）。`turn.temp` 只有兩段，`temp` 不是合法副檔名。

**封閉狀況清單本身沒被違反**：我 grep 過全部 `core/inst/src/`，字面只出現 `.temp`／`.runi`／`.bad`／`.tempd`／`.json` 這五個，沒有第六個狀況字。

**建議修法**：§B-2 補上這兩個中間檔，§B-1 補一句「無副檔名的版面檔，其狀況後綴直接接在名字後」。

---

#### #22｜低｜CONFIRMED｜`core/inst/src/run_exec.cpp:150-153` ＋ 行程訊號處置

**一句話**：`advance_turn` 的 rename 失敗會留下 `turn.temp` 沒人清；`SIGXFSZ` 未處置會讓行程被直接砍死、錯誤路徑清理完全不跑。

實測 `ulimit -f` 觸頂時 rc=153（core dumped），留下 `<pid>-0.json.temp`／`inst.json.temp` 殘骸。殘骸本身無害（`is_delivery_name` 正確忽略 `.temp`，實測 `.temp` 與既有 `.bad` 混在 inbox 時都原地不動、正常投遞照吃），但 M1 沒有任何機制清它，`aos recover` 排在 M3。

**建議修法**：`advance_turn` 失敗時 unlink 自己的 `turn.temp`；考慮忽略 `SIGXFSZ` 讓 write 回 EFBIG 走正常錯誤路徑。

---

#### #23｜低｜**PLAUSIBLE**（本報告唯一一條）｜`core/inst/src/handoff.cpp:241`、`handoff_fs.cpp:92-122`

**一句話**：批發布用的是覆蓋語意的 `rename`，且 `.temp` 是固定名 ＋ `O_TRUNC` ＋ 非排他，理論上併發彙整會互相覆蓋或交錯寫。

§D-4「`inst.json` 已有一份沒被讀走時本輪 MUST NOT 發布（不覆蓋、不合併）」只靠開頭 `:117` 的 `lstat` 擋，是 check-then-act；發布用普通 `rename`（`handoff_fs.hpp:42` 註解明說是刻意的）。`write_file_flags()` 用 `O_WRONLY|O_CREAT|O_TRUNC`（非 `O_EXCL`），三個呼叫點都是固定路徑。

**原語已證實不安全**（`scripts/trunc_demo.py`：兩行程並寫同一個 `O_TRUNC` 固定路徑，300 次有 291 次產生帶 NUL 空洞的混合內容）。破損內容會讓發布出去的批解析失敗 → 依 §D-7「回合正常返回 MUST 刪 `.runi`，**包含**整批解析失敗」→ **整批直接消失**、投遞已被刪，等於資料遺失。

**但在真的 `aos` 上打了 220 輪都沒中**：我 300 回合 x3 支併發 exec（每回合不同 payload）→ 300/300 全部執行、0 遺失；鏡頭 3 另跑 160 輪（`scripts/t9c.sh`／`t9e.sh`／`t9f.sh`，最大批 20MB）→ 批被寫壞 0、含 NUL 的批 0。窗口很窄，只能標 PLAUSIBLE。

**建議修法**：見 §5 裁決三——批 `.temp` 改用每行程唯一的名字寫，最後用 `publish_exclusive()` rename 到 `inst.json`。這一刀同時解掉 #23 與併發雙重彙整。

---

#### #24｜低｜CONFIRMED｜`core/inst/src/handoff_fs.cpp:103-121`

**一句話**：`write_file_flags` 在「寫失敗**且** close 也失敗」時，`close_checked` 會把先發生的 errno 蓋掉，回報的是後者（比較沒用的那個）。`read_file` 同型。

**建議修法**：只有在還沒有錯誤時才讓 close 的 errno 生效。

---

#### #27｜低｜CONFIRMED｜`core/inst/src/run_exec.cpp:133`

**一句話**：`.aos/turn` 等於 `UINT64_MAX` 時 `++value` 靜默回繞成 0，rc=0、零警告。

**證據**（`scripts/v11.sh`）：
```
$ echo 18446744073709551615 > .aos/turn && aos exec w
rc=0
turn 之後 = [0]
```
`turn` 的其他每一種壞內容都是大聲拒絕（EINVAL），**唯獨溢位是無聲的**——而 §E-4 明定 `turn` 是要進 git 的「可攜的回合座標」，PC 倒退回 0 卻沒人知道。實務上跑不到 2^64 回合，但手改或位元腐蝕就能觸發。

**建議修法**：`if (value == UINT64_MAX) { error = ERANGE; return false; }`，跟其他壞內容一致地拒絕。
**違反**：與 `run_exec.cpp:98-99` 註解自陳的「讀到壞內容不猜」原則不一致。

---

#### #28｜低｜CONFIRMED｜`core/inst/src/run_loop.cpp:75`

**一句話**：`aos exec --loop` 只對 rc=3 停手，rc=1 被完全忽略——持續性的狀態損壞會讓 loop 永遠空轉。

```cpp
const int result = run_exec_once(folder, did_work);
if (result == 3) return 3;          // 只有這一條會停
```
配合 #9（turn 壞掉每輪都回 1）：loop 會一輪一輪回 1、一輪一輪照跑，PC 永遠凍在原地，沒有任何東西會喊停。鏡頭 3 實測 5 秒 loop 只跑 1 次（因為之後沒事可做，不會暴衝），但「連續失敗不會終止」這個性質本身要補。

**正面副作用**：因為 rc=3 會直接 return，**兩個 `--loop` 打同一世界會很快退化成一個**（實測 2 個 loop ＋ 400 份投遞：只出現 1 次 refusing、遺失 0、重複 0）。真正危險的是被反覆一次性叫起來的 `aos exec`（cron／systemd timer／多個 agent 各自呼叫）。

**建議修法**：M2 loop 層補「連續 N 次 rc=1 就停」，或把「PC 推不動」定為致命。

---

### 已知、已排程，僅量化不列為新發現

**`.runi` 不是鎖（TOCTOU，已排 M2／M3）**——量化後果：

- 隊長量法：500 回合、2–3 支併發 exec，(總執行數 − 投遞數)/回合數 = 22/500 = **4.4%**
- 鏡頭 3 量法：200 回合、2 支併發 exec，**「這一輪的批最後總共被執行超過一次」的回合比例 = 38/200 = 19%**，而且**要跑完 drain 才看得到**（只看併發期間是 0/200，會誤判成沒事）

**以 19% 為準**（那才是「這批跑了幾次」的正確問法），我的 4.4% 低估了。兩次測量都是**零遺失**。

**機制釐清（重要）**：不是 `.runi` 的 claim TOCTOU 直接造成的，而是**兩個 aggregate 各自發布了一次**——A、B 同時 `lstat` 得到 ENOENT 都決定發布，B 在 A 寫出 header 之前讀 header 所以 §D-6 比對不到，B 照樣發布；A 先 claim 執行，B 撞 `.runi` 回 3，**B 那份重複的 `inst.json` 留在原地，下一回合原封不動再跑一次**（實測 29/200 觀察到殘留的 `inst.json`）。

**所以 §D-6 的去重保護的是「投遞殘留」，保護不了「併發雙重彙整」——這是兩件事，§D-6 的「覆蓋範圍」段只提了前者。**

---
## 2. 文件與程式對不上的

| # | 檔案 | 說法 | 實際 |
|---|---|---|---|
| D1 | `docs/SPEC.md` | 三向標記規則說「已裁決且已實作 → 直接寫，無標記」 | **仍有 11 處 `(planned, M1)`**（行 65／68／75／143／173／176／188／193／210／241／246），而這 11 條**全部已實作**。SPEC 第 9 行還寫著「本檔與實作衝突時以本檔為準，**除非該條款帶 planned 標記**」——帶著標記的條款現在反而是最準的。**直接違反 M1 驗收條件 1。** |
| D2 | `docs/SPEC.md:251-263` | §D-9 說「完整對照 (planned, M1)——由實作端實測後收編，**屆時消掉已知未決 #2**」；M1 spec 也說 #3（pid 不唯一）要消掉 | **兩條都還在。** 失敗模式我全跑了一遍（見 §3），資料是有的，沒收編。§D-9 現行表的「1 ＝函式庫層失敗」也涵蓋不了實測到的多數 1（`.aos` 不存在、version 讀不到／不認得、chdir 失敗、resolve 失敗、`advance_turn` 失敗——全是 CLI／世界層）。 |
| D3 | `docs/aos-folder.md:8` ＋ `:227` | 「**這份是規格。**」／「**整個 `.aos/` 都不進 git。**」 | §E-4 的標題就寫著「**（取代 aos-folder 十的「整包不進」）**」，並 MUST 要求 `.aos/version` 與 `.aos/turn` 進 git。檔頭免責說「收編前本檔仍是那幾節的現行規格」，但收編已經在 S1（`dfef513`）發生了。**M1 spec 成品 1 明訂「aos-folder.md 開頭聲明全檔為說明」——未做。** |
| D4 | `docs/usage.md` | 應含 `deliver`（M1 驗收 6 明列） | **完全沒有 `deliver`、沒有 `turn`**（grep 零命中）。檔內的 `aos --help` 輸出只列 `exec`／`init`，實際有五個子命令。`aos init` 那一段說「建立 `.aos/`、`inst.tempd/` 並寫入版本 1」——漏了 `turn`；同一句「整個 `.aos/` 都是本機執行狀態，應加入 `.gitignore`」直接違反 §E-4。 |
| D5 | `core/inst/docs/handoff.md:84` | 「用 `kind` 區分無效投遞、讀取失敗、隔離失敗與發布後刪除失敗」（4 種） | 實際 **7 種**：M1 追加了 `HeaderWriteFailed`、`HeaderInvalid`、`DirectorySyncFailed`。整份 `handoff.md` 對 `deliver`／header sidecar／批 id 去重／fsync 順序**完全沉默**，而 `deliver_instructions` 是這一層新的公開 API。 |
| D6 | `core/inst/docs/capi.md` | 自稱是 C ABI 的完整說明 | `grep -c aos_deliver` = **0**。`aos_deliver_buffer`／`aos_deliver_file`／`aos_handoff_state`／`aos_deliver_result`／`AOS_DELIVER_NAME_MAX` 全部缺席。 |
| D7 | `core/inst/docs/architecture.md` | 描述 inst 的分層 | 對 `handoff_deliver`／`handoff_header`／`.aos/turn`／`inst-head.json` 零命中。 |
| D8 | `wf/workflows/common/code-map.md:97` | 頂層彙總「inbox 怎麼聚合／取件／釋放 → `handoff.cpp`；路徑推導在 `handoff_fs.cpp`」 | 頂層彙總沒提 `handoff_deliver.cpp`／`handoff_header.cpp`／`run_deliver.cpp`／`capi_handoff.cpp`／`turn`／`inst-head.json`。**但葉層 `code-map/inst/{library,capi,cli,tests}.md` 都已同步**——所以鐵律 3 沒有被違反，只是頂層 roll-up 沒刷新。 |
| D9 | `smoke-notes.md` S4 兩節 | 自稱「每一段都是實跑貼上的原文…命令改了就重跑、重貼」，供 S8 直接照抄 | S4 早於 S6（`turn` 落地），那兩節的 `ls -1a .aos` 輸出**沒有 `turn`**。我照同一串命令複跑，實際是 `inst-head.json / inst.tempd / turn / version`。**命令沒改，但世界改了，沒人重跑。** 若 S8 照抄就會寫出錯的文件。（S4 其餘部分——三次投遞、四種拒收、退出碼、canonical 位元組——我逐條複跑，**全部一字不差重現**。） |
| D10 | `core/inst/src/handoff_fs.hpp:50-52` | 「有副檔名、不以點開頭、且**副檔名部分**正好是 `.json`」 | 程式用的是**第一個**點，所以 `a.b.json` 的「副檔名」被算成 `.b.json` 而遭拒。註解讀起來是最後一個點。見 #10。 |

### M1 驗收條件逐條

| # | 條件 | 狀態 |
|---|---|---|
| 1 | SPEC B／D／E 區逐條有編號、位階、來源；grep 無「planned, M1」殘留 | **未達成**（11 處殘留，見 D1） |
| 2 | `aos deliver` 行為與 SPEC D 區一致；同一 process 連續投遞 N 次得 N 份 | **達成**（`test_run_deliver.cpp` 第一案 ＋ 900 次並發實測） |
| 3 | 崩潰窗口測試：彙整完成、刪投遞前中斷，重啟後同一批不會被執行第二次 | **達成**（`test_handoff_header.cpp` 四案 ＋ 我的五狀態手工佈置全部通過）——但只覆蓋彙整段，取件段見 #2 |
| 4 | `.aos/turn`：init 後為 0，跑一回合後為 1 | **達成** |
| 5 | 彙整產出的批旁有 header sidecar，四欄位齊 | **達成** |
| 6 | ctest 全綠（含新測試）；code map 同步；`docs/usage.md` 補 deliver | **部分**：ctest 4/4 綠 ✓；code map 葉層同步 ✓ 頂層未刷新（D8）；**usage.md 完全沒有 deliver ✗** |
| 7 | 文件裡寫的每條指令與輸出都真的跑過 | **部分**：smoke-notes 的 deliver 段我複跑全部重現 ✓，但 S4 的 `ls .aos` 已因 S6 而失效（D9） |

---

## 3. 對抗驗證做了哪些、各自結果

**沒打出問題的也全部列出——那是證據。** 腳本在 `scripts/`。

### 打出問題的

| 驗證 | 手法 | 結果 |
|---|---|---|
| 同名同內容重投 | 固定檔名生產者連投 3 回合；`aos deliver` 產物放回 inbox | **#1** 靜默丟批 |
| syscall 順序 vs §D-5 | 自寫 LD_PRELOAD 攔截器（本機**沒有 strace／ltrace**） | 彙整八步**完全正確**；**#2／#5** claim／release 無 fsync |
| inbox 混入 FIFO | `mkfifo pipe.json` ＋ 正常投遞 | **#3** rc=124、一份都沒處理、6 個行程疊著卡 |
| `inst.json` 是斷 symlink | `ln -s /nonexistent/gone` | **#25** rc=0、stderr 空、投遞無限堆積 |
| header 寫失敗＋投遞刪失敗 | `.temp` 佔成目錄 ＋ inbox chmod 500 | **#26** 每回合重跑，1→2→3 |
| header 巢狀 `"id"` | 手造巢狀物件雙向 | **#4** A 向靜默丟批、B 向重跑 |
| 去重命中＋無關 `.temp` | 手工佈置 | **#21** 無關殘骸被扶正執行 |
| `.runi` 存在時的行為 | 預放 `.runi` 再跑 exec | **#6** 先完成整輪彙整才回 3 |
| 同名壞投遞連續兩次 | 兩份不同內容的壞投遞同名 | **#7** 第一份 `.bad` 被無聲覆蓋 |
| 合法投遞讀不到 | `chmod 000` | **#8** 被貼 `.bad`、永久出局 |
| `turn` 內容壞掉 | `abc` 等 8 種壞內容，連跑 3 回合 | **#9** 每輪 rc=1 但持續做事 |
| `turn` = UINT64_MAX | 手改 | **#27** 靜默回繞成 0 |
| 多點檔名 | `2026-08-28.report.json`、時間戳命名 | **#10** 永久靜默忽略 |
| `aos init` 的 fsync | trace ＋ 讀碼 | **#12** 父資料夾從未 fsync |

### 打了但沒有問題的（證據）

| 驗證 | 規模 | 結果 |
|---|---|---|
| 彙整 fsync 順序 | LD_PRELOAD 全序列比對 §D-5 七步 | **一字不差** |
| 崩潰狀態機 | 手工佈置 5 個狀態 | **S3 提交點論證成立**：狀態 1 roll-forward 跑一次；狀態 2 只清投遞不重跑；狀態 3 正常重發；狀態 4（`.temp` 殘缺）不 roll-forward 不重複；狀態 5 跑一次且**下一回合自癒** |
| §D-6 明講不保證的那條 | 舊投遞殘留 ＋ 新投遞混入 | **恰如條款，不比條款更糟**：OLD 跑第二次，**NEW 有跑到、沒被吃掉** |
| 50 並發 deliver | 50×10 輪 ＋ 不清空連投 8×50 = **900 次** | 零丟失、零撞名、零 `.temp` 殘留 |
| deliver／exec 交錯 | `--loop 1` 常駐 ＋ 1 流×300 與 4 流×200 = **1100 筆** | **遺失 0、重複 0、stderr 0 行** |
| 併發 exec 逼批遺失 | 300 回合 × 3 支併發，每回合不同 payload | **300/300 全部執行、0 遺失** |
| ENOSPC（真的） | `unshare -Urm` 掛 64KB tmpfs | **最乾淨的一塊**：不留殘骸、不吞投遞、不重複執行、init 失敗回收半成品世界 |
| EXDEV | 四種跨檔案系統組合 | **結構上不可能發生**。額外好性質：claim 的 rename **不跟隨 symlink** |
| 權限不足 | inbox／`.aos`／`inst.json`／header 各種 chmod | 錯誤訊息全帶路徑與 `strerror`，可診斷性好 |
| exec 進行中投遞 | 子行程 sleep 期間 deliver ＋ 100 份湧入的壓力版 | 新投遞完整保留到下一回合，遺失 0、重複 0 |
| 符號連結／斷連結／目錄 | 三種異物 | 全部正確隔離；符號連結只改名連結本身，**沒動到 `/etc/passwd`** |
| `.temp` 殘檔＋既有 `.bad` | 三者同在 inbox | 兩者原地不動，正常投遞照吃 |
| 零長度／空白／只有 LF／`[]` | 五種 | 前三種 `JsonSyntax` 隔離；`[]` 消化不寫 header（刻意分支） |
| 檔名含空白／UTF-8／240 字元 | 三份 | 全部正常收取，排序正確，0 殘留 |
| 超大批次 | 5000 筆／單筆 10MB argv／100 萬層巢狀 | 都正常；100 萬層巢狀沒爆堆疊（`NotAnObject`） |
| header 損壞 | 九種（截斷／空檔／id 非字串／null／空字串／二進位／無 id／轉義 `\"id\"`） | **全部只往「多跑一次」倒，不往「吃掉投遞」倒**——失效方向正確 |
| `aos init` 重跑 | 有狀態的世界 | turn／`inst.json`／`.runi` 三個檔 md5 前後一致 |
| `.aos/version` 異常 | 七種 | exec 與 deliver 兩側全部 rc=1，且都在 aggregate 之前擋掉 |
| `.bad` 不自動刪 | 連跑三輪 | 每輪都在、也不會被再讀（§D-8 ✓） |
| §C-8「exec MUST NOT 認識 header」 | grep exec 層三個檔 | **零命中**，§A-6 推論守住 |
| C ABI 凍結規則 | `git diff dfef513^..b5cc35a -- inst.h` | **全部尾端追加**，無插值無重排無改值 |
| `static_assert` 覆蓋 | `capi_handoff.cpp:20-37` | `aos_handoff_state` 0–9 十個鏡射值全有 assert；10–12 是 C-only 延伸 |
| 分層違規 | grep handoff* 的 include | 只有 `<aos/inst.hpp>`、自家內部標頭、系統標頭 |
| `next_delivery_name` fork／多執行緒 | 讀碼 ＋ 並發實測 | `fetch_add` 保證行程內唯一；`getpid()` 每次現取，fork 後不撞名；relaxed 足夠。**這一項沒有缺陷** |
| 摘要框架 | 讀碼 ＋ 實測 | `'\0'` 框架對檔名側嚴密；內容側的 raw NUL 會被唯一 parser 擋成 `JsonSyntax`。64-bit FNV 生日界約 2^41 批 |
| 錯誤路徑 temp 清理 | 逐個 early return | 五處 unlink 都在；批 rename 失敗時**刻意**留 `.temp` 當 roll-forward 素材 |
| smoke-notes 複跑 | S4 deliver 全段 | 全部一字不差重現（唯一落差是 D9） |
| 退出碼全表 | 12 種失敗模式 | 0：無批／子行程非零／指令不存在／重導向開不起來。1：解析失敗／resolve 失敗／exit 檔寫不進／不是世界／advance_turn 失敗。2：用法錯誤／不存在的子命令。3：`.runi` 已存在 |
| 資源邊界（非缺陷） | 5000 筆 `parallel:true` | 615/5000 `SpawnFailed: ENOMEM`（第一個失敗在 record 4384），**逐筆誠實回報、不當機、不留殘骸**。§C-7 明說不設上限，這是資源自然邊界；使用者該知道門檻約在四千多筆 |

---
## 4. 審查沒覆蓋到的角落（誠實列）

1. **真正的斷電**。所有崩潰狀態都是「手工佈置等價的檔案系統狀態」，不是真的 power-loss。#2／#5／#12／#15 導致的重排是**可能發生**而非**必然發生**（ext4 `data=ordered` 常常會順帶落盤），觸發機率沒有量化。要真證需要 dm-flakey／`CONFIG_FAIL_MAKE_REQUEST` 或 VM 硬切電。
2. **檔案系統差異**。多數測試在 `/tmp`（tmpfs），**tmpfs 的 fsync 是 no-op**，所以驗的是「有沒有發這個呼叫」而不是「落盤語意對不對」。鏡頭 3 有補 ext4 的跨 fs 測試，但 xfs／9p／drvfs 沒碰。
3. **`publish_exclusive` 的 `link+unlink` 退路**。tmpfs 與 ext4 都支援 `RENAME_NOREPLACE`，正常情況下這條分支**一次都沒被自然執行到**。#11 的執行期證據來自 `scripts/fault.c` 的故障注入，我複驗了程式碼路徑但**沒有獨立重跑注入器**。NFS／FUSE 上值得補測。
4. **pid 重用真的發生**。本機 `pid_max=4194304`，600 次投遞消耗約 1200 個 pid、無重複，換算約 200 萬次投遞才繞一圈。#1 的 `aos deliver` 自然觸發路徑沒實測到；我用手寫的同名檔重現了機制本身（aggregate 只看檔案系統，等價成立），**自然觸發率只有估算**。要實測可在 namespace 裡把 `pid_max` 調到 1000 再跑。
5. **`--loop` 模式的完整行為**。turn 遞增、SIGINT 時序、#9 的「每輪回 1 但不停」只做了短時間觀察；長跑沒做。
6. **`.temp` 交錯寫的真實重現**（#23）。原語已用 `trunc_demo.py` 證實（291/300 破損），但在真的 `aos` 上打了 220 輪都沒中。要 CONFIRMED 需要 `ptrace`／`LD_PRELOAD` 注入延遲。
7. **`.aos/insts/` 底下的其他 CPU**。庫層支援（三支 handoff API 都吃 `instruction_path` 參數，`test_handoff.cpp` 有 `llm-head.json` 案例），但 CLI 沒有任何選項指得到它，**沒有從命令列這一側驗過整條協定**。與 `aos-folder.md` 自承的「還沒實作的只有 insts/」一致。
8. **`aos deliver` 的 C ABI 執行期**。讀了宣告與 `static_assert`，`test_capi.c` 的既有案例由 ctest 覆蓋，但**沒有另寫 C 程式實跑** `BUFFER_TOO_SMALL` 那條分支。
9. **`parallel` 執行緒下的 exit 檔 fd 洩漏**（#13）。由旗標與 `std::thread` 用法**推導**，沒有實跑複現那個時間窗。
10. **不在鏡頭內的區塊**：SPEC A 區、C 區（§C-1～§C-7、§C-9）、§E-2 footprint、§E-3 快照回滾，以及 `resolve.cpp`／`spawn_prep.cpp`／`format_*.cpp` 的內部正確性，完全沒碰。
11. **`aos exec` 撞上 `.runi` 的 19% 是這台機器在這個負載下的數字**，換機器／換批次大小會變。

---

## 5. 需主線裁決的三件事

其餘 25 條大多是機械修法或條文措辭，不需要重新想設計。以下三件**必須先裁**，因為它們決定「這是修實作還是改條款」。

### 裁決一：`inst-head.json` 的批 id 該不該在批被取走時失效？（對應 #1）

**問題**：目前 id 是內容導出的（FNV-1a over 排序後的 檔名＋內容），且批被消化之後永不清除。這讓去重分不出「崩潰殘留」與「內容相同的全新投遞」，後者被靜默刪除。

**為什麼會走到這裡**：verdicts A 表自己記過——「批 id＝FNV-1a 摘要兼去重依據（**隨機 id 需名冊＝manifest，與「manifest 留 v2」相撞**）」。也就是說，選內容導出的 id 是為了避開 manifest；而內容導出的 id 在原理上就分不出殘留與重投。**這個取捨被記錄了，但它的反向代價沒有被記錄。**

**我的建議：修實作，走「sweep 標記」，不要引入 manifest。**
在 `remove_accepted_deliveries()` 全數成功且目錄 fsync 成功之後，把 header 改寫成帶 `"swept":true`（或直接刪掉 header）；去重比對時**只有 `swept` 不成立**才啟用。

**理由**：
- 殘留的定義本來就是「sweep 沒完成」，所以這個判準精確對應 §D-6 的立法意圖，不多不少。
- 不需要 manifest，不牴觸「manifest 留 v2」。
- 成本是一次額外的小檔改寫，只在成功清完投遞後發生，不在熱路徑。
- 若不想動實作，**最低限度也要**：命中去重而刪投遞時 MUST 噴 warning，並在 §D-6 補一句承認「內容相同的重投會被誤判」。靜默是這條最貴的部分。

### 裁決二：§D-5 的耐久性射程要不要從「發布」延伸到「取件／釋放」？（對應 #2、#5）

**問題**：§D-5 立法的是「彙整耐久性與提交點」，字面只管彙整；實作也只在彙整段做了完整的 fsync 鏈。但 §D-7 說「`.runi` 存在 ⟺ 有一回合沒跑完」，這個等價關係要成立，取件的 rename 就必須是耐久的。目前它不是，釋放的 unlink 也只是被 `advance_turn` 順帶救到——而 §B-3 說 turn 在 M2 要搬到 loop 層，搬走這個巧合就沒了。

**我的建議：延伸，而且現在就補。**
`claim_instruction` 在 rename 後補 `fsync_dir`，`release_instruction` 在 unlink 後補 `fsync_dir`，失敗都比照 aggregate 記 issue 續行（不要讓耐久性失敗卡住世界）。§D-5 標題從「彙整耐久性」改成「交接耐久性」，涵蓋三步協定全部。

**理由**：
- 兩行程式碼，沒有設計風險。
- 不補的話，M1 spec 驗收 3 宣稱的「同一批不會執行兩次」在**副作用已經發生**的那個方向是假的——而那正是最貴的方向。
- 釋放那一條是 latent regression：M2 搬走 turn 的人不會知道自己順手拆掉了一個耐久性保證。現在補掉就永遠不會發生。

### 裁決三：`aggregate` 的批發布要不要改成排他？（對應 #23、併發雙重彙整、19% 重複執行）

**問題**：§D-4 說「`inst.json` 已有一份沒被讀走時本輪 MUST NOT 發布（不覆蓋、不合併）」，但實作只靠開頭一個 `lstat` 擋（check-then-act），發布用的是覆蓋語意的 `rename`，`.temp` 還是固定名 ＋ `O_TRUNC` ＋ 非排他。`handoff_fs.hpp:42` 的註解明說這是刻意保留原樣的。

**我的建議：改成排他。這是這份審查裡投報率最高的單一修改。**
批 `.temp` 改用**每行程唯一的名字**寫（比照 `next_delivery_name()`），最後用**既有的** `detail::publish_exclusive()` rename 到 `inst.json`；`EEXIST` 就代表別人先發布了，本輪放棄、**不清投遞**。

**理由**：
- **一刀解三個問題**：(a) #23 的固定名 `O_TRUNC` 共寫（原語已證實 291/300 會產生帶 NUL 的破損內容，而破損批會依 §D-7 靜默消失＝資料遺失）；(b) 併發雙重彙整（19% 重複執行的真正機制）；(c) §D-4「MUST NOT 覆蓋」從願望變成真的被 enforce。
- **不需要引入鎖**，也不牴觸「`.runi` 不是鎖」那條已排 M2／M3 的 gotcha——這是發布路徑的排他，跟取件的互斥是兩件事。
- `publish_exclusive()` **已經寫好、已經在 deliver 用、已經有退階路徑**，是現成零件。
- 順帶要補條款：§D-6 的「覆蓋範圍」段目前只聲明「只保證整組殘留」，應加一句明說**去重不保護併發雙重彙整**——因為 B 在 A 寫出 header 之前讀 header，比對本來就不可能命中。

---

## 附錄：scripts/ 對照

| 腳本 | 用途 |
|---|---|
| `trace.c` | LD_PRELOAD syscall 攔截器（本機無 strace 的代替品）。`gcc -shared -fPIC -O0 -o trace.so trace.c -ldl`，用 `AOS_TRACE_LOG=... LD_PRELOAD=.../trace.so aos exec W` |
| `fault.c` | 鏡頭 2 的故障注入器（`FAULT_NO_RENAMEAT2`／`FAULT_UNLINK_TEMP` 等） |
| `fstrace.c` | 鏡頭 2 的另一版 syscall 追蹤 |
| `trunc_demo.py` | #23 的原語證明：兩行程並寫同一個 O_TRUNC 固定路徑 |
| `t1.sh` `t3.sh` `t15*.sh` | #1 陳舊 header 靜默丟批 |
| `t4.sh` | §D-5 syscall 順序比對 |
| `t9.sh` `t10.sh` | 崩潰狀態機五狀態 ＋ §D-6 殘留混入 |
| `t7.sh` `t8.sh` `t11.sh` | 並發 deliver／交錯／批遺失壓力 |
| `t9b.sh`–`t9f.sh` | 併發 exec 重複執行率、`.temp` 共寫 |
| `v1.sh`–`v11.sh` | 隊長的複驗與補測（含 #25／#26／#27／#21 的重現） |
| `tx.sh` `ty.sh` `tz.sh` | 鏡頭 3 的 FIFO／斷 symlink／多點檔名 |
| `t1_inner.sh` | `unshare -Urm` 底下的真 ENOSPC |
| `s0*.sh` `s1*.sh` `probe.cpp` | 鏡頭 2 的狀態機與探針 |

**回歸測試建議**：`t3.sh`（#1）、`v11.sh`（#25／#26／#27／#21）、`v7.sh`（#3）、`v8.sh`（#4）最值得優先變成 ctest 案例——它們都是確定性的、不需要併發、跑得很快。
