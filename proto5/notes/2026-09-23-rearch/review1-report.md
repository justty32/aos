## 1. 總評

**方向 OK，草稿目前不宜直接當作實作契約。** 問題集中在復原與交接，不需要推翻已拍板的架構。
CPU 的開機順序會清掉對帳依據；三種檔案組合也不足以判斷回音是否已被消費。
kernel 的接鏈、派工、收件都有跨檔崩潰窗口；`boot` 更繞過專用 CPU，首次啟動就可能同時跑兩格。
底層另有直接矛盾：`timeout_ms:0`、指示詞解析中心、`$ref:""` 的文件根，以及 executable 找不到時的 `kind`。以下為唯讀審查，沒有修改檔案。

## 2. A：正確性、一致性與洞

### CPU

**C-1｜在哪：[cpu §6，第 1–2 步](../../spec/cpu.md:208)／問題：先把對帳依據清掉。**  
第 1 步寫 `current=null`，第 2 步才讀 `state.current`。照文字執行，上一任留下的工作會失去身分，原 request 可能重新執行。  
**建議：**先讀取並對帳舊 state，再發布新主人的初始狀態；對帳完成前不得清掉舊 current。**嚴重度：擋。**

**C-2｜在哪：[cpu §6，第 2–3 步](../../spec/cpu.md:209)／問題：兩檔皆無不代表回音沒發出去。**  
時序可以是：刪 request → 發成功回音 → 收件者讀完刪 response → 主人尚未清 current 就崩潰。重啟會憑空再補 `Interrupted`，所以「沒有猜的空間」「收件者拿走後不再碰」均不成立。  
**建議：**補持久完成記錄或收件確認規則，讓「尚未發布」與「已被消費」可區分；單純交換刪檔與寫檔順序不夠。**嚴重度：擋。**

**C-3｜在哪：[cpu §4.3](../../spec/cpu.md:150)、[§6](../../spec/cpu.md:209)／問題：存在沒列出的第四種組合。**  
正常完成是「刪 request → 寫 response」，壞單和開機補 `Interrupted` 卻是「寫 response → 刪 request」。兩步間崩潰就會兩檔都在：先判 request 會覆寫既有回音，先判 response 而什麼都不做又會留下可重跑的原單。  
**建議：**統一正常、錯誤、恢復的完成規則，列出四種組合與判定優先序；恢復程序再次崩潰也必須能重入。**嚴重度：擋。**

**C-4｜在哪：[cpu §3、§6](../../spec/cpu.md:86)／問題：刪 request 後，原 JSON-RPC 身分無從恢復。**  
`id` 可以不同於檔名，但 state 只存 `current` 檔名。原單刪掉後，補 `Interrupted` 時既不知道原 id，也不知道原單是不是不得回音的 notification。  
**建議：**認領時持久保存原 id、是否有 id，以及恢復所需資料，不由檔名猜協議身分。**嚴重度：要修。**

**C-5｜在哪：[cpu §5.1–5.2](../../spec/cpu.md:170)／問題：四個停止來源沒有接成同一個狀態機。**  
只在取下一件前查看來源，長工作執行中便可能尚未讀到 pipe／檔案 stop；之後收到 TERM，到底是第一次溫和停，還是已在停機途中的強制停，沒有答案。檔案 stop 不靠檔名辨識，也須說清是否先掃完整個佇列。  
**建議：**明訂執行中如何接收並記住停止要求，以及後續訊號的升級規則；Python handler 可設旗標，再由執行監控處理。同種標準訊號可能合併，措辭應是「已處理第一次後，再處理到訊號」，不能保證快速連送兩次必然計兩次。**嚴重度：要修。** [Python signal](https://docs.python.org/3/library/signal.html)、[Linux signal(7)](https://man7.org/linux/man-pages/man7/signal.7.html)

**C-6｜在哪：[cpu §0、§5.1](../../spec/cpu.md:28)／問題：EOF 不等於父行程死亡。**  
EOF 表示所有寫端都已關閉且緩衝資料讀完；父可以活著但關閉管線，父死後也可能有其他行程留著寫端，導致永遠沒有 EOF。  
**建議：**改成「控制連線 EOF 視同 stop」，並明定父行程獨占寫端、不必要的繼承副本必須關閉。**嚴重度：要修。** [Linux pipe(7)](https://man7.org/linux/man-pages/man7/pipe.7.html)

**C-7｜在哪：[cpu §6–7](../../spec/cpu.md:214)／問題：回音寫不出去，不能再用回音回報。**  
刪 request 後，發布 response 遇到 ENOSPC／EACCES，規範沒有定義保留哪些資料、主人是否退出；§7 卻說 request 處理中的錯誤都回 response、不影響退出碼。  
**建議：**把發布失敗列為主人層級的 I/O 失敗，定義保留恢復資料、停止接新單與退出碼；不要讓「壞單也回音」涵蓋無法發布的情形。**嚴重度：要修。**

**C-8｜在哪：[cpu §0、§3.1](../../spec/cpu.md:24)／問題：奈秒時間戳不保證名稱唯一。**  
`time.time_ns()` 可能因時鐘解析度、同時交件或回撥而重複；request 已刪之後，`link` 也擋不住歷史名稱重用。  
**建議：**改稱「時間戳」，唯一性由交件者識別搭配計數或隨機值保證；EEXIST 只保證當下不覆蓋。**嚴重度：要修。** [Python time](https://docs.python.org/3/library/time.html#time.time_ns)

### Kernel

**K-1｜在哪：[kernel §3，第 1–2 步](../../spec/kernel.md:102)／問題：先接鏈仍然會斷鏈。**  
發布 `k-(N+1)` 後、寫入 `state.next=N+1` 前崩潰，下一格會因磁碟上的 next 仍是 N，被守門判成舊鏈丟掉。反過來先存 next，也會留下尚未發布後繼的窗口。  
**建議：**定義可恢復的接鏈提交狀態與補鏈責任者；不能只靠兩次獨立寫入保證「這格崩了，下一格照跑」。**嚴重度：擋。**

**K-2｜在哪：[kernel §3 第 5 步、§6–7](../../spec/kernel.md:160)／問題：boot 繞過序列化，`--seq` 不是互斥。**  
首次 boot 的 tick 0 已排入 tick 1，再啟動 kernel cpu；tick 1 此時就能執行，與尚未完成第 6–9 步的 tick 0 同時改 K。重複 boot 還會撞上已通過守門的舊 tick；重設序號也會重用 `k-1` 等名稱。  
**建議：**所有修改排程狀態的 tick，包括第一格，都經同一執行序列；boot 另定鏈世代與交接程序。失敗 boot 保留哪個 daemon 綁定、哪條鏈，也須一併定義。**嚴重度：擋。**

**K-3｜在哪：[kernel §1.2、§3 第 7–8 步](../../spec/kernel.md:60)／問題：缺少 request 對行程的映射。**  
派工後只記 `req="k-N-cpu"`，NAME 從 queue 拿掉，其他欄位也沒記它在哪顆 cpu。下一格收到回音，無從知道該更新哪個行程、讀哪份政策、轉交哪個 once。  
**建議：**在途記錄至少保存 request、NAME、行程世代；回音、計數與 rm 全部依這筆綁定處理。**嚴重度：擋。**

**K-4｜在哪：[kernel §3，第 7–9 步](../../spec/kernel.md:114)／問題：收件會永久失單，派件會重派。**  
讀刪 response 後、存 state 前崩潰，磁碟上的 req 永遠等一份已消失的回音；發布工作後、存 state 前崩潰，磁碟上仍是 req=null、行程仍在 queue，下格可用新名稱重派，甚至派到別顆 CPU。搬 done／bad、刪 once 行程與存 state 之間也缺恢復規則。  
**建議：**先持久記錄待送／待收身分與處理進度，再做可重複的發布及清理；修正「不會重派」「計數是準的」兩項保證。**嚴重度：擋。**

**K-5｜在哪：[kernel §3 第 5 步、§5](../../spec/kernel.md:109)／問題：spawn 結果未知可能產生同家兩個主人。**  
daemon 已 spawn，但回覆逾時，或 kernel 收到 child id 後尚未存 state 就崩潰。下格不知道該孩子身分，而 `ls` 只有 id／pid／alive，不能按 cpu 家找回；重送 spawn 就可能重複啟動。  
**建議：**在此先寫出必要的 daemon 邊界契約：spawn 可按穩定身分重試，或能按 cpu 家對帳；逾時代表結果未知，不代表沒有啟動。**嚴重度：擋。**

**K-6｜在哪：[kernel §3 第 5 步、§5、§8](../../spec/kernel.md:154)／問題：kernel cpu 不能靠已停掉的鏈重生自己。**  
kernel cpu 死了，下一格留在 requests，卻沒有 tick 能執行第 5 步拉起它。若死時 tick 還活著，它又可能成為仍在修改 K 的孤兒。  
**建議：**指定鏈外恢復者與舊 tick 的交接條件，或明訂這種情形需手動 boot；不能說它與工作 CPU 的恢復完全相同。**嚴重度：擋。**

**K-7｜在哪：[kernel §2、§3 第 6 步、§4](../../spec/kernel.md:87)／問題：once 的接受與延後回音缺少完整生命週期。**  
原 add 留著，下格重掃可能回 AlreadyExists；先刪，pending 尚未保存就崩潰則失單。pending 只存檔名，也不足以保存不同於檔名的 JSON-RPC id。一般 add／rm 的副作用、回覆與原單刪除順序同樣沒有交代。  
**建議：**明訂已接受請求的持久記錄、重掃判斷、原 id 與結果轉交狀態；once 完成與 rm 只能提交其中一種終局回音。**嚴重度：擋。**

**K-8｜在哪：[kernel §2 rm、§4](../../spec/kernel.md:88)／問題：rm 後同名重加，舊回音可能污染新行程。**  
X 正在跑 → rm X → add 新 X → 舊 X 完成。只有 NAME 無法區分兩代，舊回音可能增加新 X 的計數，甚至刪掉新 once；新 X 也可能先在另一顆 CPU 跑起來。  
**建議：**保留被 rm 那代的在途記錄與丟棄標記，並明訂名稱重用與不同世代重疊的規則。**嚴重度：要修。**

**K-9｜在哪：[kernel §2 stop、§3](../../spec/kernel.md:90)／問題：停止後仍可能派工，而且沒有收尾者。**  
第 6 步向 CPU 放 stop，第 8 步卻仍派新工；工作 CPU 完成當前工作時，kernel cpu 可能已退出，once 結果便無人轉交。下一格即使執行，也因 stopped 直接退出。  
**建議：**分開「停止新派工」與「完成收尾」，明訂在途工作、once 回音和排隊工作的去向；若留待下次 boot，須明講等待者會停在哪裡。**嚴重度：要修。**

**K-10｜在哪：[kernel §3、§8 第 1 點](../../spec/kernel.md:184)／問題：stop 不保證最多等一個 interval。**  
tick 睡完還要等 daemon `ls`，可能再等多次 spawn，每次可達五秒，之後才讀 syscall；daemon 一直出錯時，甚至每格都到不了 stop。  
**建議：**在可能阻塞或失敗的 daemon 操作之前處理停止要求，或撤掉目前的延遲上限承諾。**嚴重度：要修。**

**K-11｜在哪：[kernel §4](../../spec/kernel.md:126)／問題：判定表無法唯一決定計數與退件。**  
開頭 runs 加一，stopped 又說計數不動；error 加 fails 卻沒檢查 bad_after；非 aos 結果未必清 aos，會把不連續的兩次算成連續；stopped 要回 queue，但 once 又說任何结果都轉交並刪除。  
**建議：**先分 once／反覆，再列結果判定優先序及每個計數的完整更新，將退件門檻套到所有一般失敗。**嚴重度：要修。**

**K-12｜在哪：[kernel §6](../../spec/kernel.md:170)／問題：CLI 承諾拿不到的資料。**  
once 預設不等卻印 name，但省略 name 時是 kernel 分配，唯一回音又要等工作完成；stop 是 notification，卻被列入送件後等回音的客戶端。`--wait-ms` 也未列在用法。  
**建議：**不等模式由客戶端預先指定名稱或印送件識別；stop 明訂只確認送件成功，並補齊等待旗標。**嚴重度：要修。**

**K-13｜在哪：[kernel §1.1、§2](../../spec/kernel.md:47)／問題：池的合法性不足以保證可排程。**  
「有一顆 kernel 池」沒排除兩顆，後文卻依賴唯一一顆；一般 add 可指定 `pool:"kernel"` 或不存在的池，once 會無限等。  
**建議：**明訂恰好一顆 kernel cpu，拒絕一般行程使用保留池；不存在的池要拒絕，或明定為等待配置的狀態。**嚴重度：要修。**

### 跨文件與底層契約

**X-1｜在哪：[cpu §4.1](../../spec/cpu.md:128)、[kernel §3](../../spec/kernel.md:104)／問題：預設 tick 本身不合法。**  
CPU request 的 timeout 只准正整數，但 kernel 明寫 tick `timeout_ms:0`，一般行程預設也是 0；aos-exec 則明定 0＝不限。  
**建議：**統一為非負整數、bool 不算、0＝不限。**嚴重度：擋。**

**X-2｜在哪：[cpu §4.1](../../spec/cpu.md:128)、[kernel §3 第 8 步](../../spec/kernel.md:117)／問題：並列 timeout 尚未形成可執行的解析契約。**  
`{"$ref":"job.json","timeout_ms":5000}` 會依 directives 忽略 `$ref` 旁的 timeout；「整份解完才讀」因此丟掉 kernel 指定的上限。另外 `$env` 只產生字串，不能直接通過整數驗證；`load_obj` 本身也不解析 timeout。  
**建議：**CPU 另行保存、解析 timeout，寫清來源優先序與解析 context；inst 仍照既定欄位順序解析，不能通用遞迴展開整份 JSON，否則會改掉未知欄位忽略、`_metainfo` 和 `$opt` 的語意。**嚴重度：擋。**

**X-3｜在哪：[cpu §4.1](../../spec/cpu.md:123)、[inst-posix §3.1](../../spec/inst-posix.md:94)／問題：`base=C` 不等於所有中心固定 C。**  
現有 `load_obj({"cwd":"sub","stdout":"out",…}, base=C)` 得到 `C/sub/out`；解完 cwd 後，其他 `$ref` 也以 cwd 為中心。這和「相對路徑／$ref 的中心一律是 CPU 家」不同。  
**建議：**保留已定的 CPU 中心方向，但明列 CPU 宿主的解析差異與適配方式，不能同時聲稱直接 `load_obj(params, base=C)` 就與 inst 完全相同。**嚴重度：要修。**

**X-4｜在哪：[cpu §4.1](../../spec/cpu.md:125)、[load_obj](../../lib/aos_inst.py:91)／問題：`$ref:""` 的根不是整個 request。**  
`load_obj(params, …)` 的文件根是 params，故 `/argv/0` 有效、`/params/argv/0` 無效；進入外部 `$ref` 後，目前文件還會切換成被引用的文件。  
**建議：**改寫成「最初文件是 params，之後依 directives 跟隨目前文件」；若真的要 request 根，必須另傳文件與位置 context。**嚴重度：要修。**

**X-5｜在哪：[cpu §4.1 result](../../spec/cpu.md:141)、[aos-exec 退出碼](../../spec/aos-exec.md:53)／問題：找不到程式的分類改了。**  
CPU 把 executable 找不到列為 kind=aos；底層明定是 child／127，沒執行權是 child／126，exit 檔照寫。這會使 kernel 從一般失敗變成「連續兩次 aos 就退件」。  
**建議：**沿用底層分類，並明定 result 中 aos 的 code 是 API 的 1，還是正規化後的 125。**嚴重度：要修。**

**X-6｜在哪：[cpu §3、§4.1](../../spec/cpu.md:80)、inst-posix §3.3／§6／問題：工作串流會撞控制 pipe。**  
合法的 stdin inherit 會讓工作與 CPU 競讀 fd 0，可能吃掉 stop；stdout inherit，包括 stderr merge，會把一般輸出灌入控制回程。  
**建議：**CPU 啟動時將控制 pipe 轉到私有、不傳給工作的 fd，另定工作可繼承的標準串流；不能只靠 `close_fds=True`，它保留標準 fd。**嚴重度：要修。** [Python subprocess](https://docs.python.org/3/library/subprocess.html)

**X-7｜在哪：[cpu §3、§4.3、§6](../../spec/cpu.md:82)／問題：合法 notification 被要求回音。**  
未知 method 的合法 notification 仍不得回覆，§4.3 卻一律寫 response；§6 正常／Interrupted 回音也漏掉這個分支。此外未完整定義 method、id 型別驗證。  
**建議：**區分壞信封與合法 notification：前者按 JSON-RPC 回錯，後者即使 method／params 錯也不回；補 method 必須字串、id 的合法型別，且 `id:null` 不是省略 id。**嚴重度：要修。** [JSON-RPC 2.0](https://www.jsonrpc.org/specification)

**X-8｜在哪：[kernel §1.1、§6](../../spec/kernel.md:53)、directives §1／問題：boot 綁 daemon 會被頂層 `$ref` 吃掉。**  
若 info 是 `{"$ref":"base.json"}`，boot 只在外層加 `daemon:D2`，整份解析仍忽略它，繼續用引用內的 D1。舊 findings #49 已專門修過這件事。  
**建議：**保留外層 daemon 綁定的明確優先規則，或明訂 boot 如何重寫配置及其固化效果。**嚴重度：要修。**

Linux 基礎操作本身沒有問題：`link` 的 EEXIST、同目錄 rename 的原子替換都成立；它們不提供多檔交易。若「開機對帳」只指行程重啟，不必為缺 fsync 判擋；若包含斷電，則須另外定義落盤保證。process group 的限制也應寫成「離開原 group 的後代」，不只有另開 session。[link(2)](https://man7.org/linux/man-pages/man2/link.2.html)、[rename(2)](https://man7.org/linux/man-pages/man2/rename.2.html)、[fsync(2)](https://man7.org/linux/man-pages/man2/fsync.2.html)、[setpgid(2)](https://man7.org/linux/man-pages/man2/setpgid.2.html)

## 3. B：給人讀的品質

**R-1｜在哪：cpu 開頭「一句話」。**  
四件套說清楚了，但「每則只跑一次、反覆由 kernel」才是這次最重要的改變。建議寫：「一顆 exec cpu 是一個資料夾加一個主人行程，逐件把 request 裡的 inst 跑一次，寫回同名 response；反覆排程交給 kernel。」

**R-2｜在哪：kernel 開頭「一句話」、§8。**  
tick 鏈的重點有講到；「整個系統只有一種通訊方式」卻與檔案／pipe 兩條路矛盾。建議改成：「工作與 syscall 走資料夾，父子生死控制走 pipe，兩者共用 JSON-RPC 信封。」

**R-3｜在哪：cpu §0 名詞表。**  
目前不是太多，而是缺少真正容易混淆的組合：inst／request／response、base／cwd／目前文件，以及 kernel 家／專用 kernel cpu 家。建議補這幾組；`link`、暫存檔的操作細節移到 §3.1，名詞表留一句用途。

**R-4｜在哪：cpu §0「主人」、§1；kernel §1。**  
「唯一會改資料夾」立刻遇到外人投件、刪回音、人寫 info、kernel 初始化 CPU 家等例外；巢狀的 `K/cpus/` 又容易讓人以為 K 的主人管整棵子樹。建議寫成「唯一管理該家的執行與狀態者」，列明投收件接口及啟動前初始化邊界。

**R-5｜在哪：kernel §1 資料夾圖、§1.3、§2 add。**  
圖說 procs 放「解好的 inst」，後文卻原樣收、到 CPU 才解。建議統一為「收到的 inst＋政策」，另外註明 CLI add 會預先解析，直接 syscall 可以保留指示詞。

**R-6｜在哪：kernel §1.2 範例與 §3。**  
req／pending 被稱為「檔名」，例子卻沒有 `.json`；cpu.current 則有。建議兩份統一保存完整檔名，或統一稱為運輸識別並明訂加副檔名的地方。

**R-7｜在哪：cpu §6、kernel §3。**  
最難讀的都是「做一半後下次怎麼接」。建議 CPU 用四組存在狀態表；kernel 九步逐步標示讀取、發布、持久提交、可重做與不可再做的動作，取代「沒有猜的空間」「下次重來」這類結論句。

**R-8｜在哪：kernel §1.1、§3、§7。**  
「週期」實際是 sleep 加處理時間；「FIFO」實際又受 CPU 檔名字典序影響，`k-10` 排在 `k-2` 前。建議分開說明 tick 間隔、行程最早再派時間、CPU 取件排序；正常只有一個後繼時也明說此前提。

**R-9｜在哪：kernel §1.2 範例、§3 第 4／7 步。**  
kernel cpu 的 req 混在工作 CPU 表內，但第 4 步已清它的回音，第 7 步又收每顆 req 非 null 的 CPU。建議明訂 tick 回音走獨立處理，kernel cpu 不進一般工作收件流程。

**R-10｜在哪：cpu §4.1、§5.4，以及兩份 §8。**  
串流「預設」應指 inst-posix §3，§6 是執行語意；四個溫和停來源實際在 cpu §5.1，kernel 目前沒有 §5.1。另建議把已拍板前提從「我自己選的，等確認」移出，避免讀者重新猜哪些仍待決。

## 4. 痛點對照表

F＝[findings](../../../proto5.1/notes/findings.md)；舊 R＝[review-fable](../../../proto5.1/notes/review-fable.md)。舊 R1–R3、R5–R9、R14–R27 已在後續修過，以下判的是新草稿是否保留修正；「解了」指規範結構，不代表新實作已驗證。

| 舊項目／來源 | 判定 | 新草稿的效果與剩餘問題 |
|---|---|---|
| [cpu-simpler](../../backlog/cpu-simpler.md)；F1、8、10、19 | 解了舊機制 | 單一主人消除多 consumer 認領、短鎖、running 搬移、inode 核對；link 正確解決當下同名覆蓋。 |
| F27、35、40、51：換槽、短間隔飢餓、idle/null 窗口 | 解了舊機制 | 不再用符號連結換槽，也不靠 runner 自己反覆跑；新的提交窗口另見 K-4。 |
| F30、41、47；舊 R5；kiss-holes #6：漏中間退出碼 | 部分解 | 逐次回音消除快照資訊不足；收件後崩潰仍會漏計，見 K-4。 |
| [request-identity](../../backlog/request-identity.md)；F11–13、18、23、26；kiss-holes #1、7 | 沒解交易問題 | 獨立回音名稱減少串單，但送件／記帳、收件／記帳仍分離；C-2、K-4、K-7。 |
| kiss-holes #2；F8、23：排隊與等待無期限 | 沒解 | 不存在的池、停鏈、未完成 once 都能永久等待；CLI 超時不等於工作取消。 |
| F20、46、52；舊 R2、15、18、27：壞單堵整顆 CPU | 部分解 | 固定 responses 讓壞 JSON 有回址，非法自訂結果路徑消失；發布 I/O 失敗處置漏寫，見 C-7。 |
| F4、25、32、39、48：timeout、執行失敗、結果不明 | 部分保留 | 真實 timed_out 與 Interrupted 方向正確；找不到 executable 的 kind 改錯，見 X-5。 |
| 舊 R8；F48：回音格式分裂 | 解了格式分裂 | JSON-RPC 信封統一；notification 與恢復回音仍須修，見 C-4、X-7。 |
| 舊 R3、7、12、20、22、23；F50：hold 忙轉、idle 直譯器、重寫 procs | 解了主要機制 | hold／idle／舊計數欄位消失，procs 不再每格重寫；但 `poll_ms=0` 仍允許空閒忙掃。 |
| 舊 R6；F50：daemon 閒著重寫 state | 尚未處理 | CPU 已說閒置不重寫；daemon 的既有修正待其新規範保留，不是本次阻塞。 |
| 舊 R10：中止後等收屍才有回音 | 通常情形解了 | 強停回 stopped；KILL 靠重啟補 Interrupted，但目前對帳有 C-1～C-4。 |
| 舊 R11：工作與 kernel 共用 interval | 部分解 | CPU poll 與 kernel interval 分開；收結果、派下一件仍受 tick 延遲影響。 |
| 舊 R13；F9：mtime／牆鐘收屍 | 解了舊機制 | 不再按逾期 mtime 猜死亡；取代它的父子與重生契約仍須補齊。 |
| 舊 R4；kiss-holes #3：主人死而子程式活著 | 沒解，明確接受 | cpu §5.3 已列保證外；kernel §7 的不重疊宣稱也須排除這種情形。 |
| [kill-tree-exceptions](../../backlog/kill-tree-exceptions.md)；F28、42 | 沒解，方向已改 | 不做 kill-tree 是既定方向；同 group 個別存活例外並未因此實現。 |
| 舊 R1、16；F45；kiss-holes #5：daemon 死後孤兒與重啟重疊 | 部分解／待 daemon | EOF 停止接新單的方向可行；舊 CPU 尚活時不得同家再起的邊界仍要保留，見 C-6、K-5。 |
| F29、33、42；舊 R17、21、25：daemon 副作用、回音、停機预算 | 部分解／待 daemon | RPC ls 與超時代號有定義；spawn 結果未知仍沒解，見 K-5。 |
| F43：新 runner 家避免吃舊 ctl | 舊機制消失，新限制需寫 | 固定 CPU 家會保留 queued stop；重複 stop、崩在刪 stop 前、重 boot 如何消費舊控制單尚未定義。 |
| F31：inst 搬家失去解析中心 | 部分保留 | CLI 先解、直接 RPC 到 CPU 才解是明示的新契約；實際 base／cwd 說法仍矛盾，見 X-3、X-4。 |
| F34：工作 timeout 砍 kernel 控制流程 | 意圖保留，契約有錯 | tick 不限時已寫，但其 0 值被 CPU 拒絕，見 X-1。 |
| 舊 R9；F49、53：daemon 綁定與失敗 boot | 部分保留，有回歸風險 | K 記 daemon、name／pid 分開；頂層 `$ref` 綁定與失敗復原漏寫，見 X-8、K-2。 |
| [agent-fail-state](../../backlog/agent-fail-state.md)；F3、5、6、13、14、21、22、38 | 沒解，屬 agent 後續 | consume、批次讀驗、工具記憶自癒不因 transport 改變自動解決；依前提不列本次阻塞。 |
| kiss-holes #4：其他入口同時跑同一 agent | 沒解，已接受邊界 | 排程行程身分不等於 agent 家的排他；但 boot 自己造成並行不能用此邊界豁免。 |
| [tool-call-order](../../backlog/tool-call-order.md) | 沒解 | FIFO 派工不等於工具依賴順序，多顆同池 CPU 仍可並行。 |
| [llm-cpu-fallback](../../backlog/llm-cpu-fallback.md)；F15、24、36 | 沒解，責任移到程式 | pool 不提供 endpoint failover，也不自動提供模型設定與金鑰隔離。 |
| 舊 R24、26；F37、48：LLM／tool CPU 特例 | 解了舊機制 | 薄層與工具串流接管特例消失；改由 inst 指定檔案，但 inherit 控制通道衝突須修，見 X-6。 |
| 新 tick 鏈、boot、序號重用 | **新引入** | 接鏈提交失敗、首次 boot 並行、kernel cpu 無法自救，見 K-1、K-2、K-6。 |
| 新 kernel 派工／收件狀態 | **新引入到排程層** | 舊跨檔交易問題擴散到排程控制，能重派同一工作或永久占住 CPU，見 K-3、K-4。 |
| 新 once 延後回音與 rm | **新引入** | 接受狀態、原 id、取消、同名新世代和停止後轉交都需持久規則，見 K-7～K-9、K-12。 |

F2、7、17、44、54 與舊 R19 是測試、環境、修改範圍或舊連結紀錄，不是這兩份規範要解的運作痛點。