# Instruction 交接協定

這份文件回答：「多個生產者把工作交給一顆執行 CPU 時，檔案怎麼安全地彙整、取走與
釋放？」它說明 `aos::inst` 公開的 handoff API 與磁碟狀態；JSON 欄位請看
[記錄格式](format.md)，子行程如何執行請看[執行語意](exec.md)，CLI 的完整入門則看
[使用說明](../../../docs/usage.md)。

## 為什麼需要獨立的 handoff 層

一個 aos world（由某個資料夾及其 `.aos/` 執行狀態組成的工作空間）可能同時有多個
工作生產者。生產者不能一起覆寫同一份 `inst.json`，否則後寫者會吃掉先寫者的工作；
未來不同的抽象 CPU 也會各有自己的 instruction 檔，需要完全相同的交接步驟。

handoff 因此只接受一個 instruction base path，例如 `.aos/inst.json` 或
`.aos/insts/llm.json`，並負責四件事：

1. **投遞**：把一份待辦 JSON 放進 inbox。這是三步協定裡唯一由**外部生產者**執行的
   一步，所以協定細節（唯一檔名、先 `.temp` 後排他 rename、canonical 位元組）由
   `deliver_instructions()` 包起來，生產者不必自己手刻。
2. **彙整**：把多份有效投遞攤平成一個批次，再原子發布成 base path，並在批旁邊寫一份
   header sidecar。
3. **取件**：把 base path 改名為 `.runi`，表示這一批已被某個回合占有。回合就是一次
   「取走一批、全部執行、清掉執行中標記」的完整處理。
4. **釋放**：回合正常返回後刪除 `.runi`。

協定的 normative 條文在 [SPEC](../../../docs/SPEC.md) §D 區（§D-1～§D-8）；本檔寫的是
這個函式庫實際怎麼做。

它不印 stdout／stderr、不決定 CLI 退出碼，也不執行 instruction。呼叫端可以自行把
結構化結果映成自己的 UI 或錯誤政策。

## 路徑怎麼推導

以 `/srv/demo/.aos/inst.json` 為例：

| 用途 | 路徑 |
|---|---|
| base：下一批等待取件的 instruction | `/srv/demo/.aos/inst.json` |
| 寫批用的每行程唯一暫存（也是 roll-forward 的錨） | `/srv/demo/.aos/inst-<pid>-<seq>.json.temp` |
| 已取件、正在處理 | `/srv/demo/.aos/inst.json.runi` |
| inbox：生產者投遞目錄 | `/srv/demo/.aos/inst.tempd/` |
| header sidecar：這一批的 metadata | `/srv/demo/.aos/inst-head.json` |
| 寫 header 用的每行程唯一暫存 | `/srv/demo/.aos/inst-head-<pid>-<seq>.json.temp` |

base 必須以 `.json` 結尾。inbox 是把最後的 `.json` 換成 `.tempd`，header 是把最後的
`.json` 換成 `-head.json`；另外兩個狀態則直接附加在 base 後面，所以 `insts/llm.json`
會配到 `insts/llm.tempd/` 與 `insts/llm-head.json`。

**注意 `inst.json.temp` 不在表上**：彙整**不再產生**那個檔。批寫進每行程唯一的
暫存，然後**直接**排他 rename 成 base，中間沒有共用槽位。

**為什麼不能有共用的固定槽位**。直覺上「唯一名寫完 → rename 進固定的
`inst.json.temp` → 從那裡發布」很誘人，因為固定路徑是個現成的 roll-forward 錨。但
那個槽位是**共用可變狀態**，兩個彙整者會互相覆蓋，於是：

> A 掃到投遞 `{d1}`，B 稍後掃到 `{d1, d2}`（`d2` 在 A 掃完之後才到）。A 把自己的批
> 寫進槽位，B 覆蓋成 `[d1,d2]`。A 接著寫 header（id ＝ `id({d1})`），然後從槽位發布
> ——**發布出去的是 B 的批**。A 清掉自己看到的 `d1`、標 swept；B 撞 `EEXIST` 乾淨
> 放棄，於是**沒人清 `d2`**。下一輪 `d2` 被重新彙整、再跑一次。

集合相同時位元組相同，覆蓋無害；集合不同時就漏出上面這條。**去掉槽位，這整類問題
就不存在**——每個彙整者從頭到尾只碰自己那一份檔。

**那 roll-forward 的錨呢？靠內容認身分，不靠名字。** 去重命中時，彙整掃 base 所在
目錄找**兄弟唯一暫存**（`inst-*.json.temp`，跳過 `inst-head-*`），排序後逐一讀，
**位元組跟本輪重算的 canonical 批完全相同**的第一個就是錨。這跟 #21 的逐位元比對
是同一個原則：能通過比對的檔，內容就一定是「本輪這組投遞的 canonical 批」——不管
它是我們自己上一次崩掉留下的，還是併發同儕正在飛的。兩者是同一串位元組，誰把它
rename 到 base 都是同一個結果，輸的那一邊拿 `EEXIST` 乾淨放棄。**名字只是找得到
它的索引，身分由內容決定。**

唯一名的形狀是把權杖插在最後一個 `.json` **之前**（`inst.json` → `inst-4711-0.json.temp`，
`inst-head.json` → `inst-head-4711-0.json.temp`）。這是刻意的：整體仍然符合 §B-1 的
`<名字>.<副檔名>.<狀況>` 文法，名字變成 `inst-4711-0`，沒有引進新的狀況字。權杖是
`<pid>-<seq>`，跟投遞用的是同一個計數器。隔離用的第二個 `.bad` 名字（見下）走同一
套規則。

> **殘骸會累積，這是刻意的。** 固定槽位時代最多只會有一個 `inst.json.temp`；現在
> 每次「崩在寫完批之後、發布之前」都會留下一份 `inst-<pid>-<seq>.json.temp`。這**不是
> 漏刪**，而是 §D-8「留現場、清理歸人或 `aos recover`（M3）」的一貫哲學。
> 成功發布之後**刻意不順手掃刪**其他兄弟暫存——那可能是同儕正在飛的檔，刪掉就等於
> 把別人寫到一半的批抽走。只有自己那一份、而且只在自己確定用不到時才刪。

## 投遞

```cpp
HandoffState deliver_instructions(const std::string &instruction_path,
                                  const std::string &document,
                                  DeliverResult &result);
```

`document` 是一份完整的 JSON 文件（一個 instruction 物件或一個陣列），驗證走的是
format 層那個唯一的 parser——跟彙整、跟 `aos exec` 讀 `inst.json` 是同一套規則。
整份文件**先驗證再落地**：任何一筆不合格就整批拒收，回 `DeliveryInvalid`，
`result.inst_state` 是驗證狀態、`result.error_record` 是第幾筆出問題（1 起算，
還沒進到逐筆解碼時是 0），此時 inbox 裡什麼都不會多出來，連 `.temp` 都沒有。

通過之後的落地順序是：

1. 產生一個唯一檔名 `<pid>-<seq>.json`（`seq` 是行程內單調遞增的計數）；
2. 用 `O_EXCL` 建 `<名>.json.temp`，把 **canonical 位元組**寫進去、`fsync`、關檔——
   canonical 的意思是這份文件已經被 `read_all`→`write_all` 往返過一次，所以「投遞了
   什麼」與「彙整讀到什麼」永遠是同一串位元組，未解析的 `$env`／`$ref`／`$opt` 也
   在這一步被證明寫得回去；
3. **排他** rename 成 `<名>.json`（`renameat2(RENAME_NOREPLACE)`，檔案系統不支援時
   退階成 `link`＋`unlink`）；撞名就換一個序號重來，**絕不覆蓋既有的名字**——被覆蓋的
   可能正是另一個生產者寫到一半的投遞；
4. `fsync` inbox 目錄，讓那個目錄項落盤。

成功時 `result.name` 是發布後的檔名、`result.inbox` 是它落腳的收件匣、`result.count`
是這批有幾筆（空批次 `[]` 合法，`count` 為 0）。inbox **必須已經存在**：不存在回
`InboxReadFailed`，deliver 不會替你建世界（那是 `aos init` 的事）。

兩個邊角：

- `result.sync_error` 非 0 代表**投遞已經進 inbox 了**，只是還缺一項收尾——不是投遞
  本身失敗。這是警告不是失敗，函式仍回 `Ok`；謊報失敗會讓生產者重投，那才真的多出
  一份。兩種來源共用這個欄位：第 4 步的目錄 `fsync` 失敗，以及排他 rename 走退階
  路徑（`link`＋`unlink`）時**收尾的 `unlink` 失敗**——那時 `<名>.json` 已經連好、
  內容完整、彙整一定會收，留下的只是一份 `.temp` 殘骸要人處理。這兩種都不影響
  「投遞成功了嗎」的答案。
- 序號連撞 8 次（只可能來自 pid 重用後撞上別的行程留下的殘檔）會放棄並回
  `RenameFailed`／`EEXIST`：那時 inbox 有系統性問題，回報比空轉好。

同一個行程連續呼叫 N 次就是 N 份不同名的投遞，不會互相蓋掉；每一次呼叫都是一次真的
投遞，**沒有「重試」這回事**。

## 彙整規則

`aggregate_instructions(base, result)` 依檔名字典序讀 inbox。只接受第一個副檔名就是
結尾的 `<name>.json`；`123.json.temp`、`123.json.bad`、`name.part.json` 都會跳過。
每份內容都可是一個 instruction 物件或一個陣列，最後攤平成單一陣列。彙整會經過
format 層完整的讀取與重新寫出，因此尚未解析的 `$env`、`$ref`、`$opt` 指示詞必須
能無損寫回；否則交接雖成功，執行時的語意卻會悄悄改變。

有效投遞會被寫成一批、排他發布成 base（順序見下一節）；只有**本輪處理完成**之後才
刪除來源投遞。有效但展開後沒有任何 instruction 的空投遞是例外：沒有資料需要發布，
因此不建立空的 base，卻仍會刪除來源；否則它會永遠留在 inbox、每個回合都被重新讀取。

以下情況都是成功的 no-op（什麼都不做）：

- inbox 不存在或是空的；
- 沒有任何有效投遞（無效投遞仍照下述規則隔離）；
- base 已存在，代表前一批仍在等候取件。此時不覆蓋 base，也不碰 inbox。

### 投遞出了問題時，各走哪一條路

三種「這份投遞不能用」的情況**刻意分成三條不同的路**，因為它們的後果完全不同：

| 情況 | 動作 | issue kind | 為什麼 |
|---|---|---|---|
| 內容不是合法 JSON／不符 schema | 隔離成 `.bad` | `InvalidDelivery` | §B-1 的 `.bad` 定義就是「**內容無效**」。這份東西再讀一百次也不會變好 |
| 讀不到（`EACCES`／`EIO`…） | **留在原地**、下一輪再試 | `DeliveryReadFailed` | 讀不到 ≠ 內容無效。`.bad` 不進彙整、又 MUST NOT 自動清（§D-8），所以一次暫時性的權限或 IO 錯誤若貼上 `.bad`，就等於把一份完全合法的工作**永久**踢出佇列 |
| 不是普通檔（FIFO／目錄／socket） | **跳過不讀**、原地不動 | `DeliveryNotRegular` | 它不是「內容無效」，是根本不該讀。沒有寫端的 FIFO 會讓 `open` 永久阻塞——而那發生在取件之前，世界既沒被鎖也沒有任何診斷輸出，整台機器會無聲停擺。所以開檔前先 `stat` 確認 `S_ISREG`（`stat` 跟隨 symlink，與 `read_file` 的 `open` 同語意） |

讀不到的情況裡，`ENOENT` **靜默**跳過：那代表檔在我們掃完目錄之後被別人清掉了，
是正常現象，不值得出聲。

另外還有一種「不收但也不動」的：**以 `.json` 結尾、形狀卻不合**的檔名
（`a.b.json`、`.hidden.json`、`.json`）。收的集合刻意維持原樣不改（改判定會改變
收哪些檔），但不再**靜默**——記一筆 `DeliveryNameIgnored`，讓那份永遠躺在收件匣裡
的投遞至少出一次聲。`x.json.temp`／`.bad`／`.runi` 這些狀況檔不以 `.json` 結尾，
不會命中，也就不會吵。

**隔離絕不覆蓋既有的 `.bad`**：§D-8 說彙整者 MUST NOT 自動刪 `.bad`，而覆寫等同刪除
——第二份同名的壞投遞若蓋掉第一份，等於把鑑識證據無聲銷毀。所以隔離走的是排他
rename；撞到既有的 `.bad` 就換一個仍然符合 §B-1 的唯一名（`x.json` →
`x-4711-3.json.bad`），再撞才記 `IsolationFailed`。隔離成功之後也會 `fsync` 收件匣，
不讓「這一輪只有壞投遞」的早退路徑一次目錄同步都沒做。

## 批 header sidecar

每次真的發布一批，彙整就在批**旁邊**寫一份 header：base 的 `.json` 換成
`-head.json`，內容是一行 JSON（實跑取樣，`id` 每批不同）：

```text
{"version":1,"id":"8b9c43beaf4f9429","origin":"aggregated","result":null,"swept":true}
```

五個欄位的意義是 [SPEC](../../../docs/SPEC.md) §C-8 定的：`version` 是**指令格式**的
版本（不是 `.aos` 版面版本，兩者分開，見 §F-1／§F-2）、`id` 是批 id（去重的依據）、
`origin` 是這批打哪來（彙整發布的一律 `"aggregated"`）、`result` 留給 loop 在
writeback 時寫回（值域 M2 才定義，現在恆為 `null`），`swept` 是**去重的閘門**。

`swept` 在一輪之內會被寫兩次：發布時寫 `false`，等本輪收下的投遞**全數刪除、且收件匣
目錄落盤**之後改寫成 `true`。所以上面那份取樣是 `true`——一輪正常跑完之後看到的都是
`true`，`false` 只存在於「提交點之後、清理完成之前」那個窗口裡。缺 `swept` 欄
（舊世界寫的 header）一律視為 `false`。為什麼需要它，見下面「sweep 與去重射程」。

**誰寫誰讀**：彙整層寫，loop 讀。**exec 層不讀、也不認識 header**——`claim_instruction()`
只讀 base，`execute()` 連這個檔存在都不知道（§A-6「凍結的矽」的直接推論）。所以
header 怎麼長、將來加什麼欄位，都動不到執行機制。

**只認頂層的 `id` 與 `swept`**：讀 header 用的是一個最小的頂層物件掃描器（期待 `{`，
然後反覆「字串 key → `:` → 值 → `,` 或 `}`」；字串值正確跳過跳脫序列，物件與陣列用
深度計數跳過，跳過時仍然把字串整段當一個 token）。**巢狀物件裡、陣列元素裡、字串值
裡**長得像 `"id"` 的位元組一律不算數。這不是潔癖：§C-8 說 `result` 由 loop 在 M2
寫回，一旦它變成含 `id` 的物件，「找第一個 `"id":`」那種定點解析就會拿**巢狀**的 id
去比對，把全新的批靜默丟掉。讀不懂（不是合法的頂層物件、沒有頂層 `id`、`id` 不是
字串、值裡有跳脫序列）一律視同沒有 header——失效方向刻意往「多跑一次」倒，不往
「吃掉投遞」倒。

幾個不會讓整輪失敗的情況：

- header 寫不成或 rename 不成：**這一批照發**，只是這一輪沒有去重保證（退回沒有
  header 時的行為），記一筆 `HeaderWriteFailed` issue 讓上層看得見。
- 現任 header 讀不到內容或格式不認得：記一筆 `HeaderInvalid` issue，一律**視同沒有
  header**，照常發布。
- 標記 `swept` 失敗：也只記 `HeaderWriteFailed` 續行。代價是下一輪少一次去重保證，
  跟 header 本身寫不成同一個等級。
- 沒有東西可發布（空投遞被消化掉的那種 no-op）就不寫 header——header 描述的是
  「現任的那一批」，沒有批就沒有 header。

**但有一個組合是致命的**：同一輪裡同時出現 `HeaderWriteFailed` **與**
`DeliveryRemoveFailed`，彙整會回**非 `Ok`**（借 `PublishWriteFailed`，`path` 指向
header、`error` 是 header 寫失敗的 errno），CLI 因此回 1。理由是這兩個各自可容忍的
降級疊在一起就不可容忍了：header 沒寫成代表下一輪**沒有去重保證**，投遞沒刪掉代表
下一輪**一定會再看到同一組**——合起來就是無上限的副作用重播，每一輪重跑同一批，
而且沒有任何機制會讓它停（審查實測連三回合各重跑一次，退出碼全 0）。兩者成因還高度
相關（同一個唯讀或異常的 `.aos`），不是獨立事件。

借用既有的 `PublishWriteFailed` 而不是新增一個 `HandoffState`，是因為鏡射它的
`aos_handoff_state`（`inst.h`）第 10／11／12 格已經被 C ABI 專屬的
`ALLOC_FAILED`／`READ_ERROR`／`BUFFER_TOO_SMALL` 佔走；C++ 端再加第 10 個值就會跟 C
端錯開，`capi_handoff.cpp` 的 `static_cast` 會把它翻成錯的 C 狀態。這個取捨也寫在
`inst.hpp` 的列舉註解裡。

## fsync 與發布順序

所有由這一層寫出去的檔案都 `fsync` 之後才算寫成功（`fsync` 失敗＝寫入失敗），
`rename`／`unlink` 之後還要 `fsync` 它所在的**目錄**——目錄項有沒有落盤看的是目錄的
`fsync`，不是檔案的。發布一批的完整順序（[SPEC](../../../docs/SPEC.md) §D-5）：

```text
1. 寫批 <名字>-<pid>-<seq>.json.temp        → fsync 檔     ← 唯一名，全程只碰這一份
2. 寫 header <名字>-head-<pid>-<seq>.json.temp → fsync 檔   ← 唯一名
3. rename header → <base>-head.json  ← 去重承諾的提交點（swept 寫 false）
4. fsync 目錄
5. rename 批：<名字>-<pid>-<seq>.json.temp → base，**排他**  ← 見下
6. fsync 目錄
7. 刪掉來源投遞 → fsync 目錄
8. 全數刪成功且目錄落盤 → 把 header 改寫成 swept:true
```

**批發布（第 5 步）必須排他，而且來源是自己的唯一暫存**。目的檔已經存在就代表
**別的彙整者先發布了**，本輪 MUST 放棄：不清投遞、不重寫 header、`published` 維持
`false`、回 `Ok`。修補之前這一步是覆蓋語意的 `rename`，§D-4「`inst.json` 已有一份
沒被讀走時本輪 MUST NOT 發布」只靠開頭那個 `lstat` 擋——那是典型的 check-then-act，
兩個彙整者同時跑就會互相覆蓋。

放棄時**可以安心 `unlink` 自己的唯一暫存**（那是我們自己寫的檔）。這跟 roll-forward
的錨不同——錨不見得是我們的，所以那條路上撞到 `EEXIST` 時**不刪**。

第 5 步失敗（非 `EEXIST`）時**刻意保留**那份唯一暫存：header 已經是新 id 了，這一份
就是下一輪的 roll-forward 素材，靠位元組比對被認出來。

**排他發布的落敗者會留下一份「描述別人那批」的 header**（第 3 步已經跑完了）。這無害：
落敗者與勝出者看到的投遞集合相同時，id 本來就一樣，那份 header 描述的就是同一批；
集合不同時，剩下沒被清掉的投遞會在下一輪算出第三個 id，照常發布——既不重複也不遺失。

**為什麼 header 仍然排在批前面**。有了排他發布之後很自然會問：批先發布不就好了？
不行。批先、header 後的話，崩在中間留下的現場是「`inst.json` 已存在 ＋ header 還是
舊 id」——下一輪 `aggregate` 的第 ⓪ 步 `lstat(base)` 就直接早退，什麼都不做；等這批
跑完、投遞還在 inbox，那時算出來的 id 跟舊 header 對不上，於是**重新發布**＝雙重
執行。只有 header 先 rename，才留得下「新 id ＋ 批還躺在某份唯一暫存裡」這個
**可辨識、可 roll-forward** 的現場。

兩件事各管各的，不要混為一談：**排他發布解的是併發**（兩個彙整者同時發布），
**提交點順序解的是崩潰**（單一彙整者死在中途）。

目錄 `fsync` 失敗只記 `DirectorySyncFailed` issue、不改變控制流：目錄項本身已經換好
了，少的是耐久性保證；為此讓整輪彙整失敗只會把世界卡住，更糟。

### 取件與釋放同受這一條拘束

§D-5 的耐久性射程涵蓋**三步協定全部**，不只彙整：

- `claim_instruction` 的 `rename`（base → `.runi`）之後 `fsync` 目錄。§D-7 說
  「`.runi` 存在 ⟺ 有一回合沒跑完」，這個等價關係要成立，這一次 rename 就必須落盤
  ——否則斷電後 `.runi` 回退成 `inst.json`，而副作用**已經發生**的那一批會被整批
  重跑一次。那是最貴的方向。
- `release_instruction` 的 `unlink`（刪 `.runi`）之後 `fsync` 目錄。這一步過去只是
  「剛好」被 CLI 的 `advance_turn` 順帶 `fsync` 到——§B-3 說 `turn` 在 M2 要搬到
  loop 層，搬走那個巧合就沒了；直接用 C++ API 的呼叫端本來就沒有 `advance_turn`。
  而 `.runi` 復活代表每次 `aos exec` 都回 3，**世界永久卡死**（`aos recover` 排在 M3）。

兩處失敗都只記 `DirectorySyncFailed` issue 續行，不改變回傳值——比照彙整，耐久性
失敗 MUST NOT 讓回合停擺。

> **邊界**：這條「寫檔就 fsync」的規矩只涵蓋**函式庫自己開的檔**。
> `aos_instruction_write_fd()` 寫的是**呼叫者自己的 fd**——函式庫不代呼叫者 `fsync`、
> 也不動它的 flag、不關它；要耐久性請自己在寫完之後 `fsync`。（`write_file()` 那種
> 自己開檔的入口就有 fsync，見 [capi.md](capi.md)。）

## 批 id、去重與 roll-forward

批 `id` 是對**排序後的每份投遞**做的確定性摘要：把「投遞檔名 `\0` 內容 `\0`」依序餵給
64-bit FNV-1a，輸出 16 位小寫 hex。吃的是**檔名**而不是完整路徑——世界整包可搬，id
不該跟著搬家變。

### `swept` 是去重的閘門

比對**不是**無條件啟用的，先看現任 header 的 `swept`：

- `swept` **不成立** → 啟用比對。上一批的清理沒走完，收件匣裡的東西可能是殘留。
- `swept` **成立** → **完全不比對**。上一批的清理已經走完，收件匣是乾淨的；現在看到
  的投遞就是**全新**的一批，MUST 照常發布，即使它同名同內容、算出來的 id 一模一樣。

沒有這個閘門的話，去重就分不出「崩潰殘留」與「恰好長得一模一樣的全新投遞」——因為
id 是**內容導出**的（選內容導出是為了避開 manifest，而 manifest 留 v2）。修補之前
header 的 id 在批被執行完之後**永不失效**，於是同名同內容的全新投遞會被靜默刪除、
永不執行，而且退出碼 0、零 warning、`turn` 不動。這條路不是理論上的：`aos deliver`
是一次性行程，`seq` 每個行程從 0 起算，所以 CLI 產生的名字永遠是 `<pid>-0.json`，
只差一個 pid 重用（預設 `pid_max=32768` 的容器約 4.5 小時繞一圈）；任何用內容定址或
確定性命名的第三方生產者更是天天踩到。

### 命中之後怎麼走

`swept` 不成立且 id 相同，代表這一組投遞上一輪已經跨過提交點（第 4 步）、只是投遞
沒被清掉——崩在刪投遞之前，或 `unlink` 全數失敗。這時分兩種走法：

- 找得到**錨**——某份兄弟唯一暫存的位元組與本輪重算的 canonical 批逐位元相同
  → **roll forward**：排他 rename 到位（補完第 5 步）、`fsync` 目錄、清掉投遞。
  這一批不會丟。撞到 `EEXIST` 代表別人先發布了，放棄且**不刪那個錨**。
- 找不到錨 → 上一輪已經發布完、批也已經被取走或正在跑：**只清投遞、不重發**。
  這就是「同一批不會執行兩次」的兜底。

**逐位元比對是必要的，不是保險**。修補之前的判準只是「`.temp` 解析得出一份非空的
批」，完全不驗證它是不是 header 那個 id 對應的批——於是一份與這批毫無關係的
`inst.json.temp` 殘骸會被當成「這一批」扶正並執行掉，等於執行了未經任何驗證來源的
批次。canonical 位元組本來就是確定性的（§D-3），拿它直接比對不需要任何額外 metadata；
現在它同時扛下「認出錨」這件事，讓固定槽位可以整個拿掉。

清完投遞（且收件匣目錄落盤）之後，同樣要把 header 標成 `swept:true`——這一輪
雖然沒發布，但清理走完了。

### 覆蓋範圍（照實寫，不誇大）

去重擋的是**投遞殘留**，而且只保證**同名同內容、恰好整組**的殘留不會被發布第二次。
它不是內容去重，也不是通用的冪等保證：

- 只有一部分投遞殘留，或殘留的投遞和新來的投遞混在一起，本輪算出來的 id 就跟現任
  header 不同，那一批會照常發布——**其中重複的那幾筆會再跑一次**。這個情況不在保證
  內。
- 同樣內容重新投遞一次會拿到新的檔名（`<pid>-<seq>` 每次不同），id 也就不同。
  「投兩次一樣的東西」本來就該跑兩次，那是使用者的意思，不是這個機制要擋的事。
- **併發雙重彙整不在去重的射程內**，由 §D-5 的**排他發布**擋（見上一節）。原因很
  直接：B 在 A 寫出 header 之前就讀了 header，比對本來就不可能命中。這兩個機制解的
  是不同的問題，不要指望其中一個順便蓋掉另一個。

## 取件與釋放

`claim_instruction(base, document, result)` 先拒絕既有 `.runi`，再完整讀取 base，最後
把 base rename 成 `.runi`、`fsync` 目錄。成功時 `document` 是讀到的完整 JSON；base
不存在則回 `NoInstruction`，不是錯誤。既有 `.runi` 回 `Busy`，讓呼叫端知道不能啟動
另一個回合。

**「存在」的定義兩層必須對齊**。`aggregate` 的第 ⓪ 步用 `lstat`（**不**跟隨 symlink），
`claim` 用 `open`（**跟隨**）。一個斷掉的 symlink 會同時滿足「`lstat` 成功」與
「`open` 回 `ENOENT`」——`aggregate` 因此判定「已有一批等著被取」而不發布，`claim`
卻回 `NoInstruction` 讓 CLI 回 0，夾出一個規格沒定義的第三態「**存在但永遠取不走**」，
世界無聲卡死（`rc=0`、stderr 全空、`--loop` 安安靜靜地以為自己閒著）。所以 `claim`
拿到 `ENOENT` 時會再 `lstat` 一次：`lstat` 成功＝base 確實存在、只是讀不到，回
`InstructionReadFailed`（CLI 回 1 並把原因噴出來）；`lstat` 也 `ENOENT` 才是真的
`NoInstruction`。

`release_instruction(base, result)` 刪除推導出的 `.runi`，然後 `fsync` 目錄。應在批次
解析與所有子行程（包含 parallel thread）都結束後呼叫。若行程 crash、被強制終止或
斷電，`.runi` 會保留下來，下一次取件會回 `Busy`；這是刻意保留的未完成現場。

## 公開 API 與錯誤資料

```cpp
HandoffState deliver_instructions(const std::string &base,
                                  const std::string &document,
                                  DeliverResult &result);
HandoffState aggregate_instructions(const std::string &base,
                                    HandoffResult &result);
HandoffState claim_instruction(const std::string &base,
                               std::string &document,
                               HandoffResult &result);
HandoffState release_instruction(const std::string &base,
                                 HandoffResult &result);
```

`HandoffResult` 每次呼叫都會先重設：`published` 表示本次彙整是否真的發布；`path` 與
`error`（errno）描述致命失敗；`issues` 則是彙整仍可繼續時的逐檔問題。`HandoffIssue`
附帶投遞路徑、`InstState` 或 errno，`kind` 目前有九種：

| kind | 意義 | 這一輪算失敗嗎 |
|---|---|---|
| `InvalidDelivery` | 內容不合法：已隔離成 `.bad` | 否 |
| `DeliveryReadFailed` | 投遞讀不到（權限／IO）：留在原地，下一輪再試 | 否 |
| `IsolationFailed` | 隔離成 `.bad` 失敗（含撞名兩次） | 否 |
| `DeliveryRemoveFailed` | 發布後刪投遞失敗 | 否＊ |
| `HeaderWriteFailed` | header 寫不成／rename 不成／標 swept 失敗 | 否＊ |
| `HeaderInvalid` | 現任 header 讀不到或讀不懂：視同沒有 header | 否 |
| `DirectorySyncFailed` | `rename`／`unlink` 之後的目錄 fsync 失敗 | 否 |
| `DeliveryNotRegular` | 不是普通檔（FIFO／目錄／socket）：跳過不讀、不隔離 | 否 |
| `DeliveryNameIgnored` | 以 `.json` 結尾但形狀不合：不收、不隔離，只出聲 | 否 |

＊ 單獨出現時不算失敗，但 `DeliveryRemoveFailed` 與 `HeaderWriteFailed`
**同一輪一起出現**時整輪回非 `Ok`，理由見上面「批 header sidecar」那一節。

`DeliverResult` 是投遞專用的結果（同樣每次呼叫先重設）：成功時看 `name`（發布後的
投遞檔名）、`inbox`（落腳的收件匣）、`count`（這批幾筆）與 `sync_error`（非 0 ＝ 已投遞
但目錄 fsync 失敗的警告）；`DeliveryInvalid` 時看 `inst_state` 與 `error_record`；
其餘失敗看 `path` 與 `error`。

整體 `HandoffState` 不是 CLI 退出碼。`Ok` 可能代表已發布，也可能代表 no-op；呼叫端
要看 `published`。`Busy` 與 `NoInstruction` 是協定狀態，`DeliveryInvalid` 表示投遞的
文件過不了驗證，其餘非 `Ok` 值表示這次操作無法完成。

## 可直接執行的完整例子

先從 repo 根目錄準備投遞：

```bash
rm -rf /tmp/aos-handoff-demo
mkdir -p /tmp/aos-handoff-demo/inst.tempd
printf '%s\n' '{"argv":["printf","hello\\n"]}' \
  > /tmp/aos-handoff-demo/inst.tempd/100.json
```

把以下內容存成 `/tmp/handoff-demo.cpp`：

```cpp
#include <aos/inst.hpp>

#include <iostream>
#include <string>

int main() {
    const std::string base = "/tmp/aos-handoff-demo/inst.json";
    aos::HandoffResult result;

    auto state = aos::aggregate_instructions(base, result);
    std::cout << "aggregate=" << aos::to_string(state)
              << " published=" << result.published << '\n';

    std::string document;
    state = aos::claim_instruction(base, document, result);
    std::cout << "claim=" << aos::to_string(state) << '\n';

    state = aos::release_instruction(base, result);
    std::cout << "release=" << aos::to_string(state) << '\n';
}
```

編譯並執行：

```bash
c++ -std=c++23 /tmp/handoff-demo.cpp -Icore/inst/include -Icommon/include \
  -Lbuild/lib -Wl,-rpath,"$PWD/build/lib" -laos_inst -o /tmp/handoff-demo
/tmp/handoff-demo
```

輸出是：

```text
aggregate=Ok published=1
claim=Ok
release=Ok
```

執行後 `100.json`、`inst.json` 與 `inst.json.runi` 都不存在，代表投遞已發布、取件並
釋放；留在原地的是 `inst-head.json`——那一批的 header sidecar，發布時寫的：

```bash
cat /tmp/aos-handoff-demo/inst-head.json
```

```text
{"version":1,"id":"8b9c43beaf4f9429","origin":"aggregated","result":null,"swept":true}
```

`swept` 已經是 `true`：投遞在同一次 `aggregate_instructions()` 裡就清乾淨了，所以
sweep 在那一輪之內就走完。這個例子只示範交接；真正執行 `document` 裡的指令，仍是
呼叫端自己的責任。

### 換成用 `deliver_instructions()` 投遞

上面的例子是手動把檔案放進 inbox（示範用）。真正的生產者應該走 deliver，讓協定細節
由函式庫負責。先準備一個空世界的 inbox：

```bash
demo=$(mktemp -d)
mkdir -p "$demo/inst.tempd"
```

把以下內容存成 `$demo/deliver-demo.cpp`：

```cpp
#include <aos/inst.hpp>

#include <iostream>
#include <string>

int main() {
    const std::string document = R"({"argv":["printf","hello\n"]})";
    aos::DeliverResult result;

    const aos::HandoffState state =
        aos::deliver_instructions("inst.json", document, result);
    std::cout << "deliver=" << aos::to_string(state)
              << " name=" << result.name << " count=" << result.count
              << " inbox=" << result.inbox << '\n';
}
```

從 repo 根目錄編譯，然後進 `$demo` 跑兩次（base 是相對路徑，所以要在那個目錄裡跑）：

```bash
c++ -std=c++23 "$demo/deliver-demo.cpp" -Icore/inst/include -Icommon/include \
  -Lbuild/lib -Wl,-rpath,"$PWD/build/lib" -laos_inst -o "$demo/deliver-demo"
cd "$demo"
./deliver-demo
./deliver-demo
ls -1 inst.tempd
cat inst.tempd/*.json
```

輸出是（`90507` 之類的數字是實跑當下的 pid，每次都不一樣）：

```text
deliver=Ok name=90507-0.json count=1 inbox=inst.tempd
deliver=Ok name=90508-0.json count=1 inbox=inst.tempd
90507-0.json
90508-0.json
[{"argv":["printf","hello\n"]}]
[{"argv":["printf","hello\n"]}]
```

兩次呼叫得到兩份不同名的投遞，內容都是 canonical 的批陣列——投的是單一物件，落地的
是 `[{...}]` 加一個 LF。接著對同一個 base 呼叫 `aggregate_instructions()`，就會把它們
併成一批。
