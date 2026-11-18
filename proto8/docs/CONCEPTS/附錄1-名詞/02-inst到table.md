← [回入口 附錄1-名詞.md](../附錄1-名詞.md)｜附錄 1 名詞｜上一份：[01-aos到agent](01-aos到agent.md)｜下一份：[03-aos-exec到最小實作](03-aos-exec到最小實作.md)

## 1. 名詞（二）：inst、loop、daemon、proc、介面、資料夾程式、入口、table

| 詞 | 使用者的意思 | 出處 |
|---|---|---|
| inst（單子） | 讀一張單子（JSON：`argv`、`cwd`、`envs`、`stdin`／`stdout`／`stderr`、`timeout_ms`…）去做對應的 POSIX 呼叫、跑一次。吃 JSON、固定幾個 key、不認識的略過（但 JSON 裡可以多放九軸、traits、資源標籤、優先順序標籤、工具等有的沒的）；inst 是 C lib、沒有 aos-inst 命令列（`#!/usr/bin/env aos-inst` 這種 shebang 不能用），單子當入口時由 aos-exec 行程內跑、不設 `+x`（[ideas § 20](../../../thinking/2026-10/19/ideas/README.md)） | 3f.1、3g.2、3g.13b |
| loop（`aos-loop`） | 讓一個程式一次一次執行：`loop.json` 寫 `{"exec", "max"}`〔`exec`＝要跑什麼：使用者選「exec，loop／daemon 的 run 也一起改 exec」，[thinking](../../../thinking/2026-10/23/naming.md)〕，每次 `aos-exec` 子資料夾或跑一張單子，子程式退 10 就停 | 3f.2、3g.3 |
| node（節點） | loop 所服務的那個資料夾；時間＋task 結合起來才是好的 node | 3f.2、3f.5 |
| daemon | 統一管理所有 loop：哪個資料夾歸誰管（排他）、監控；Linux 許可權全在它身上；可以吃一點控制；可牽動另一個 daemon；正式只承諾跑資料夾；本體非常短 | 3f.2、3g.3、3g.4 |
| proc | 會跑、會交流的東西（行程，跟 Linux 同字同義，C-75）；daemon 底下的子項不論包成 loop 一直跑、還是 aos-exec 跑一次都是 proc，名單叫 `procs`（使用者 11-03「exec是基石，loop是另一種基本形式，搞不好以後還會有更多形式。」）；動作與狀態見[名詞表](../../../thinking/2026-11/03/procs/03-規劃-fable-照原則定的細節-可翻案.md#0-名詞表代定) | C-75、11-03 |
| state_flux（回音窗） | 程式的第三扇公開窗 `state_flux.json`：`ctl.json`＝別人寫給我的指令、`state.json`＝我現在是什麼樣（穩定，只在狀態真的轉換時重寫）、`state_flux.json`＝我聽到了什麼（外面敲一下就回一聲的回音欄：`responded_at`、`ctl_seq`、`ctl_warning`，aos-daemon 再加 `procs_ctl_seq`、`procs_ctl_warning`、`mailbox_warning`）（使用者 11-09「state可以拆成不太變動的，和容易變動的，頻繁變動的從state拉出來」、名字「那就state_flux」）；父判卡住讀它 | N-09「state 與 state_flux」、[clock-and-hot-writes 05](../../../thinking/2026-11/09/clock-and-hot-writes/05-state拆分規劃.md) |
| 介面（interface） | 一組約定，資料夾程式**宣告自己遵守**（像 Go 的 interface；使用者 11-04 晚「程式語言中定義class/struct的後，也會宣稱說自己繼承於/遵守於某些介面，比如golang interface之類。」）：寫在資料夾頂層的 `interfaces.json`，key＝介面名（例 `aos-agent`、子介面 `aos-agent/screen`；也可宣告設定檔，例 `"llm": "llm.json"`，P-43（續））；用的一方只認宣告、不猜裡面是什麼（[aos-agent](../../../py/aos/apps/agent/README.md) 的 `add`）。不是 daemon 子項的 loop／exec 型（那是怎麼跑），也不是 eca 的 claude／codex（那是 `cli.json` 的 `kind`） | C-51 的 11-04 註、[thinking 11-04 aos-agent 03](../../../thinking/2026-11/04/aos-agent/03-種類與契約.md) |
| task（aos task） | 一個 inst 裝不下多個任務，所以用 task JSON 裝一包；跑在 daemon 上的 argv 中介程式 | 3f.4 |
| kernel（不譯「核心」，C-74） | 第三層；一個任務包，偏定義與概念，落成協議和格式；參照物是時鐘（時間）與資料夾（空間）；切在 task 與時鐘之上，不碰 loop 的下一個 inst；管什麼見 C-47（資源管理＋排程、從寄件人看；使用者 11-17 選項框「C-47：資源管理＋排程」） | 3f.6、3g.6、3g.7 |
| 標頭檔 | 一個已經設好的資料夾（例如一個 agent：skills、memory、工具放好）；引用它＝用那個資料夾，不複製，跑起來時執行環境在引用者這邊；工具對 agent 而言也是標頭檔 | 3g.10、3g.12 |
| binding（繫結） | library／程式語言做的事：把 agent 那條很長的 list 裡固定的元素綁死，用時只填幾個引數（「list」用 table 比喻，C-71） | 3g.9 |
| 工具 | agent 函式的引數之一；對 agent 來說就是被引用的標頭檔，內部怎麼跑不用懂；agent 也可以是工具；aos 體系的每個指令都是工具 | 3g.12、3g.13 |
| 資料夾程式（定義） | 一個資料夾＝一個程式；入口是 `$AOS_ENTRY`（預設 `_entry`）指的檔（四種，見「入口」）；agent、工具、loop 一次裡的格都是。呼叫時不變（C-46、C-68）。就是上面說的「標頭檔」 | 10-19 |
| 入口（`AOS_ENTRY`） | 資料夾程式裡被執行的那個檔，在資料夾裡的相對位置，預設 `_entry`（只佔一層，跟 JSON 的 `js["_entry"]` 對上，C-72）；像 lua table 的 metatable 裡定的那個（C-68、C-71）。入口之外的東西就是其他元素。**定義（C-73）**：要麼自己是可執行檔（含 shebang 檔），要麼是 aos-exec 完整實作跑得動的檔——inst 單子、JSON 陣列（當 argv）、或 JSON 裡 `js[$AOS_ENTRY]` 的值（單子、陣列、字串路徑；沒 `argv` 的物件＝當資料夾、一路往下再取）；找法 N-61 | 10-19 |
| `AOS_CO` | current obj（使用者「aos current obj」）：實際入口在那份 JSON 檔裡的位置，JSON 指標、不帶 `#`（例 `/dev/sub`）；整份檔或不是 JSON＝空字串；aos-exec 每層覆寫（N-57） | 10-21 晚 |
| `AOS_CF`、`AOS_CD` | current file、current dir：aos-exec 每層覆寫的兩個環境變數——實際被執行的那個檔的絕對路徑（不帶 `#/…`）、它所在的資料夾（＝cd 進去的地方）。程式 cd 走之後靠它們找回自己的東西（`aos-exec "$AOS_CD/tools/stamp"`）（C-69、N-57；[ideas § 19](../../../thinking/2026-10/19/ideas/README.md)） | 10-19 下班前 |
| `檔#/指標`（JSON 尋址） | aos-exec 的入口路徑可以指進 JSON 裡：`cfg.json#/tools/stamp`＝cfg.json 裡 `/tools/stamp` 那個值（JSON pointer）；第一個 `#` 就切，檔名不能含 `#`（N-62；使用者「#/。」「尋址一定值得。」） | 10-19 下班前 |
| table（比喻） | 資料夾比喻成 lua 的 table：靠名字找元素、裡面還能放 table；跟 lisp 的 list 本質一樣是「用 index＋巢狀方式分資料，只是 index 格式不同」，比喻一律用 table（C-71）。舊條文與舊討論裡的「list」都是它 | 10-19 |
