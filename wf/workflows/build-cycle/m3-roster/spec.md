# M3 名冊補完：status／recover／check — 規劃 spec

← [build-cycle](../README.md)｜[roadmap M3](../../roadmap.md)｜[SPEC](../../../../docs/SPEC.md)

**閘門 ①／② 由使用者概括授權**（2026-08-28 `/goal`：調度者統籌、一路做到完全）。
先裁的問題由主線依下列方向拍板，落檔時記入 [verdicts A 表](../../ideas/verdicts.md)
＋ `docs/SPEC.md`。

> **調度者裁決（2026-08-28，實作層級；plan 第一節 36 項未列者一律採建議案）**：
> check 的 MUST 違規用**新退出碼 5**（§D-9 加列）；共用層**新開 `core/world`**（`PUBLIC_DEPS aos::inst`，
> `core/loop` 本輪不動）；版面 helper 七個從 `core/inst` 內部標頭**升為公開 C++ API**（非 C ABI）；
> **名冊＝子命令名冊** `init/exec/deliver/status/recover/check`（`loop` 挪出、`init` 補進，
> `tooljson`／`llms` 進封閉豁免清單）——roadmap M3 段那六個名字照此更正；`deliver --control` **加**，
> 條文限定只驗「恰好一個 key `op`」、輸出不帶 `count`、投 `control.tempd/`；**診斷豁免**照建議
> （唯讀面 MUST 能在 `version` 缺席／不認得時運作，recover 寫入 MUST 拒絕，三支 MUST NOT 回 3／4）；
> forensic 副本 **`.aos/recover.d/<turn>-<utc>-<seq>.d/`、進 git**；status 五個封閉狀態字
> `layout-invalid/runi/ready/pending/no-work`；條款分區 §A-9／§B-5／§B-6／新開 **H 區**。
> **已知未決 #1（SIGINT 續跑）不裁**——建議「M3 裁掉、處置歸 recover」是合理的，但那是使用者的方向，等他表態。
> 動工前提：M2 落地後先核 plan 第零節 16 條假設。

> **本階段建立在 M2 之後的世界**：`core/loop`、header `result` 四值、
> `.aos/control.tempd/`、退避、SPEC G 區、退出碼 4 都以
> [m2-loop-project/plan.md](../m2-loop-project/plan.md) 第五節「動哪些檔」為準。
> [plan](plan.md) 第零節列了 **16 條「對 M2 落地結果的假設」**，M2 落地後由實作隊
> **逐條核對**、不符就改 plan。

## 一句話

把這台機器**留下的靜態狀態**與**它自己的規範**變成可機械查詢的東西：補上
**`status`**（世界現在停在哪一格，唯讀投影）、**`recover`**（崩潰殘留怎麼收，人明示
才動手）、**`check`**（這個世界合不合 SPEC，每筆違規帶條款編號）三支子命令；同時把
**程式名冊封閉**（§29）、**版面 ownership table**（§28）、**版面版本的 bump 判準**
（B10 的另一半）寫進 SPEC——**M3 之後，「aos 有哪些子命令」與「`.aos/` 每條路徑誰能動」
都從 open question 變成條款**。

---

## 本階段裁決（主線裁，七項，方向已定不翻案）

### 裁決 1 — §29 接受：名冊封閉，判準＋窮舉表，衝突時表優先

**判準（可直接抄進 SPEC）**：

> 一件事需要一支 `aos` 子命令的**充要條件**是：它必須由**外部方**（人或外部程式）執行，
> 而且**它必須運作的那個時刻，沒有任何一個可用的回合能承載它**。

這是 §25／M2 §A-7「歸 loop 的充要條件＝必須在沒有任何 inst 可跑的時刻運作」的**同一個
測試往外推一層**。測試怎麼跑：問「這件事能不能做成一筆 inst、投進去讓某個回合跑掉？」
——能 → **系統 inst**（這台機器上的 OS），**MUST NOT** 開子命令；不能 → 候選，再對
窮舉表核一次。

**窮舉表（名冊本體，到此封閉）**：

| 格 | 為什麼「做不成 inst」 | 落在這格的 |
|---|---|---|
| **0 世界的存在** | 世界**還不存在**：沒有 `.aos/`、沒有收件匣可投、沒有 `version` 可讀 | `init` |
| **1 推進本身** | 推進回合這件事不能由回合推進（自舉不成立）。`--loop` 是同一支的持續模式 | `exec` |
| **2 外部方執行的協定步驟** | 投遞是**回合的入口**；要靠回合完成投遞，就得先有東西被投進去 | `deliver` |
| **3 靜態狀態的 inspector ＋ repairer** | 最需要它們的時刻正是**回合跑不動**的時刻（`.runi` 卡住、`aos exec` 退 3、loop 死掉） | `status`／`recover` |
| **4 規範的 validator** | 它要回答「這個世界合不合法」；**在答案是「不合法」的世界裡沒有任何回合會跑** | `check` |

**名冊 ＝ `init`／`exec`／`deliver`／`status`／`recover`／`check`，六支，到此封閉。**
**判準與表衝突時以表為準**（M2 的教訓：判準推不出它自己的列舉，別讓判準單獨承重）。

**三條範圍句（缺一條，名冊條款當天就自相矛盾）**：
1. **名冊封閉的是「會讀寫 `.aos/` 的子命令」**。`aos` 執行檔上還掛著 `tooljson`／`llms`
   （實跑 `--help` 確認；`grep .aos` 兩者零筆），使用者已判定為失敗作
   （[ideas README](../../ideas/README.md)：「之後要找時間改到符合」）。它們進一份
   **封閉的豁免清單**，**MUST NOT** 增長、**MUST NOT** 被引為新增子命令的先例；
   M3 **不刪、不改、不搬**它們。
2. **名冊是子命令名冊，不是小專案名冊**。`loop` 不是第七個名字——M2 已定「小專案獨立
   ≠ 命令獨立」，`aos exec --loop` 背後連的是 `core/loop`。**新增小專案不是修憲**
   （否則 M3 自己要開的 `core/world` 就得先修憲才能討論）。條文要明說「§29 原文把
   `loop` 列進名冊，本條把它挪出、改列為 `exec` 的實作」。
3. **`init` 補進名冊**。§29 的六個名字**漏了它**——`aos init` 今天就存在，§B-3／§B-4／
   §D-9 都在條款裡點名它。漏的是清單不是程式；roadmap M3 段照抄了那六個名字，已經
   傳染一層，一併更正。（§29 從協定推名冊，而 `init` 不在交接協定裡——它建的是協定的
   **場地**，所以要補「格 0」這一格。）

**修憲門檻（要加第七支要過的關，四條全部滿足才成立）**：
1. **MUST** 證明它**做不成 inst**（不能只是「做成 inst 比較麻煩」）；
2. **MUST** 指出它落在窮舉表哪一格，或提出新增一格的理由；
3. **MUST** 同一個 commit 內改 SPEC 的名冊條款、`docs/usage.md`、code map；
4. **MUST 經使用者點頭**（SPEC 開頭：條款的新增、修改、位階變更 MUST 經使用者點頭，
   AI 不得自行修憲）。

**回歸守門（可機械檢查）**：`aos --help` 列出的子命令集合 ＝ 名冊窮舉表 ∪ 豁免清單。

### 裁決 2 — `deliver --control` 加，且條文一併限定三件事

M2 把「`deliver --control` 旗標要不要加」留給 M3 跟 §29 一起裁。**裁：加。**

**過門檻的推導**：投控制記錄正是格 ②「外部方執行的協定步驟」——M2 §G-7 已明寫控制面
走投遞協定、先 `.temp` 後 rename、檔名比照 §D-2，與 `deliver` **同構**。而 §D-3 的立法
理由（layout-and-spec §11：投遞是「整套協定裡**最容易寫錯**的一步，也是唯一沒有實作
提供的一步」）**逐字適用**於控制記錄。它**不是新名字**，名冊不變。

**條文 MUST 一併限定三件事**（這三條同時消解三個反對理由，缺一條這個裁決就不成立）：
1. **驗證範圍**：`--control` **MUST 只驗「這是一份恰好一個 key `op`、值為字串的 JSON
   物件」**，**MUST NOT** 判斷動詞合不合法（動詞的認定歸回合層，§G-7 已規定不認得的
   `op` → 隔離 `.bad` ＋ warning ＋繼續）。
   → 於是沒有第二套 schema（不違反 §A-6），**而且 `core/inst` 不需要知道 loop 的動詞
   集合——沒有反向相依**（否則會被 CMake 的相依環直接擋下）。
2. **輸出契約**：stdout **MUST** 是單行 JSON `{"delivery":"<檔名>","target":"control.tempd"}`，
   **MUST NOT** 帶 `count`（`count` 是「批內筆數」，控制記錄不是批）。
3. **目標匣與其餘行為**：投 `.aos/control.tempd/`；唯一檔名、先 `.temp` 後 rename、
   排他發布、inbox 不存在就報錯不自動建——**MUST** 與 §D-2／§D-3 完全相同。

**時序**：**條款在 M3 裁定並入 SPEC**；**實作可以排在三支主線之後**（它不擋 status／
check／recover）。§29 的門檻今天就得裁——不然 M3 之後每次有人想加旗標都要重問一次。

### 裁決 3 — 三支工具的分界：投影／驗證／修復，各管一句話

| 子命令 | 一句話 | 它**不**回答 |
|---|---|---|
| **`status`** | **現在停在哪一格**——把 `.aos/` 投影成一份結構化的當下狀態，回答「接下來 `aos exec` 會做什麼」 | 合不合法（check）、該怎麼修（recover） |
| **`check`** | **合不合 SPEC**——逐條驗版面與 schema，**每筆違規帶條款編號** | 現在在哪一格（status）、幫你修（recover） |
| **`recover`** | **崩潰殘留怎麼收**——列出可修項、證據與建議動作，人明示動作才動手 | 世界正常時的狀態（status）、規範違反（check） |

可引用的一句：**status 問「這個檔在不在、裡面是什麼」；check 問「這個檔對不對、違反哪
一條」；recover 問「這個殘留怎麼收、證據夠不夠」。** 同一個路徑可以同時出現在三邊——
**刻意的重疊是設計不是冗餘**（把它們硬拆成互斥會逼人跑三次才知道一件事）。

**三條硬約束**：
1. **`status` 與 `check` MUST NOT 改世界**：不建檔、不建目錄（含 `control.tempd/`）、
   不把不合法命名的項目改名成 `.bad`（隔離是彙整的權責 §D-4）、不動 `.bad`
   （清理是人或 recover 的權責 §D-8）、**不求值任何指示詞**（§C-4；求值要讀 `$ref`
   指到的檔，既擴大唯讀面又可能失敗）。這條要能被機械驗（驗收條件 3）。
2. **`recover` 不帶動作旗標時 MUST 唯讀**：預設是「列出可修項＋證據＋建議動作」。
   **MUST NOT** 自動重播批次、**MUST NOT** 猜子行程有沒有跑過。
3. **三支都 MUST NOT 推進回合、MUST NOT 觸發彙整**。

### 裁決 4 — 診斷豁免：三支工具的**唯讀面**在版面不合法時 MUST 仍然運作

§B-4 現行條文是「`.aos/version` 讀不到 ＝ 不是合法 `.aos`，**MUST** 拒絕；版本不認得
＝ **MUST** 拒絕」。**那條約束的是「要對這個世界動手」的操作**（`init`／`exec`／
`deliver`——實跑確認三者都回 1）。三支工具存在的理由**正好就是**診斷壞掉的世界。

**裁**：§B-4 加一句診斷豁免——

- **`status`／`check`／`recover` 的唯讀面 MUST 能在 `.aos/version` 缺席或不認得時繼續
  運作，並把該事實當成輸出報告出來，MUST NOT 據此拒絕啟動。**
- **`recover` 的任何寫入動作 MUST 拒絕**（版面版本讀不到＝不知道自己在修哪一版的版面）。
- 分界的操作型定義：**「這支程式有沒有印出一份完整的報告」**——世界壞了但報告得出來
  ＝ 0；連 `.aos` 都進不去（沒有可報告的內容）＝ 1。

（這是**修憲**，走閘門，主線點頭後才動。隊員之間對「status 遇到不認得的版面該回 0
還是照 §B-4 拒絕」有分歧，本裁決採「唯讀可診斷、寫入才拒絕」——理由是那條線同時
解釋了 recover 為什麼可以看卻不能修，一條規則管三支。）

**同理，三支 MUST NOT 回退出碼 3**：3 的意義是「拒絕啟動」（§D-9 涵蓋欄寫「只有
`aos exec`」），而 `.runi` 對 status 是**要報告的內容**、對 recover 是**它該出手的理由**
——讓 recover 回 3 等於讓 fsck 拒絕檢查一個壞掉的檔案系統。M3 **MUST** 把 §D-9 那一列
的「只有 `aos exec`」明確化為「只有 `aos exec`（含 `--loop`）」。三支也 **MUST NOT**
回 4（M2 已把 4 給 loop）。

### 裁決 5 — `recover` 的三條設計原則（T5 的教訓，直接入法）

1. **不重做彙整層已經在做的事。** header／批 不一致的 roll-forward **今天由
   `aggregate_instructions` 每一圈做**（§D-6 的批 id 比對）。分工線是實測畫出來的、
   不是設計出來的：**投遞還原封不動躺在 inbox → 彙整層自癒，recover MUST NOT 碰；
   投遞已不在 → recover。**（實測：§D-5 的五個崩潰點在投遞還在時一圈 `aos exec` 全部
   自癒；投遞不在時跑幾圈都不動。）
2. **孤兒批 `.temp` MUST NOT roll-forward**，即使它看起來是一份完整的批——沒有投遞
   佐證就無法判定它跑過沒有，rename 它＝重播一個來歷不明的批。對它只有兩個合法動作：
   **列出**與**進 forensic 副本後刪除**。
3. **證據不足時預設停住**（T5 原話），要人明示動作旗標；`--replay` 另外要 `--force`。
   **每個動作 MUST 先建 forensic 副本才動世界**，副本建不起來 **MUST** 中止。

### 裁決 6 — 三支共用一個唯讀的「世界檢視」層，且它 MUST NOT 解讀回合層語意

三支工具讀的是同一份版面。**MUST** 共用同一份版面知識（路徑常數、`version` 判定、
`turn` 讀取、收件匣掃描與分類、header 讀取），**MUST NOT** 各寫一份——`check` 的存在
理由是「三份真相收斂的機械手段」（layout-and-spec §12／§29），**它不能自己是第 N 份
真相**。

**防環規範（跟共用層同等重要）**：這一層 **MUST NOT** 解讀回合層的語意——header 的
`result` 與 control 記錄的 `op` **一律原樣以字串傳遞**，由呼叫端處理（`status --json`
直接吐出；`check` 依 SPEC 的值域表比對）。理由：那兩份字面表的唯一來源在 `core/loop`
（M2），共用層一旦要解讀它們就會產生反向相依、變成相依環。**值域住在條文裡，不住在
程式碼裡**——這正是「每份規範→validator」的直接應用。

（共用層**放哪個小專案**、要不要開 C ABI，由 [plan](plan.md) 第二節提案、主線裁。）

### 裁決 7 — ownership table（§28）、版面版本 bump 判準（B10 另一半）、命名例外，一起進 SPEC B 區

- **ownership table**：`.aos/` 每條路徑一列，標**誰建／誰寫（唯一 writer）／誰讀／誰刪／
  進不進 git**（對照 §E-4）＋對應條款；角色詞彙封閉。**「建立者」與「writer」是兩件事**
  （`init` 建 `turn` 並寫初值，之後所有權交回合層——分兩欄就是為了不讓這種交接被誤讀成
  雙 writer）。**鐵律：每條路徑 MUST 有唯一 writer**；有兩個 writer 的路徑 MUST 在表裡
  標明並寫出處置（§28：那就是未來損壞的準確位置）。
- **版面版本 bump 判準**：操作型定義＝**舊 aos 遇到新版面會不會做錯事**（不只是「看不
  懂」——「看不懂就拒絕」是 §B-4 已經保證的安全網，bump 要防的是**它以為自己看得懂**）。
  三問任一為是就 MUST bump；純新增有充要條件（含「舊 aos 的動作最多只讓新機制**降級**、
  MUST NOT 產生新的錯誤狀態」這一條）。`turn`／`inst-head.json`／`control.tempd/` 三個
  既裁的純新增，逐條過帳寫進條文當 worked example。
- **`check` 依 `.aos/version` 決定套哪一版規則集；v1 是目前唯一的一版**——語意預留
  是零成本的（今天的實作照樣是一個相等比較），未來加 v2 不用修憲。
- **三個版本數字一段話釘死**（進 §F-2）：**版面版本**（`.aos/version`）／**格式版本**
  （header 的 `version`）／**輸出 schema 版本**（`status --json`／`check --json` 輸出裡
  的版本欄，M3 新增）——**三件不同的事，互不相關、互不遞增、MUST NOT 被同一個決定
  同時動到**。第三個與世界的狀態完全無關。
- **三個命名例外承認為封閉清單，不改檔名**：`version`／`turn`（無副檔名＝單值標量檔，
  §B-3 已把 `turn` 稱為「這台機器的 PC」）、`insts/`（無 `.d` ＝命名空間目錄，不是一種
  資料格式）。理由：改 `version` 的檔名會讓**每一個既有世界依 §B-4 立刻變成非法世界**
  ——那是 bump 判準的教科書案例，拿「全世界都要 migrate」換「命名一致」不划算。

---

## 調度者須知（讀程式碼與實跑挖到的，**裁決本文一律不改**）

> 前四條是**實測**挖到的、今天真的存在的行為，全部影響 M3 的規格；第 1 條還會回頭
> 影響 M2 的實作。

1. **`inst-head.json` 是唯一的雙 writer，而且已經有一個真實的損壞窗口——M2 as-planned
   沒防。** `aggregate_instructions()` 判斷「要不要發布」只 `lstat(inst.json)`，
   **不看 `.runi`**；而 `run_exec` 的順序是 **aggregate 先、claim 後**。所以第二支
   `aos exec` 會在批 N 還在跑時發布批 N+1 並**覆蓋掉批 N 的 header**，然後才因 `.runi`
   退 3。**今天的後果**：header 描述的批 ≠ `.runi` 裡的批（直接打到 `status` 要怎麼報
   「現在跑的是哪一批」）。**M2 之後的後果**：writeback 把 `result` 蓋到**錯的 header**
   上。處置成本近零（writeback 前用既有的 `decode_header_id()` 比對 `id`，不符只
   warning，不寫）——**這條要優先回報 M2 實作隊**，M2 願意順手收的話 M3 就只剩條文。
   注意它與 M2 §G-2 那句「退避的判準 MUST NOT 要求先讀回 header」**不衝突**：退避用的
   還是回合層自己算的結果，讀 `id` 只是為了確認「這份 header 還是不是我的」——條文要
   把兩件事分開寫。

2. **「回 3 的那一次 `aos exec` 也改了世界」。** 承上：`.runi` 在、`inst.json` 不在時，
   `aos exec` 仍然先彙整發布一份新的 `inst.json` ＋覆蓋 `inst-head.json`，然後才撞
   Busy 回 3。**於是 T5 教的恢復手法 `mv .runi inst.json` 會靜默吃掉剛彙整的那一批。**
   `recover --replay` **MUST** 有「落點被佔住」的拒絕分支。三支工具 MUST NOT 有這個
   行為——**這正是為什麼唯讀要寫成條款而不是靠實作自覺**。

3. **兩個「無聲失效」的坑，M3 是第一個能讓它們發聲的東西**：
   - **`.aos/turn` 內容壞掉 ＝ 永久回 1 的世界**：五種壞法（無尾 LF／空檔／非數字／
     負號／u64 溢位）之下，批**照常跑完、`.runi` 照常釋放**，只有 `turn` 遞增失敗讓
     `aos exec` 每次回 1，`turn` 永遠停在壞值，**沒有自癒路徑**。M2 之後它會變成連續
     `machine_failed` → 退出碼 4 停機（症狀變明顯，病因還在）。
   - **投遞匣的不合法命名被靜默忽略**：`name.part.json`／`noext`／`x.json.runi`／
     子目錄全被 `is_delivery_name` 忽略，**零 warning、`aos exec` 回 0**——那份工作
     永遠不會跑，而今天沒有任何機制會告訴人。這是 `check` 最有價值的一條驗證項。

4. **`status` 判定不出「外部作用發生了沒」，M2 之後也判定不出來。** T5 的
   `unknown-effect` 想抓的組合（子行程可能已跑過但沒有 exit 證據）在今天的版面**沒有
   證據可據**：`exit` 欄位是**選填**（可以整批不宣告＝零證據）、值**可以是指示詞**
   （status 不該為了求值去讀 `$ref`）、檔在或不在**兩邊都不是證明**（實測：parent 被
   SIGINT 後子行程照樣寫出 `done-*.txt`，`*.exit` 永遠缺）。而 §E-2 明說一筆 inst 的
   實際轉移函數有自由變數、實作 MUST NOT enforce footprint——**世界裡的作用本來就不是
   `.aos/` 看得到的**。所以 `status` **MUST** 只輸出逐格的機械事實（宣告了幾格、
   幾格是指示詞、幾格檔在、幾格檔不在），**MUST NOT** 出現任何叫 `effects_happened`
   的欄位。這一段要原樣寫進條款，否則下一個人會加它。

5. **`check` 只讓「三份真相收斂」收斂了一半，roadmap 要留一行。** verdicts B11 的原文是
   「機器可讀 schema 仍缺（`aos check` 那步）」。`check` 是拿 C++ 寫的驗證器去對 SPEC 的
   **中文條款**——它把「違規」機械化了，但**沒有**把 schema 單一來源化（那份「parser／
   文件／prompt 都從它派生」的 JSON Schema，M3 明確不做）。別讓 M4 以為 B11 已經全結。

6. **`check` 的退出碼與 §D-9 的分界是真的張力，不是措辭問題。** §D-9 的分界是「aos
   自己有沒有把這一步做完」——check 找到違規時它**做完了**，照那條界線該回 0；但那樣
   CI 就只能靠 `--json` ＋ `jq`，一支 validator 最基本的用法沒了。plan 列成必裁項
   （建議新碼 5，M2 已佔用 4），**主線一句話裁**。spec 不預設答案，只認列這是 §D-9
   自 M1 收編以來第一次被真正壓力測試。

7. **`insts/` 在版面樹裡，但沒有任何程式建立或讀取它。** `aos init` 只建 `version`／
   `turn`／`inst.tempd/`（實跑確認）。所以 `check` 對它的驗證項**必須是 SHOULD**——
   定成 MUST 的話**每一個 `aos init` 的世界上線第一天就紅**。§B-2 要順手註明「`aos init`
   MUST NOT 建它，不存在＝零顆其他 CPU、是合法狀態」；§E-4 也漏了 `insts/<cpu>.json`
   與 `<cpu>-head.json`（照理該與 `inst.json` 同為 MAY），一併補。

8. **`recover` 沒有互斥，而且不該假裝有。** `.runi` 不是鎖（verdicts D 表唯一未修的
   實作缺陷，M2 明確不修、M3 也不修），`.runi` 裡**沒有任何辨識活體的資訊**（無 pid、
   無時間戳、無心跳），所以 recover **分不出「回合層還活著」與「回合層死了」**。
   條款與 stderr 訊息 **MUST** 寫明前提「動手前先確定沒有 `aos exec` 在跑這個世界」。
   （順帶：讓 `.runi` 帶 pid 會怎樣？用本階段的 bump 判準過帳 ＝ **MUST bump 版面版本
   到 2**，因為舊 aos 的 `release` 會 unlink 掉別人還在用的租約。這是那份判準最好的
   教學例，建議寫進條文，但 **M3 不做這件事**。）

9. **§D-6 的去重有一條會真的丟批的路徑**：現任 header 的 `id` 相符 ＋ 批 `.temp` 存在
   但零長度／壞掉 → `aos exec` 清掉投遞、**丟棄這批**，零長度 `.temp` 永久殘留。
   完全符合現行條文（「否則只清投遞」），但沒人會預期去重機制會丟批。`recover` 只能
   事後**報「發生過」**，救不回——照實寫進矩陣，不要假裝能救。

10. **`docs/subprojects.md` 與 M2 裁-14 表面衝突，而 M2 只打算改 code map。**
    `subprojects.md`／`add-subproject.md` 的相依三層判準說「只有 `.cpp` 用到 →
    `PRIVATE_DEPS`」，但跨小專案相依**必須 `PUBLIC_DEPS`**（否則合併版 `libaos.so`
    會長出 `NEEDED libaos_inst.so.0`）。M2 plan 只把這句加進 `code-map/build.md`——
    而那兩份才是下一個人開新小專案時會讀的。M3 要開新小專案，**順手在兩份各補一句**。

---

## 做完之後長什麼樣（結果狀態）

1. **`aos status [--json] [WORLD]`**：人讀輸出 ＋ `--json`。狀態字是**封閉的五個**
   ——`layout-invalid`／`runi`／`ready`／`pending`／`no-work`（判定順序即此）。
   `--json` 帶 `schema_version`，**所有宣告過的 key 恆在、缺席用 `null`、陣列缺席用
   `[]`**。報得出：版面版本、`turn`（含「檔不在」與「內容壞掉」的區分）、當前批次在
   哪個位置、header 四欄、投遞匣的 ready／`.temp`／`.bad`／**不合法命名**四類、
   control inbox 同款、`insts/` 底下每顆 CPU 的**同構**投影、以及 `.runi` 存在時的
   **逐格 exit 證據計數**（不是判決）。**唯讀，跑前跑後 `.aos/` 逐位元組相同。**
2. **`aos check [--json] [WORLD]`**：逐條對 SPEC 驗版面與 schema。**每筆違規帶
   SPEC 條款編號**＋穩定的違規碼＋路徑＋實際值＋期望值；MUST 違規（error）與 SHOULD
   違規（warning）分開報；`.gitignore` 政策是**三態**（pass／fail／not-applicable，
   走 `git check-ignore`，不自己解析）。**唯讀。乾淨 `aos init` 的世界零違規。**
3. **`aos recover [WORLD] [動作旗標]`**：不帶動作旗標＝列出**可修項＋證據＋建議動作**
   （唯讀，每一列帶一行可複製的指令或「為什麼不能自動修」）。動作分兩族：作用於
   `.runi` 的三選一互斥（`--replay`／`--abandon`／`--adopt RECEIPT`）與版面殘留的
   （`--tidy`／`--drop-bad`／`--fix-turn N`）。每個動作先建 **forensic 副本**再動世界。
   **`.bad` 的清理在此兌現**（§D-8 從 M1 就指名 M3）。
4. **名冊封閉進 SPEC**：四格判準（實為五格，含格 0）、六支窮舉表、表優先、範圍句、
   豁免清單、修憲門檻。**「aos 會不會一直長出新子命令」這個 open question 消失。**
5. **ownership table 進 SPEC B 區**：每條路徑五欄齊，唯一雙 writer（`inst-head.json`）
   逐條標明並給處置，雙刪除者兩處（`*.bad`／`*.runi`）標明是刻意且冪等的。
6. **版面版本的 bump 判準 ＋ 三個版本數字 ＋ 命名例外清單**進 SPEC。
7. **`deliver --control`**：控制記錄不再需要外部生產者手刻（條款 M3 落定，實作可排在
   三支之後）。
8. **共用世界檢視層就位**：三支命令讀的是同一份版面知識，`kAosDir` 那批字串不再逐檔抄；
   它 **MUST NOT** 解讀回合層語意（`result`／`op` 原樣傳遞），因此相依圖無環。
9. **SPEC 更新**：名冊條款、ownership table、bump 判準、三個版本數字、命名例外、
   三支命令的條款（新區）、§B-4 診斷豁免、§B-2／§E-4 的 `insts/` 補洞、§C-8 的雙 writer
   處置、§D-9 的 `.runi` 那列明確化＋（若主線裁了）check 的新退出碼；
   `(planned, M3)` 摘標歸零。
10. **verdicts 過帳**：B9（沒有控制介面）、B11（三份真相，**部分**）、B12 的 §28／§29、
    D 表的 `.bad` 那條——各自標明現況；A 表加 M3 的裁決。

---

## 驗收條件（每條都可機械檢查）

1. **三支命令存在且被登記**：`aos --help` 的子命令集合**恰好**是
   `{init, exec, deliver, status, recover, check} ∪ {tooljson, llms}`，且**等於**
   SPEC 名冊條款的窮舉表 ∪ 豁免清單（煙霧腳本比對**集合**，不比順序——M2 已動過一次
   順序）。三支對認不得的選項回 **2** ＋ stderr 印 usage 行（沿用 `aos deliver` 的既有
   慣例：實跑確認今天 `deliver --help` 與 `--bogus` 都是 2＋usage；**本專案沒有
   per-subcommand `--help`**，M3 不新增這個機制）。
2. **唯讀保證（`status`／`check` 共用，四層）**：
   - **T1 指紋比對**：對下列每一種世界跑前跑後取
     `find .aos -printf '%y|%m|%s|%T@|%i|%P\n'` ＋ `sha256sum`，`diff` **MUST** 零輸出
     ——乾淨 init／有投遞／有 `.bad`／有 `.runi`／有 `inst.json.temp` 殘檔／有孤兒投遞
     `.temp`／`turn` 壞掉／`version` 不見／`version` 是 `2`／崩潰現場（parallel＋SIGINT）。
     **刻意不比 atime**（讀檔本來就會動它）。
   - **T2 唯讀權限**：`chmod -R a-w "$W/.aos"` 之後，兩支的退出碼與 stdout **逐位元組**
     等於可寫時的輸出。
   - **T3 syscall**（SHOULD，沒有 `strace` 記 skip）：`strace -f -e trace=%file` 看不到
     任何 `O_WRONLY`／`O_RDWR`／`O_CREAT`／`O_TRUNC`／`rename*`／`unlink*`／`mkdir*`／
     `link*`。
   - **T4 grep 護欄**：兩支的 `src/` 裡 `mkdir`／`O_CREAT`／`rename(`／`unlink(` **零筆**；
     `resolve`／`$ref`／`$env` **零筆**（不求值指示詞）。
3. **`status --json` 是穩定 schema**：五個狀態字各有一個測試；**逐欄位**斷言（不是
   「有輸出就好」）；輸出能被 `jq -e` 吃下；**每個宣告過的 key 在所有場景都存在**
   （對所有場景各跑一次 `jq -S 'paths'`，斷言 key 集合是同一個超集）；
   **輸出裡不存在任何宣稱外部作用的欄位**
   （`jq -e 'tostring | test("effect|did_run") | not'`），且 `status` 的 `src/`
   `grep -n 'running\|blocked-runi\|unknown-effect\|bad-delivery'` **零筆**。
4. **`check` 的每一筆違規都帶條款編號，且那個編號真的存在**：
   `jq -e '[.violations[].clause] | all(test("^§[A-H]-[0-9]+$"))'`；且逐一
   `grep -q "\*\*$clause" docs/SPEC.md`。**這一條是 §29「三份真相收斂」的機械形式**，
   同時是 SPEC 與 check 的耦合檢查（建議常駐煙霧腳本）。
5. **`check` 對乾淨世界零違規**：`aos init` 之後立刻 `aos check` **MUST** 零 error、
   零 warning、退出碼 0；跑完一回合之後再跑一次，仍零違規。
   （前置：`insts/`／`control.tempd/` 的驗證項**必須是 SHOULD**，否則這條過不了——
   見調度者須知第 7 點。）
6. **`check` 的每一個違規碼各有一個測試**佈出違規並斷言它出現；違規順序**確定**
   （同一世界跑兩次 `--json` 的 `diff` 零輸出）；`check` 的 `src/` 沒有任何寫入呼叫、
   沒有任何上限常數（§C-7）。
7. **`recover` 預設唯讀**：同 T1 的快照手法，斷言不帶動作旗標時 `.aos/` 不變；
   並斷言它**列出了**該列的可修項（有輸出，不是靜默），且**每個 finding 帶 `action` 欄**
   （值是一行可複製的 recover 指令，或 `"none"` ＋一句為什麼不能自動修）。
8. **`recover` 的每一種殘留形態各有一個測試**（矩陣每列一個測試名），每個測試斷言
   「世界變成什麼樣」＋「forensic 副本在哪」＋退出碼。硬條款另加 grep：
   - **`--replay` 之外的動作 MUST NOT 讓任何 inst 被執行**（用會寫檔的 inst 反證）。
   - `recover` 的 `src/` `grep 'return 3\|return 4'` **零筆**；`.runi` 存在時
     `aos recover` 回 **0**。
   - `grep 'temp_holds_complete_batch\|roll_forward'` **零筆**（不重做彙整層的自癒）。
   - **forensic 副本一律先建**：注入一個讓 `mkdir` 失敗的路徑，斷言原檔**未被動過**、
     退出碼 1。
   - `grep -E '\.(old|bak|orig|saved|backup)'` **零筆**（零新狀況字）。
9. **`.bad` 清理兌現 §D-8**：造出 `.bad` → `recover --drop-bad` → `.bad` 進 forensic
   副本並從 inbox 消失；且**彙整層仍然不自動刪**（既有行為不變的回歸測試）。
10. **`status` 與 `recover` 的分界可機械驗**：`status` 的 `src/` 出現任何 recover 動作
    旗標名（`--replay`／`--abandon`／`--adopt`／`--tidy`／`--drop-bad`／`--fix-turn`）
    **零筆**。
11. **ownership table 的路徑集合完整**：SPEC 的 ownership table 列出的路徑集合
    ⊇ SPEC §B-2 版面樹的每一個節點，且 ⊇（`aos init` 之後 ∪ 跑完一回合後 ∪ 崩潰現場）
    `find .aos` 實際出現的路徑集合（煙霧腳本比對，缺一條就算不完整）。
12. **`deliver --control` 落地**（若實作排進 M3）：投一份 `{"op":"stop"}` → 檔案出現在
    `.aos/control.tempd/`、檔名符合 `<pid>-<seq>.json`、內容是 canonical 位元組、
    stdout 是 `{"delivery":…,"target":"control.tempd"}` **且不含 `count`**；接著起 loop
    **MUST** 在回合邊界停下、退出碼 0。**不是「恰好一個 key `op`」的輸入 MUST 在
    deliver 端就被拒絕（退出碼 1）；但動詞本身 MUST NOT 在 deliver 端驗**
    （`grep -rn '"stop"' core/inst/` **零筆** ＝ 沒有反向相依的證據）。
13. **共用層沒有製造相依環**：`cmake --preset default` 與 `cmake --preset merged` 都
    configure 成功（相依環會直接 `strongly connected component (cycle)` 失敗）；
    `readelf -d build/merged/lib/libaos.so | grep NEEDED` **MUST NOT** 出現任何
    `libaos_*.so`（M2 裁-14 的 `PUBLIC_DEPS` 地雷，新小專案會再踩一次）；
    共用層的 `src/` `grep 'aos/loop\|aos::loop'` **零筆**（防環規範的機械形式）。
14. **`ctest --preset default` 全綠**（含 M3 新增的測試 target），
    `cmake --preset merged` 仍能設定並建置成功；外部消費測試（`env -u VCPKG_ROOT`）通過。
15. **code map 同步**：新小專案多一冊、總圖加一列、`code-map/build.md` 反映多出來的
    `add_subdirectory()`；三支命令的檔各自在對應分冊有一列。
16. **`docs/usage.md` 更新且命令實跑**：三支命令各一節，**每條命令與輸出都貼實跑結果**
    （feature-dev 鐵律）；退出碼表更新；`--help` 輸出重貼。
17. **SPEC `(planned, M3)` 零筆**：`grep -n "planned, M3" docs/SPEC.md` 無輸出
    （延後實作的條款改標 `(planned, M4)`，**不留 M3**）。
    條款編號沒有重用：`grep -o '§[A-H]-[0-9]*' docs/SPEC.md | sort | uniq -d` 零筆。
18. **既裁沒被翻**：`grep -n '"version":1' core/inst/src/handoff_header.cpp` 仍在
    （§F-1 沒被動）；`core/inst/src/format*.cpp`／`resolve.cpp`／`inst.cpp` 零改動；
    §C-3 欄位表一字未改；`grep -rn '"ok"\|"partial"\|"machine_failed"' core/inst/src/`
    **仍為零筆**（＝M2 驗收條件 5 沒被 M3 打破）。

---

## 明確不做

- **`agent step`／`emit-context`**（T5 開的另外兩支）——依裁決 1 判 **OS 層 → 做成系統
  inst**。**照實認列**：`agent step` 唯一做不成 inst 的部分是 T5 要求的 phase evidence
  ＝**回合歷史**，而回合歷史被 M2 裁決 1 歸給系統 inst；`emit-context` 是純資料轉換，
  完全做得成 inst。但**注入機制 M2 沒做、M3 也不做**，所以**M3 結束時這兩支仍然沒有
  家**。roadmap 要留一行——建議把三個症狀併成一行：**回合歷史**（M2 裁決 1）、
  **`agent step`／`emit-context`**（M3 §29）、**「loop 崩潰後人手上只有一個 `.runi`、
  沒有它為什麼死的資訊」**（M2 調度者須知第 3 點）——是**同一個缺件（系統 inst 的注入
  機制）的三個症狀，MUST 一起排**。
- **系統 inst 的注入機制**本身——M2 裁決 1 認列的代價，M3 之後。
- **一份機器可讀的 JSON Schema**（讓 parser／文件／prompt 都從它派生）——`check` 只把
  **違規**機械化，不做 schema 單一來源化（調度者須知第 5 點）。
- **序列化拷問**（M4 存貨，未解禁）、**外層契約 B5**、**記憶體模型**、**doorbell 實作**、
  **LLM CPU 形狀**——全部 M4 閘門後。
- **任何新子命令**（名冊內的三支以外）——裁決 1 剛把門關上，M3 自己不准開。
- 以下是讀的過程中發現「順手就會膨脹」、**本階段一律不碰**的：
  - **`.runi` 不是鎖**（verdicts D 表唯一未修的實作缺陷）——M2 明確不修，M3 也不修；
    只在條款與 stderr 訊息裡認列 recover 沒有互斥。
  - **`aggregate` 在 `.runi` 存在時仍發布**（調度者須知第 1／2 點的根因）——**根治
    要動 M1 剛凍結的彙整邏輯，M3 不做**；M3 只做零成本的 header `id` 比對，並把根治
    記進 verdicts D 表，與「`.runi` 不是鎖」一起排。
  - **`.runi` 帶 pid**（讓 recover 分得出活體）——**MUST bump 版面版本**，M3 不做；
    只當 bump 判準的教學例寫進條文。
  - **已知未決 #1（SIGINT 斷點續跑）**——`recover` 讓那個現場**有辦法收拾**，但**不**
    兌現「從斷點繼續」。這條矛盾是否消掉，主線另裁（plan 列成提案）。
  - **`.aos` 版面的第二個軸**（verdicts B7）——ownership table **不開新軸**；
    `status` 是**命令**不是檔案，M3 不在 `.aos/` 底下新增 status 投影檔。
    條文可加一句「ownership 解決正確性、第二個軸解決分類」（§28 原話），B7 仍開著。
  - **`tooljson`／`llms` 的存廢**——裁決 1 只把它們放進封閉的豁免清單，另案處理。
  - **`core/inst` 改名 `core/exec`**（core-layering 的開放項）——M2 已定不動。
  - **格式層**（`format*.cpp`／`resolve.cpp`／`inst.cpp`）與 §C-3 欄位表——零改動。
  - **`aos exec` 退出碼不反映子行程成敗**（§D-9）與 exit status 表達力
    （verdicts A 表「exit status 之後會改」）——不趁機改。
  - **並行度上限**（§C-7「沒有任何上限」是既裁的）——三支工具也 MUST NOT 加
    `--max-files` 之類的旗標。
  - **`aos migrate`／版面升級工具**——ownership table 會發現 `.aos/version` 是「未來的
    雙 writer、現在沒有擁有者」。條文照實寫「aos MUST NOT 自動升級版面；升級由人執行，
    升級工具是否進名冊，留待第一次真的要 bump 時走修憲程序」，M3 不做。

---

## 動工前讀

[layout-and-spec](../../ideas/machine-shape/layout-and-spec.md) 全檔（尤其 §12／§16／
§17／§28／§29）、[machine-shape/loop.md](../../ideas/machine-shape/loop.md) 的 §25／§26／§27、
[machine-shape/instruction.md](../../ideas/machine-shape/instruction.md)、
[T5 subcommand-specs](../../experiments/t5-agent-loop/subcommand-specs.md) 與
[T5 record](../../experiments/t5-agent-loop/record.md)（尤其「規格與實作對不上的地方」
四條與 SIGINT unknown 那節）、
[turn-based-folder/decided-and-open](../../ideas/turn-based-folder/decided-and-open.md)、
[verdicts](../../ideas/verdicts.md) A／B／C／D 四表、
[keep](../../ideas/call-format/keep.md)、[core-layering](../../ideas/core-layering.md)；
`docs/SPEC.md` **全文**（尤其 §B 全區、§C-2／§C-6／§C-8、§D 全區、§E-2／§E-4、
§F-1／§F-2、已知未決）、`docs/aos-folder.md`、`docs/usage.md`、`docs/subprojects.md`、
`docs/build.md`；
**[m2-loop-project/spec.md](../m2-loop-project/spec.md) 與 [plan.md](../m2-loop-project/plan.md) 全文**
（M3 的地基；plan 第五節「動哪些檔」是 M2 之後檔名的唯一依據）、
M1 的 [spec](../archive/m1-loop-side/spec.md)／[plan](../archive/m1-loop-side/plan.md)；
[add-subproject](../../add-subproject.md)、`cmake/AosSubproject.cmake`、根 `CMakeLists.txt`、
`core/CMakeLists.txt`、`core/inst/CMakeLists.txt`；
[code map](../../common/code-map.md) 與 `code-map/inst/*.md`、`code-map/build.md`、
[conventions](../../common/conventions.md)、[gotchas](../../common/gotchas.md)；
程式碼現況 `core/inst/src/` 的 `handoff.cpp`／`handoff_fs.*`／`handoff_header.*`／
`run_exec.cpp`／`run_init.cpp`／`run_deliver.cpp`、`include/aos/inst.hpp`／`inst.h`、
`core/inst/tests/`（Catch2 風格與 `test_run_support.hpp` 的 helper）。
