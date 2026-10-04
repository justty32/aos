← [思考筆記](2026-10-04-r3-synthesis.md)｜Fable 原報告：aos 的「C 語言」會長什麼樣（使用者 10-04 題目；第四輪會一起納入）

# aos 的「C 語言」會長什麼樣？（思考報告，Fable，2026-10-04）

題目：[brief4](brief4.md)。只讀 repo，沒改任何東西。依據：原則（`proto7/notes/principles.md`）第 1、3、5、7、8、9 條、核心 spec S-01／S-04／S-10／S-11／S-12／S-16／S-20、proto7-2 spec §4～§8、core-slimming §5／§10、r3 綜合。**這些都是提案，不是決定。**

## 0. 結論先講

1. **aos 已經有一個「語言」，但它不是 C，是 PLC／HDL 那種時鐘式語言：程式＝tasks.json，指令＝表上的一項，時鐘＝tick-tock，暫存器＝槽裡的檔。** tick 是直譯器，每回合重讀一次程式（`tasks_rev` 就是「這回合跑的是哪一版」）。
2. **inst 不是 aos 的 C，是 aos 的 `execve` 結構**：描述「一次 POSIX 執行」的參數塊（argv、串流、cwd、envs），沒有順序、分支、迴圈、等待。tasks.json 的一項＝inst 加上時間（mode、from／until_round）、空間（mounts）、身分（name、槽）——那才是完整的一條指令。
3. **「Linux 用 C 寫、也跑 C 程式」在 aos 成立的版本是：kernel 用 tasks.json 項目寫、也管 tasks.json 項目。** 多出來的一點是 kernel 會改程式（selfmod、supervisor 探針）：在 C 是禁忌，在 aos 是常態，因為程式就是一份可原子覆寫的檔。
4. **推薦第三條路**：語言不進核心，核心零要求。缺的那層「順序＋等待＋重試＋停」做成一個**任務包**：一支 keep 的小直譯器任務，吃一份步驟表（像 IEC 61131 的 SFC：步／轉移），每步展開成 once 子任務＋等 exit.json。先不做、記格式。
5. **LLM 直接寫 tasks.json＋inst 夠用於「常駐」和「單發」，不夠用於「有順序的多步工作」**：selfprog 的三個真模型都卡在 keep／each／once 的時間語意，不是卡在語法。步驟表給 LLM 的是它本來就會寫的東西——一張有序的計畫。

## 1. 類比先對準

### 1.1 哪裡不對：語句在 CPU 時間上執行，任務不在

C 的語句是**同步、順序、單一控制流**：下一句等上一句。aos 的任務是程序，彼此**預設並行**，`tasks.json` 的排列不保證前一項做完（r3 綜合已定）。所以「任務＝語句」推到底會卡在第一步：aos 沒有「下一句」。

對得上的機器不是 von Neumann，是**同步時序電路**：

| 時序電路／PLC | aos | 出處 |
|---|---|---|
| 時鐘緣 | tick 結束（回合開始）、tock 結束（回合結束） | S-08 |
| 掃描週期：讀輸入映像 → 執行所有程式塊 → 寫輸出映像 | tick 讀 tasks.json 快照（`tasks_rev`）→ 任務跑 → tock 判槽、寫 last-round.json、再通知 | spec §4.2、§7 |
| 所有 always 塊並行、暫存器在時鐘緣同時更新 | 所有項目同一個 tick 起；「上一次」檔在 tock 一次提交 | A2-12 |
| 暫存器（跨週期保值） | 槽裡任務自己的檔（state.json，換 run 不清） | spec §5.1、§8 |
| 組合邏輯（週期內算完） | 任務內部，任何語言 | S-04 |
| 多個時鐘域 | 多條時間線；跨域只比依據版本、不換算回合 | S-05、r2 綜合 |
| 非同步重設／中斷 | wake、ctl kill、pause | spec §2.3、§6 |

這張表說明一件事：**aos 的「程式」天生是兩層的**。回合層（誰在哪一回合起、靠什麼檔接續）是 PLC 式的；任務內層（這個程序裡怎麼算）才是 C／Python／sh。aos 不需要自己的 C，任務內層已經有一百種語言；它需要的是回合層的**程式組織單元**。

### 1.2 把對應推到底

| C 的概念 | aos 的對應 | 備註 |
|---|---|---|
| 變數 | 檔案。槽內自己的檔＝`static` 區域變數（活過 run、隨槽刪而亡）；node 根＝全域；`.aos/` 核心檔＝唯讀暫存器 | spec §5.1、契約卡檔案所有權表 |
| 賦值 | 原子覆寫（tmp＋rename）；多寫者要 `flock`（tasks.json） | spec §0 |
| 型別 | 檔案格式＋契約（`need`、schema）；三態 ok／unknown／absent 就是 `Option` 型別 | r3 綜合、component-contracts |
| 指標 | 路徑字串。ENOENT＝空指標（N）、讀不到／壞掉＝懸空（U）；掛載＝別名／`extern`；`mount_allow`＝可見度 | S-23、spec §4.5 |
| 作用域 | node（cwd、環境、掛載表）；槽是第二層 | S-10、S-13 |
| 順序 | **沒有語言級的順序。** 只有三種：任務內部；`from_round`（絕對時刻）；「等某個檔出現」（檔案協定） | r3 綜合「一條鏈一個程序」 |
| 分支 | 任務自己讀檔判斷；外部能做的是 `enabled`／改表（kernel 當分支器） | spec §4.1 |
| 迴圈 | `keep`＝`while(true)` 重起；`each`＝每回合一次；`once`＝一次；`until_round`＝迴圈上限 | spec §4.1 |
| 函式呼叫 | once 子任務＋等它的 exit.json；參數走 argv／inst，回傳走 exit code＋槽外交付物。**呼叫延遲 ≥ 1 回合**，是 `await`，不是 `call` | spec §4.4、§5.1 W7 |
| 遞迴／新堆疊 | 子 daemon（路一）：一個 call 開一條新時間線 | S-21 |
| 並行 | 預設；`max_live`＝幾個槽 | spec §4.1 |
| 錯誤處理 | exit code 慣例（0／非 0／125）、三態、kill；沒有 unwind，只有「保留現狀、下一圈再看」 | 錯誤四分支 N／U／B／K |
| 記憶體管理 | 槽重用＝固定位址；核心只留上一次＝沒有堆；tock 刪槽＝GC（報完一回合才收） | spec §5.1、§8 |
| 編譯 vs 直譯 | tick 直譯 tasks.json，每回合一次；「編譯」＝把高階東西展開成表項（pack install 就是） | core-slimming §10.4 |
| 連結器 | 掛載（把別人的 out/ 接進來）＋pack 依賴檢查 | S-23 |
| 標準函式庫 | 任務包（supervise、schedule、account、relay／adapt、observe） | core-slimming §10.3 |
| 自我修改程式 | kernel 改 tasks.json、agent 改自己的表（selfprog）——合法而且是主要控制手段 | S-17、selfprog |

**唯一的阻塞原語**是 `wait_tock`（等下一個時鐘緣）。其他「等」都是「每回合看一次檔」。這跟 HDL 一樣：沒有 `sleep(ms)`，只有 `@(posedge clk)`。

## 2. inst 在這張圖裡的位置

**它是什麼**（讀 `proto7-2/lib/aos_inst.py`、`aos_exec*.py`、`proto6/spec/inst.md`）：一份 JSON 描述**一次** POSIX 執行——`argv`（必填）、`stdin`／`stdout`／`stderr`／`exit`、`cwd`、`envs`，加四種指示詞 `$env`／`$fmt`／`$ref`（可跨檔、有循環偵測）／`$opt`。`aos-exec` 跑一份回 `(code, kind)`。沒有 shell、不展開萬用字元、不收輸出、不注入 `AOS_*`。proto6 的話是「任務表的每一項是 inst 的超集」。

**它能表達什麼**：一條 exec 指令，以及「這條指令的參數從哪裡來」。`$ref` 已經是一個小型取值語言（JSON Pointer 加相對位置），這正是 r3-fable 警告的「表達式語言長成怪物的起點」——目前守住了（只取值、不運算）。

**缺什麼**（相對於「語言」）：順序、條件、迴圈、等待、錯誤分支、呼叫別的 inst。**多什麼**（相對於「一條指令」）：跨檔引用與循環鏈——這是連結器的活，塞在指令編碼裡。

**repo 其實已經走過一次「要不要往語言長」**：proto6 的 tick 有 `hooks`（before_all／after_task／after_all）、`tasks-blocked`（先跑一串 inst 清障再看）、`kind`、`id`——這些是順序與條件的苗頭。proto7-2 spec §9 明說「不選核心提供每回合鉤子」，core-slimming §5.1 把 D（同步 hook）、E（進程內外掛）、F（op 外掛）全部否決。**結論一致：核心不長語言。**

**定位一句話**：inst 是 aos 指令集裡的 `exec` 欄位（機器碼的運算元編碼），tasks.json 的一項是完整的一條指令，tasks.json 整份是一支 PLC 程式。S-12「tick 用 inst JSON 當基底，因為它在 Linux 上最通用」說的是**可攜的 ABI**，不是語言。它已經做到該做的，不需要再長。

## 3. 三條路

| | (a) 有一個 aos 語言（核心認得） | (b) 沒有語言：任務＋任務包＋檔案協定 | (c) 語言是一個任務包：直譯器任務吃步驟表 |
|---|---|---|---|
| 核心改動 | tick 要解語法、管順序、管等待——每個結構都是新的邊緣狀況（proto6 hooks 的教訓） | 零 | 零（只用 once＋exit.json＋edit_json＋ctl） |
| 順序／重試／預算 | 語言級，寫一次 | 每個人手寫；selfprog 證明 LLM 會寫錯 mode | 步驟表級；錯了只壞那個任務 |
| S-01 LLM 可讀 | 看語法；JSON 的話可讀 | 可讀，但「程式」散在多個檔與多個任務 | 一份 JSON 步驟表＋槽裡的 `pc` 狀態，`cat` 一眼看出跑到哪 |
| 原則 7／9（核心精簡、KISS） | 衝突 | 合 | 合 |
| 原則 3（單 node 視角） | 無關 | 合 | 合（直譯器只在自己 node 跑） |
| 原則 5（通用 vs agent） | 語言是通用的，但動機來自 LLM | 通用 | 通用（cron、備份、CI 都用得到） |
| 失敗模式 | 語言 bug＝核心 bug | 模式散落、重複、不一致 | 直譯器任務掛了＝一個任務掛了；keep 起回來接 `pc` |
| 跟 kernel 任務包的關係 | 搶同一塊（supervise 也在做重試） | supervise／schedule 包就是「用改表實作控制流程」 | 步驟表是「單一工作內的控制流程」，supervise 是「多個常駐任務之間的」——不重疊 |

**(c) 有兩個口味**：
- **(c1) 展開式**：編譯器把步驟表展開成一堆 `once` 項（`from_round`、`slot`、`restart_of` 都現成），之後每回合改表。這其實就是 kernel 的 supervisor／scheduler 已經在做的事——所以 (c1) 不是新路，是任務包的既有方向。
- **(c2) 直譯式**：一支 keep 任務（暫名 `aos7-step`）每收到 tock 讀自己槽的 `state.json`（`pc`、重試計數、等哪個子任務），照步驟表前進一步：要跑東西就 `edit_json` 加一項 `once`（`slot` 釘名）並記下 run id，下回合看 exit.json。**推薦先想這個**：單一程序、單一寫者、狀態一目了然，而且 keep 保證它死了會回來接前任。

**第三條路的本質**：aos 的 C 不是「寫 kernel 的語言」，而是「kernel 之上、任務之內」的一層小語言，核心把它當普通任務。這跟 PLC 完全一樣——掃描引擎（韌體）不認得 SFC，SFC 是跑在引擎上的程式組織單元。

## 4. 歷史類比：借什麼、避什麼

| 來源 | 貼近 aos 的點 | 借 | 避 |
|---|---|---|---|
| **PLC 週期掃描（IEC 61131-3）** | 掃描＝回合；輸入映像凍結後才執行＝tick 的 `tasks_rev` 快照；輸出在週期末一次寫出＝tock 先提交 last-round 再通知；**SFC**（步／轉移／動作）＝回合制狀態機的標準寫法 | SFC 當 (c2) 步驟表的骨架：一步＝一個狀態，轉移＝檔案條件或 exit code，動作＝起 once 子任務；每步至少佔一回合 | 全域單一 I/O 映像記憶體（aos 用檔案＋node 天然分區，不要收成一張表）；ST／LD 那種完整語言 |
| **HDL（Verilog／VHDL）** | 所有 always 塊並行、非阻塞賦值在時鐘緣同時生效、多時鐘域要同步器 | 用「兩相時鐘」把讀寫時機說死：tick 讀的是上一回合末的世界，tock 提交這回合——spec 其實已經這樣做，缺的是把它說成一句規則；跨時間線＝跨時鐘域，只能經同步器（轉接包）| 模擬器的 delta cycle、零延遲假設——aos 的 tick 不準時是設計（S-08） |
| **Make** | 宣告式；「目標檔不存在或比依賴舊」就做；每次重算 | 以檔案存在／新舊當轉移條件（`once` 的 `launch` 標記、`exit.json` 的 `seen_round` 已是 .stamp 檔）；Make 一次跑完，aos 是 `watch make`——每回合重算一次是對的 | 依賴圖放進核心；隱式規則 |
| **Erlang／OTP** | 程序＋信箱＋supervisor 樹＋let it crash | supervisor 當任務包（supervisor 探針已跑；`spawn_tock` 模式零違規）；「一個 run 一個身分」＝pid 不重用 | link／monitor 進核心；熱更新機制（aos 的熱更新就是改表） |
| **Unix shell＋管線** | 小程式組合 | 任務包就是 coreutils：一件事一支程式，用檔案接 | 管線的 fd 連接（隱式順序、背壓）——aos 的邊是檔案，不是 fd |
| **Plan 9 rc／namespace** | 每程序自己的命名空間 | 已借（掛載＝namespace；other-os-borrow §1） | — |
| **資料流語言（Kahn、Lucid）** | 節點＝任務、邊＝檔案、tock＝fire | 「輸入齊了才跑」做成 gate 任務（gang 探針的 prepare／commit 就是） | 阻塞讀；token 計數（aos 的檔是覆寫暫存器，不是 FIFO） |
| **工作流引擎（Airflow 等）** | DAG＋scheduler＋每次 run 一個 task instance＋retry／backoff 宣告 | retry／backoff／timeout 當**宣告欄位**放在步驟表或 supervise 包的設定，不寫成程式 | 中央 metadata DB；DAG 綁 Python；scheduler 跟 executor 分不開 |
| **LLM agent DSL（LangGraph 類）** | 顯式 state＋節點圖＋條件邊 | state 是一份 JSON 檔、人和 LLM 都能 `cat`（S-01）；條件邊＝轉移 | 節點是語言內函式（綁 Python，違 S-04 精神） |

**最貼近的是 PLC 的 SFC 加 HDL 的時鐘語意**：前者給「程式長什麼樣」，後者給「什麼時候讀到什麼」。Make 第二（檔案即條件）。Erlang 第三（supervisor 包已在路上）。

## 5. LLM 的角色

- **證據**（selfprog，三個真模型 82 次呼叫）：都算對答案、都沒把自己弄死；但一次性工作寫成 `keep`（14 次）或 `each`（63～69 次）、把讀 tock.json 當成「等」（7 輪空轉）、找不到結束任務的紀錄。**錯的全是時間語意，不是 JSON 語法。**
- **為什麼步驟表對 LLM 比較好寫**：LLM 的自然輸出是「先做 A，成功就 B，失敗重試三次，超過預算就停」——一張有序計畫。tasks.json 要它把這張計畫翻成「三個獨立的常駐／每回合／一次性項目＋自己記得拿掉」，翻譯本身就是錯誤來源。步驟表讓 LLM 寫它本來就會寫的形狀，由直譯器任務負責翻成 once＋等待。
- **為什麼也好讀**：槽裡的 `state.json` 寫著 `{"pc": "retry", "tries": 2, "waiting": "handle#57"}`，一個只會 `cat` 的 LLM（或人）就知道卡在哪——這正是 S-01 的檢驗方式。
- **LLM 直接寫 tasks.json／inst 夠不夠**：常駐（keep）、單發（once）、定時（from_round）夠；多步、有條件、要重試、要停的工作不夠——它會退回「寫一支 Python 自己管」（可以，但每個 LLM 寫一版，而且寫錯 mode 的風險還在）。
- **別忘了 agent 本身就是直譯器**：idle／think／act 狀態機（S-19）吃的「程式」是自然語言目標。hsched 的結論「LLM 提政策、確定性執行」套在這裡就是：LLM 寫步驟表（慢路徑、可審），直譯器任務執行（快路徑、確定性）。步驟表是這兩者之間的穩定中間表示。

## 6. 小例子：「每回合檢查信箱，有信就讓 agent 處理，失敗重試三次，超過預算就停」

**(A) 今天就能寫：一項 each＋一支 sh**（路 b，最薄）

```json
{"tasks": [{"name": "mail", "mode": "each", "argv": ["sh", "mail.sh"]}]}
```
```sh
# mail.sh：每回合由 tick 起一次；狀態在 $AOS7_TASK/state.json（換 run 留著）
tokens=$(sed -n 's/.*"tokens": *\([0-9]*\).*/\1/p' usage.json 2>/dev/null); [ "${tokens:-0}" -ge 50000 ] && { aos7-ctl daemon "$AOS7_TASK/mnt/aosd" pause . --owner budget; exit 0; }
letter=$(ls inbox/*.json 2>/dev/null | head -1); [ -z "$letter" ] && exit 0
if python3 agent.py "$letter"; then rm -f "$AOS7_TASK/tries"; else n=$(( $(cat "$AOS7_TASK/tries" 2>/dev/null || echo 0) + 1 )); echo $n > "$AOS7_TASK/tries"; [ $n -ge 3 ] && mv "$letter" inbox/failed/; fi
```
好處：零新東西。代價：重試、預算、停都寫死在 sh 裡；polyglot 探針已示範 sh 讀 JSON 有多彆扭；第二個 node 要同樣的東西就複製一份。

**(B) 拆成任務＋kernel 包**（路 b＋任務包，常駐系統會長成的樣子）

```json
{"tasks": [
  {"name": "watch", "mode": "keep", "argv": ["aos7-watch", "inbox", "--spawn", "handle"]},
  {"name": "budget", "mode": "keep", "argv": ["aos7-account", "--cap", "tokens=50000", "--then", "pause"]},
  {"name": "sup", "mode": "keep", "argv": ["aos7-supervise", "sup.json"]}
]}
```
`sup.json`＝`{"handle": {"max_restarts": 3, "backoff_rounds": [1, 2, 4], "on_exhausted": "escalate"}}`。watch 看到信就 `edit_json` 加一項 `once` `handle`。好處：每件事一支通用程式，跨 node 複用。代價：三個任務彼此靠檔案協定，「這封信現在重試到第幾次」要讀三個地方；supervisor 探針量到 keep 與 supervisor 搶起的競態（spawn 模式才零違規）。

**(C) 步驟表＋直譯器任務**（路 c2，推薦記下的形狀）

```json
{"tasks": [{"name": "mail", "mode": "keep", "argv": ["aos7-step", "mail.steps.json"],
            "mounts": {"aosd": ".aosd"}}]}
```
```json
{"guard": {"file": "usage.json", "field": "tokens", "max": 50000, "goto": "stop"},
 "start": "check",
 "steps": {
   "check":  {"wait": {"glob": "inbox/*.json", "as": "letter"}, "then": "handle"},
   "handle": {"run": {"argv": ["python3", "agent.py", "${letter}"]}, "ok": "done", "fail": "retry"},
   "retry":  {"count": 3, "then": "handle", "exhausted": "park"},
   "park":   {"run": {"argv": ["mv", "${letter}", "inbox/failed/"]}, "then": "check"},
   "done":   {"run": {"argv": ["mv", "${letter}", "inbox/done/"]}, "then": "check"},
   "stop":   {"ctl": {"op": "pause", "node": ".", "owner": "budget"}}
 }}
```
語意：每收到一次 tock 前進最多一步；`wait` 是「每回合看一次檔」；`run` 是加一項 `once`（`slot` 釘 `mail.handle`）然後等 exit.json，0＝ok、其他＝fail；`count` 存在槽的 state.json；`guard` 每回合先看。整個直譯器對核心的要求只有：once、exit.json、edit_json 拿鎖、ctl 檔——**全部現成**。
好處：一份檔講完整件事；LLM 寫的就是它會寫的形狀；`state.json` 的 `pc` 看得出卡哪。代價：又一個格式要維護；每步至少一回合（跟 PLC 一樣，這是特性不是 bug）；條件語言要克制（只准 `glob`／`exists`／exit code／單一數字比較，不加運算式——r3-fable 的 jq 警告）。

**哪個最好**：這個例子今天用 (A)，一支 sh 就夠。真實系統會長成 (B)。(C) 是 (A) 與 (B) 之間缺的那層：**單一工作內的控制流程**，而 (B) 的包管的是**多個常駐任務之間**的。兩者不搶。

## 7. 建議

**現在不做，記下。** 理由：原則 7、9；三個訊號都還沒出現（下面）。

**最小第一步（不寫程式，約 10 行文件）**：
1. 在 proto7-2 spec 或 notes 點名一句：**「tasks.json 一項＝aos 的一條指令，inst 是其中的 exec 欄；tick 讀快照、tock 提交，是兩相時鐘。」** 不改行為，只定方向（跟 r3「點名 tock.json 是唯一內建轉接器」同一招）。
2. 把第 6 節 (C) 的步驟表格式與「條件只准四種」的限制放進 notes 當候選格式，標 `step` 任務包，`class: general`、`layer: kernel`、依賴控制包（once＋kill）與工具包。

**時機到了的訊號**（任一出現就做 `step` 包第一版）：LLM 第三次在真實工單裡把一次性工作寫成 keep／each；第二個 node 手寫同樣的「重試＋停」迴圈；supervise 包定案後發現「單一工作內的重試」塞不進它。

**做的話的第一版**：一支 ≤300 行的 `aos7-step`（keep 任務），只支援 `wait`／`run`／`count`／`ctl`／`guard` 五種步；狀態只在槽的 state.json；探針用 selfprog 的同一份工單（「每個檔只算一次」那題正是三個模型都沒過的），比較 LLM 寫 tasks.json 與寫步驟表的達成率。

**對核心的要求：零。** core-slimming 的 `x` 透傳欄、r2 的 `timing` 都不需要。唯一可能回頭要的是「kill 必帶 run」（控制包已定），直譯器等子任務時要靠 run id 分辨是不是自己起的那一次——現成。

## 8. 給使用者想的問題

1. **aos 的「程式」到底是哪一層？** 你心裡的「C 語言」是寫 kernel 的（那麼答案是 tasks.json＋改表，已經有了），還是給 LLM 寫工作的（那麼答案是步驟表那層，還沒有）？這決定要不要做 `step` 包。
2. **每步至少一回合，接受嗎？** PLC 式語言的代價是沒有回合內順序：「A 做完馬上 B」要等下一個 tick。接受的話 (c2) 很乾淨；不接受就只能把 A→B 塞進同一個任務（任務內層），語言就要有「同回合子步驟」，複雜度翻倍。
3. **條件語言的紅線畫在哪？** 四種條件（檔案存在、glob、exit code、單一數字比較）夠不夠？一旦開放運算式，就是 jq／JSONPath 的路。

## 9. 我最不確定的三件事

1. **步驟表會不會只是 Python 的劣化版。** 任何人都能用 60 行 Python 寫出 (C) 的語意；步驟表的價值全押在「LLM 寫它比寫 Python 可靠、人 `cat` 它比讀 Python 快」。selfprog 的數據支持前半（錯在時間語意），但沒有直接比較過「給步驟表格式」的達成率。
2. **一步一回合在 interval 2000 ms 的 node 上會不會慢到沒人用。** 三步的工作要 6 秒；真實用法可能全部退回 (A)。wake 可以補（直譯器加完 once 就 wake），但那會讓「回合≈時間」變快（r2 的 `min_interval_ms` 題）。
3. **「核心零要求」能守多久。** 直譯器要知道「我起的那個 once 是不是已經跑過」靠 `launch` 標記與 run id，要知道「它失敗了」靠 exit.json——都是取樣。槽被 tock 刪掉（報完一回合）之前直譯器要讀到 exit.json，interval 快的 node 可能漏；漏了就要回頭要「事實出口」或「once 結束保留 N 回合」，那就是核心的事了。
