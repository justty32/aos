# ideas — 構想記錄入口

← [WORKFLOWS](../../WORKFLOWS.md)｜[INDEX](../../INDEX.md)

記錄尚未進入 spec／plan／feature-dev 的產品構想。這裡保存的是**方向、心智模型與待釐清
問題**，不是已實作行為；構想準備落地時，再轉交對應工作流。

> **要重新拷問 aos 的人：先讀 [verdicts](verdicts.md)。** 九輪拷問的裁決已經收成一張表
> （已裁決／仍開著／欠帳／已驗證的實作缺陷），別重問已經拍板的東西。不該被改掉的優點在
> [call-format/keep](call-format/keep.md)。

## 目前構想

| 檔案 | 內容 |
|------|------|
| [verdicts](verdicts.md) | **九輪拷問的裁決總表**：已裁決（不必再問）／仍開著（值得打）／欠帳（裁決相乘產生的）／已驗證的實作缺陷。重新拷問的入口 |
| [turing-to-os](turing-to-os.md) | **根基論證**：圖靈完備三要件（可計算／可條件分支＝對環境反應、可連續執行自身＝體積不能無限膨脹）分別由 LLM／tooling／agent loop 擔當 → agent loop ＝ CPU → aos ＝ 以 agent loop 為計算單元的作業系統；檔案系統同時是記憶體與程式（含行程）的載體，lisp 是哲學參照。**中間推導的缺口已展開成 26 條**（[cpu-to-os-gaps.json](cpu-to-os-gaps.json)，五層：CPU 前提／OS 核心機制／資源管理／方便人／橫向對比失效處）；**2026-09-02 推導已補**（§三之一：OS 是「多」逼出來的——多程式／多次／多 CPU 要、多人不管；省略步驟分必然／理念／選擇；L0 拆歸 CPU 與 OS），14 條 `status` 已分、12 條待實作再分；另含使用者對「作業系統＝方便人使用」的四層定義 |
| [os-metrics-and-resources](os-metrics-and-resources.md) | **評估指標與資源觀**（2026-09-03 使用者口述，**口述進行中**）：一般 OS 的評估＝丟一堆**計算**任務量資源消耗（**主要是時間**）；aos 任務**抽象**、指標**多樣化**。**已定方向——目標優化指標是金錢（token）／可預測性／人類可理解性三項，時間空間只是「粗淺」優化**（順序是否為優先序未說）。另有資源的分配與管理、**權限很後面**、**可以理想抽象是因為跑在 linux 上＋時間粒度粗且允許不規則**；「還有其他東西」他還在回想、留空待補。含對照表與十四條 AI 觀察（評估變二維、原生資源清單＝linux 盲區、「記憶體」其實是 context、粒度粗故不需搶佔、可預測性已有兩個可量落點、三個目標互相拉扯） |
| [program-form](program-form.md) | **在 aos 上寫程式的形式**：類似 lisp，但原語是**檔案**、複合是**資料夾**，程式的載體就是資料夾；同像性的落點因此從 JSON 搬到檔案系統（改寫了 `G24`）。「只有 lisp 承載得了」**使用者同日收回**（改記為偏好，Python／Lua 也適合，因此同像性在撐什麼成了新問題），與四條邊緣狀況（資料夾無序、檔案更像 binding、哪棵樹正在被求值、quote 從哪來）。另含**寫的方式也是 lisp 的：REPL**——agent loop 就是 read-eval-print-loop、資料夾就是 image，以及它的四條裂縫——**使用者已裁決**：節奏差一個數量級不是缺陷（快／慢世界＋同時多個 REPL＋一次跑十幾分鐘很正常），其餘三條實作時自然有解 |
| [nested-eval](nested-eval.md) | **[program-form](program-form.md) 的續篇**（2026-09-03，因該檔超長另開；**無裁決**）：使用者問「list 的元素也可以是 list，那麼求值？」——AI 觀察把它拆成兩種巢狀：**運算式巢狀**由 flatten 在跑之前壓平成 ANF（中間值＝`out/` 的名字，執行期 `inst` 裡沒有巢狀）、**資料夾巢狀**是**作用域**，子資料夾預設 quote 住，父層的 car 點名才開＝`G14` 載入器＝unquote＝`G06` 行程誕生，於是資料夾求值是 **normal order**（`if` 剛好對味）。另有三個邊界（回傳 vs 傳訊、並行與 join、深度＝幾輪回不來）與一句總結：**aos 的答案是「不要在跑的時候巢狀」**，順序被 continuation 與 `out/` 的名字接管 |
| [nested-eval-car](nested-eval-car.md) | **[nested-eval](nested-eval.md) 的續節**（2026-09-03，因該檔會超長另開；**含一條裁決**）：使用者把資料夾寫成 `(.aos dir1 dir2 file1 file2)`——**car ＝ `.aos` 本身**（`series.json` 只是它裡面被先讀的檔），其餘項目是引數，而且**不會**像 lisp 先跑子資料夾的 `.aos`。AI 觀察：這個運算模型更貼的名字是 **fexpr／operative**（Kernel）而非 lazy——`.aos` 對子資料夾正好有三種「自己看著辦」的處置（當資料讀／`G14` 開它／`deliver` 轉手）；operative 拿得到的環境在 aos 就是資料夾本身（list 與環境同一個東西）；applicative 只是一種「先跑完子資料夾」的 `.aos`，所以 aos 是**預設不**、不是不能。兩個小修正：求值應為 `aos run` 不是 `exec`、引數依檔名故更像具名引數。**使用者同日已裁**：資料夾＝operative（fexpr）、子資料夾跑不跑全由父 `.aos` 決定、`f(g(x))` 的攤平是 `.aos` 內部的事——**兩層分開：`.aos` 內是 inst 鏈（機器層）、外是資料夾樹（行程層）**；`G06` 行程誕生＝父 `.aos` 開子資料夾。**同日再裁：頂層資料夾由使用者開（terminal `aos run`）或由他開的 daemon 代開，不是自宣告 `init`**——daemon 也可看成一個資料夾，再往上是 shell／systemd＝linux，故頂層不需特例 |
| [nested-eval-sugar](nested-eval-sugar.md) | **[nested-eval-car](nested-eval-car.md) 的續節**（2026-09-03，**含一條裁決**）：使用者觀察「inst 攤平／接力棒／`out/` 在這種情況下變成一種語法糖，因為複雜邏輯可以直接託付給子資料夾」，**同日裁定：inst 鏈是為省成本而存在的語法糖，不是本體**——本體只有**原子 inst**（工具／LLM 呼叫，不是資料夾、無法再往下託付）與**開／讀／選**。**同日續裁：inst 層與資料夾層互不相關**——資料夾不會被壓進 inst（AI 提的「編譯器把子資料夾壓成 inst 鏈」**已被否決**，痕跡留在檔內）；**inst 層＝POSIX 呼叫 ＋ aos 子命令**（`aos run`、`aos deliver`…）**的搭配，子命令就是包好的語法糖，資料夾層使用它們**。AI 觀察：兩層唯一的橋是 `.aos` 裡 `aos run <子資料夾>` 那一行且**單向**、C 語言線全關在 `.aos` 內、`.aos` 看起來像 shell script 是因為它本來就是；薄的 `.aos`（只做開／讀／選）今天不存在（`G14` 缺的）；父層那條資料夾層級的短接力棒要留，省成「材料齊了就跑」會變 Make ＝ applicative |
| [play-watchlist](play-watchlist.md) | **[nested-eval-sugar](nested-eval-sugar.md) 的續節**（2026-09-03）：使用者問「概念都差不多有概論了嗎、還缺啥」，AI 回答**主幹已齊，剩下四條缺口全在兩層之間那座橋上**——父層怎麼拿子資料夾的結果（回傳 vs 傳訊未裁）、子資料夾看不看得到父層（`../`，閉包有沒有落點）、失敗（子資料夾跑壞／inst 失敗／等太久，完全沒討論過）、資料夾壽命（暫態跑完留著還是刪，只講了生沒講死）。另記現況落差：今天的 agent 住在 `.aos/agents/` 裡（inst 層），照新模型該是獨立資料夾（operative）。**使用者已裁先玩不裁**，本檔是玩的時候的觀察清單（排程／資源計量／權限不是缺，是已裁先玩，見 [os-metrics-and-resources §九](os-metrics-and-resources.md)）|
| [exec-run-async](exec-run-async.md) | **`exec`／`run`／長任務與 `async:true`**（2026-09-04，**無裁決**）：檔案＝普通呼叫、資料夾＝跑 car；run 反覆 exec 到可見停止條件；agent 一圈至少三步。AI 反對用記憶體裡的執行緒做 async，提議糖仍走唯一的橋：自動開子資料夾、fork `aos run <child>`、結果落固定路徑，父逐步查看；timeout 與 async 是兩件事。另附現有程式同步 LLM 與整批並行但回合等最慢者的對照 |
| [exec-run-async-time](exec-run-async-time.md) | **[exec-run-async](exec-run-async.md) 的續篇**（2026-09-04，**無明說裁決**）：使用者傾向用環境限制做事前保證、timeout 只留作保險絲；使用者把 `async:true` 定義成子世界與父世界時序脫節。AI 觀察把規則收成「同步世界只放時間有上限的原子，時間看外面的搬去脫節子世界」，每個 `aos run` 是一個時鐘；因此今天 agent 步內同步等 LLM 與模型不合。另留「誰推子時鐘、父死後子是否繼續」兩題給實玩 |
| [daemon-clocks](daemon-clocks.md) | **[exec-run-async-time](exec-run-async-time.md) 的續篇**（2026-09-04，**無明說裁決**）：使用者傾向所有時鐘都由 daemon 走、父死子續走、集中登記以便關機一次全停；並說 fork 先不考慮。AI 觀察：daemon＝時鐘總管，登記表就是 daemon 資料夾這個 list；今天已有各資料夾分散的 `.aos/run.pid` 與單個 `aos stop`，缺跨資料夾總表與一次全停 |
| [land-rules](land-rules.md) | **[daemon-clocks](daemon-clocks.md) 的續篇**（2026-09-04，**無明說裁決**）：使用者定義一塊地預設只看自己，掛載／symlink 才能開洞；刪資料夾就是死，路徑是唯一標示符，搬家等於死。AI 建議 daemon 同查 pid＋路徑、孤魂補一刀，現在不做 `git mv` 式通知；真要搬就停時鐘後當新生，並附現有 `.aos/` 絕對路徑與 mv 破壞面對照 |
| [top-to-bottom](top-to-bottom/README.md) | **「資料夾＝list」整套模型的大白話總整理**（2026-09-03 使用者要求，**無新裁決、無新主張**，只重排既有材料）：從 **Linux → 你或 daemon（REPL）→ 資料夾樹（operative）→ `.aos` 裡的腳本（inst 鏈）→ 原子 inst → CPU 週期**一路講到底，八個檔各 ≤ 8 KB。含本套裁決一覽（附日期、指回 [verdicts](verdicts.md)）、為什麼這樣設計（三指標／深度＝幾輪回不來／RTOS／上微核心下大核心）、還沒定的（四條橋的缺口指回 [play-watchlist](play-watchlist.md)）、以及**現有 aos 對照表**（模型裡的名字 ↔ 今天程式裡的名字 ↔ 符合／對不上）。三種聲音（使用者原話／裁決／AI 觀察）逐節標明 |
| [fuse-host](fuse-host.md) | **aos 寄生在一個 FUSE 行程裡**（2026-09-03 使用者提出，**無裁決，不排進 OS 第一塊**）：daemon 整支變成一個支援 FUSE（把程式裝成資料夾給別人讀寫，Plan 9「什麼都是檔案」／9P 那一路，Linux 的殘影是 `/proc` 與 FUSE）的行程，整棵 aos 樹寄生在裡面。AI 觀察：daemon 從「盯著桌子」變成「桌子本身」，`deliver` 落在宿主手上不必輪詢；三個提醒——時間粒度會打架（aos 粗、FUSE 極細，宿主應只記下來、回合照原節奏推）、宿主死了樹是否還在（底下應仍是真目錄）、Lua 不該進 `.aos`（宿主的語言，不是第二種腳本語言）；現實面 WSL2／Manjaro 有 FUSE、Windows 原生沒有 |
| [fuse-host-doorman](fuse-host-doorman.md) | **[fuse-host](fuse-host.md) 的續篇**（2026-09-03，因該檔篇幅另開；**無裁決**）：使用者追問「不懂攔截紀錄、馬上回應是什麼意思」，AI 用「**門房還是廚師**」展開——宿主一定會被敲門（`ls`／自動存檔／`deliver` 都算）；**馬上反應**＝門鈴一響廚師就下去炒菜（門鈴太密、半成品被端走，傷可預測性）；**攔截加記錄**＝門房只存真目錄＋記本子，廚師（`core/loop`）照原節奏才去看，兩種當法分別對應「整個取代 loop」與「攔截＋記錄」；門房還能把「`.aos/` 給機器、頂層給人」的紙上約定變成真的擋得住。AI 傾向攔截加記錄（可預測性優先），**使用者回應「daemon 可以更漂亮」，方向認同、未選邊** |
| [fuse-host-impl](fuse-host-impl.md) | **[fuse-host](fuse-host.md) 再續篇**（2026-09-03，使用者說「都順便記下來吧」；**無裁決**）：**節一**（會不會麻煩、有沒有開源庫）——難的部分 `libfuse` 已做完，門房走 passthrough（穿透，底下一個真目錄原樣轉發）最簡單，libfuse 自帶範例；庫對照 C/C++ `libfuse 3`、Python `pyfuse3`／`fusepy`、Rust `fuser`、Go `go-fuse`、Lua 老舊不建議；AI 建議 C++ 直接接、門房當 aos 自己的子命令；會咬人處——只有 Linux 有、宿主當掉掛載點卡住（故底下必須是真目錄）、擋人靠 pid 查不是百分百嚴密、每次操作多繞一趟核心；只要記錄不要擋可用更輕的 `inotify`；規模估計穿透＋記錄＋擋人約 C++ 幾百行一兩天。**節二**（跟 tmpfs 差別）——tmpfs 是用記憶體做的桌子、後面沒程式；FUSE 門房後面永遠有程式；對照表列七項差異；兩者可疊但對 aos 不建議（穩態要留得住）；一句話：tmpfs 決定放哪、FUSE 決定誰管著 |
| [game-process-model](game-process-model.md) | **一次 `aos exec` ＝ 一格 `_process(delta)`**（2026-09-01 使用者口述）：能存取到的資料夾＝世界、cwd＝本體；決策照遊戲 AI 的 **GOAP**（觀察→目的→決策→行動）；超過預算的事等下一格。一次回應 `G01`（時鐘就是 tick）／`G09`（引擎從不搶佔，自願返回）／`G04`（GOAP plan ＝可存檔的架構狀態），但把 footprint 從「值得做」升為**必要條件**。同檔第三部分是同日口述的 **L1/L2 cache 類比**：判別式「刪掉它，世界語意變不變」——`run.pid`／`every/.last/` 是 cache、`every/<stem>.json` 不是、`turn` 之後會升格；ownership table 與 `.gitignore` 政策的分類判準 |
| [assembly-and-chains](assembly-and-chains/README.md) | **一段彙編語言＝一連串 `insts.json`**（2026-09-01 使用者口述，**已拆資料夾**）：`aos exec` 讀完就不管，下個指令從投遞收取——只有「當前」和「下個」，**沒有「未來十個」**；跳轉＝自己改下一格、中斷＝外部整個換掉；要規劃多步只能**指令自供給**。**裁決：留著批**。觀察：**pending 的投遞位就是 PC**、中斷只落 tick 邊界（C 區「沒有中斷線」可結）、`deliver` 碰撞規則是中斷語意的前置、自供給＝CPS 三處付錢、`inst`／鏈／批＝指令／行程／tick，**`B1` 被三條線同時需要**；**`series.json`**＝loop 另讀的一份檔，兼行程表（`G06`）／PC／排程輸入（`G16`）／可見窗口，`B2` 因此有答案方向。**同日續述的 C 語言線**：函數＝串模板、堆疊框與暫存器**兩種壽命都要**、型別正面壓上 `B5`；**重要裁決——複雜式另存新 json 由程式確定性拆平才進 series（LLM 不出場）**，於是長出**寫→編譯→執行**三段式生產線；源碼與 IR **兩個檔案**、界線畫在 `inst`，記法先裁 lisp 進場、**收工前改判全塔統一 json** |
| [theses-review](theses-review.md) | **根基三論的複審**（2026-09-01，主 session ＋兩個 fork；**全是 AI 觀察，不是裁決**）：同像性的承重點是**自我改寫**不是表達力（`G24` 該重問成「跑著的資料夾能不能被改寫再放回去跑」，`G07` 是它的代價、那個標記就是 quote）；CPU 與 REPL 唯一不矛盾的映射是**一句＝一回合＝一批、依賴一律跨回合**，兩讀法都靠批 header 餵飽；三要件分派錯位——**分支發生在 LLM 不在 tooling**，代價就是 `G05`；缺口分流——`G13` 與 `G18` 是唯二拖了會鎖死的，`fsync` 該插隊第一位 |
| [turn-based-folder](turn-based-folder.md) | 指定資料夾的回合制演化模型；`aos exec` 就是它的實作，抽象 CPU 疊在其上；`.aos` 版面、`.temp`／`.runi` 交接協定、`core/daemon` 與 agent loop |
| [llm-cpu](llm-cpu.md) | LLM CPU 疊在 `inst` 之上（`aos llm exec` + `.aos/insts/llm.json`）、自跑推理或當全域 daemon client 的取捨、跨資料夾排程與 I/O 交換區 |
| [inst-execution](inst-execution.md) | `inst` 的 env 繼承開關與非阻塞／背景執行策略 |
| [agent-messaging](agent-messaging.md) | agent 間訊息傳遞的語意失真為何無法用數學糾正、錯誤如何層層放大成錯誤風暴；三條對策：關鍵節點人類審核、多 agent 冗餘審核、固化 |
| [core-layering](core-layering.md) | `aos/core` 該切成哪幾個小專案：最核心 `exec`（`inst_t` + 執行它的函數，連 `timeout_ms` 都不要）→ `exec_loop` → 匯聚（注入式 lib）→ 再外面就當普通 inst，不繼續往外包 ；**已拿 [top-down-cli](top-down-cli.md) 的成品試跑過 B12 判準**：core 只差一個「分支」就封閉，agent 整套不進 core |
| [call-format](call-format.md) | 對 inst-POSIX 呼叫格式的兩輪拷問（已拆資料夾）：格式與序列化的九個缺口、fork/exec 是呼叫**機制**不是呼叫**約定**及界外六樣、以及不該動搖的部分。**使用者已逐條裁決** |
| [prior-work](prior-work.md) | 跨 repo 前作對照：`simple_tools/docs` 的 agent-world 設計（2026-08-12，比 aos 早兩天）逐條對上 aos 模型——Step／Round／tick 三尺度塌成一個「回合」、git 買不到 replay、path 不是 capability、「資料夾是世界」把表示當本體 |
| [top-down-cli](top-down-cli.md) | **從上到下的指令面**（2026-08-30，唯一從使用者介面倒推的一篇）：`aos pu init`／`aos pu run --step --interval`、`aos agent init`／`say`／`listen`／`talk --interface`／`state`；agent loop 靠「自我複製投遞」安插進 pu 迴圈；LLM 思考＝投遞到另一顆 llm pu 的 tempd |
| [machine-shape](machine-shape.md) | 這台機器的形狀（已拆資料夾）：真正的指令是**「批」而批沒有名字／header**、loop 沒有可分支的旗標、loop 現在住在 `core/inst` 裡與分層規劃相反、`.aos` 命名標準延伸不到 events／status、**唯一由外部生產者執行的投遞沒有實作**、規範已有三份真相 |

> **現況落差**：使用者已判定 `core/llms` 與 `core/tooljson` 是失敗作——它們不符合這裡
> 記的回合制／抽象 CPU 模型，之後要找時間改到符合。所以讀這些構想時別把現有程式碼
> 當成它們的實作。open 狀態記在 [SESSION-LOG](../../SESSION-LOG.md)。

> **落地順序**：這些構想要照什麼順序做、哪些決策擋著哪一階段，見
> [`roadmap`](../roadmap.md)。那份只排順序，模型定義仍以本目錄為準。

新增內容優先歸入既有主題；出現獨立方向時才新增內容檔。構想被正式 spec／plan 取代後，
在這裡改留指標，不讓 idea 文件與已拍板規格形成兩份真相。
