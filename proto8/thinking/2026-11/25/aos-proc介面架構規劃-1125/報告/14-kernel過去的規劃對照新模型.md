把 10 月到 11-24 關於 kernel 的規劃與定案逐項放進 11-25 的新模型：沒有一條 kernel 的定案被推翻，要改寫的集中在三處（寄件人是誰、AOS_KERNEL 指什麼、kernel 不是常駐行程），token「兩邊各記」今天已經如此且實測逐筆對得上，另列五題給使用者裁。

# 14 kernel 過去的規劃對照新模型（11-25）

← [架構規劃入口](../README.md)

第 14 隻子 agent 寫。只讀，沒改任何既有的檔；實驗只在 `~/.aos/scratch/aos-proc-arch-1125/14/`。

- **使用者說的**：寫成 使用者 11-11：「…」 這個樣子，引號裡逐字。其他地方的「」只是把一個詞框起來，不是引他的話。
- **查到的**：附 `檔名:行號` 或指令。路徑從 repo 根算；`thinking/…` 開頭的在 `proto8/thinking/` 底下。活樹＝`~/aos-home/.stack`（公司這台）。
- **我的推論**：標「推論」，還沒有使用者的話。
- **新模型**＝[9P proc 第一輪談話](../../9p-proc-1125.md)「定了的」那一節。對 kernel 的原話是使用者 11-25：「daemon會是介於linux和aos之間的橋樑，而kernel就是底下的一個具備相關功能的aos proc」「而kernel就只是普通的aos proc」。

## 1. 結論

1. **新模型對 kernel 說的兩句話，以前都說過。** daemon 是 Linux 與 aos 之間的橋，11-05 就是這樣講的（原話在 A3）；kernel 是 daemon 底下一個帶功能的 proc，是 11-05 講的第二種擺法，也是他 11-12 回想更早版本時的說法（A5）。C-47（kernel 是從寄件人看過去的身分）講的是另一件事，兩邊疊得起來。
2. **總表 43 項**：原樣成立 23、說得更清楚 7、要改寫 5、被新模型取代（變簡單）5、對不上 2、本來就還開著 1。沒有一條關於 kernel 的使用者定案被推翻；對不上的兩處一個是當時的代定、一個要看怎麼讀（題 2、題 5）。
3. **要改寫的集中在三處。** ①「寄件人是誰」今天＝寄件人 stack 的絕對路徑；stack 改義、入口帶 PID 之後要換成名字那條路（實測：根一重起，同一隻就變成另一個字串）。② `AOS_KERNEL` 指的是一個信箱，不是 proc 的目錄。③ 今天的 kernel 不是常駐行程，是每 300 毫秒起一次、做一輪就退出的程式；「活著走 socket」要有人常駐著接。
4. **token「兩邊各記」今天已經是這樣，而且對得上。** 活樹上 llm kernel 的帳 4,923 筆、2.687 億 token；36 隻還在的 agent 自己記的，逐筆同名同數，只差 1 筆。對不上的 71 筆全找得到原因。
5. **用 Claude Code 當身體的 agent（eca）兩邊都沒帳**：不經過 llm kernel（帳裡 0 筆），自己的目錄裡也沒有累計用量。新模型的「自己報」給了方向，但今天沒有這個檔。
6. **四樣以前規劃的東西被新模型變簡單**：11-20 的「寄信問 kernel」協議、11-21 的「對外另外一份 json」、同步等待用的鎖檔、回信信箱。多半變成「讀 kernel 目錄裡的一個檔」或「一條連線」。
7. **權限站（`$AOS_KERNEL`）也是普通 aos proc**，今天三種擺法背後都已經是一個 proc。問「某個proc的信箱在哪」是今天問「表在哪」那封信的延伸：daemon 是知道事實的，kernel 是站在它前面、可以有主見的。
8. 要他裁的五題：請求算訊息還是 ctl 的字、兩個 kernel 變數指什麼、問位置時 kernel 不回怎麼辦、帳放哪與 eca 誰報、symlink。

## 2. 查到的事實

### 2.1 今天的 kernel（活樹，11-25 中午讀的）

| 項 | 事實 | 怎麼查的 |
|---|---|---|
| 有幾台 | 一台 llm kernel；權限站沒開 | `~/aos-home/.stack/procs_state.json` 的 `llm` 列；整棵活樹找不到站才有的 `hold.json`、`forwarded.json`；各定義夾的 `.env` 沒有 `AOS_KERNEL` |
| 它是什麼行程 | 一支常駐的 `aos-daemon`（pid 2227），每 300 毫秒起一支 Python（`kernel_llm`）做一輪就退出 | `~/aos-home/llm/daemon.json`；`proto8/knowledge/aos/cli/parts/llm_kernel.md:3` |
| 它站在哪 | 定義夾 `~/aos-home/llm`，不是自己的 stack | `readlink /proc/2227/cwd` |
| 它的 stack | `~/aos-home/.stack/procs/llm`：根 daemon 表上的一列，自己又是一台 daemon；列上寫了掛掉自動重起 | 那張表：`"stack": "procs/llm", "def": "../llm", "auto_restart": true` |
| 別人怎麼找它 | 根的 `.env` 寫 `AOS_LLM_KERNEL=${AOS_STACK}/procs/llm`，整棵樹繼承 | `~/aos-home/root/.env` |
| 有沒有 socket | 沒有 | `find ~/aos-home/.stack -maxdepth 4 -type s` 沒結果 |
| 設定 | 總格 8、保留給 high 的 1 格、13 個端點包 | `~/aos-home/llm/kernel.json` |
| 記了什麼 | 逐封帳 `ledger.jsonl` 4,923 行（2.6 MB）；這一窗的合計 `used.json`（今天 1,898 次、1.08 億 token，分包、分寄件人） | `~/aos-home/.stack/procs/llm/` |

### 2.2 總表：過去的規劃與定案，放進新模型之後

「放進新模型」那欄只有六種寫法：原樣成立／說得更清楚了／要改寫／被新模型取代／對不上／還開著。

**A. kernel 是什麼**

| # | 過去的規劃／定案 | 原本怎麼想（出處、原話） | 程式做到哪 | 放進新模型 | 為什麼 |
|---|---|---|---|---|---|
| A1 | kernel＝資源管理＋排程，是從寄件人看過去的身分 | C-47（`proto8/docs/CONCEPTS/04-kernel/01-C-47.md:5`）。使用者 11-11：「kernel這個身分是從外面看進去的」「他沒必要有自己是kernel的自覺」 | 知識庫照這句寫（`proto8/knowledge/aos/kernel.md:5-7`） | 原樣成立 | 新模型講 kernel「是什麼東西」（一個擺出 ctl、status 的 aos proc），C-47 講「對誰算 kernel」，兩句疊得起來 |
| A2 | 排序與資源分配本身是計算任務，核心沒有第二種東西 | C-12（`proto8/docs/CONCEPTS/04-kernel.md:8`，最早那批條文） | — | 原樣成立 | 「而kernel就只是普通的aos proc」就是這條落成介面 |
| A3 | daemon 是 Linux 與 aos 之間的橋 | 使用者 11-05 晚：「所有牽涉到linux原生行程的機制，都以daemon爲界面，而daemon所擔任的，就是橋梁，並且盡量將各類東西暴露爲檔案」（`thinking/2026-11/05/no-pid/README.md:15`；C-03、C-04；名詞表 `proto8/docs/CONCEPTS/附錄1-名詞/01-aos到agent.md:20`） | 只有 daemon 碰 pid，別人讀它寫的檔、寄信給它 | 原樣成立 | 11-25 是同一句，多的是 daemon 自己也算 aos proc、目錄裡多一個 procs 夾。11-05 同一批定的「只有 daemon 碰 pid」，跟 11-25 的「我們就是給根daemon的PID，然後讓大家自己去訪問/proc/<PID>」怎麼並存，見報告 16 |
| A4 | daemon 是最基礎的 kernel（來者不拒）；沒設 `AOS_KERNEL` 就寄給 daemon | 使用者 11-05：「其實daemon也算是一種kernel，只是他就是來者不拒，可以說是一種最基礎的kernel實作」（`thinking/2026-11/05/kernel-daemon/README.md:9`）；11-11：「AOS_KERNEL沒設的話就走AOS_DAEMON」 | `aos-agent ctl` 沒設就直寄 daemon 的 `procs_requests` 信箱 | 原樣成立 | daemon 也是 aos proc，對直接找它的人就是 kernel。「加一列、拿掉一列」以後怎麼寫，使用者列在還沒談到（題 1） |
| A5 | 兩種擺法：daemon 的身體就是 kernel；或 daemon 底下一個專門收請求的 proc | 使用者 11-05：「第二種是kernel作為一個唯一有權限對daemon下daemon-ctl指令的proc，其他人要掛proc，就是要改將請求丟給這個kernel proc，這就比較類似linux，有一個0號proc」；11-12：「我就是說有一個daemon，掌管aos proc的生死，而kernel則是他底下的一個特殊proc，是唯一具有權限能下daemon ctl的proc。」「其他daemon，其實本身就既是kernel也是daemon」（`thinking/2026-11/12/kernel-as-bridge/06-細聊-手與門.md:13`）；意見稿 11-06（`wf/user/advice/` 的 `20261106.md`）：「標準實作上我們提供的kernel通常都是一號行程，占有對於某個daemon的唯一控制權」 | 範本 `daemon-kernel`、`procs-kernel`；llm kernel 是第一種，再掛成根的一列 | 說得更清楚了 | 11-25 的講法就是第二種。第一種＝那個 proc 自己剛好也是 daemon（目錄裡多一個 procs 夾）。兩種都還在 |
| A6 | kernel 是概念，而且是主觀的；daemon 也是概念 | 使用者 11-12：「所以kernel仍會作爲一個概念存在，只要是符合這個概念的proc(或可發送請求的目標)，對於需要他的proc來說(在他心中)，那就是kernel，這是主觀的。」（同上 `:15`） | — | 原樣成立 | 括號裡的「或可發送請求的目標」比 11-25 的「aos proc」寬一點，見邊緣 14 |
| A7 | 先做兩種 kernel，都基於 daemon；kernel 是 daemon 或 loop 一次次叫的一輪 | N-42 草稿（`proto8/docs/NORMS/09-kernel.md:5`、`09-kernel/01-N-42-1-LLM-kernel.md:5`） | `proto8/py/tools/aos/kernel/round.py:69`：做一輪就退出；常駐的是 aos-daemon 或 aos-loop | 要改寫（實作與措辭） | 「活著走 unix socket」要有常駐的行程接，站本身不常駐（邊緣 1） |
| A8 | 問腦包成 aos 函數，掛成 llm kernel 那台 daemon 的一列 proc | 使用者 11-05：「問腦，他本身也可以包裝成一個aos函數，掛成proc去跑。我也建議這樣。」「能包盡量包啦」 | 每次問腦是一列 `llm_<信名>`，它的 stack 就是那封信的資料夾（`09-kernel/01-N-42-1-LLM-kernel.md:8`） | 原樣成立 | kernel 掛出去的工作列在它自己的 procs 底下，正合 11-25 說的「它會有一個procs資料夾，底下就是各aos proc」。成品放哪要注意（邊緣 4） |
| A9 | agent 也能當 kernel | 使用者 11-13：「一個普通的agent隨便弄些hook、json設定啥的，就可以收請求了。請求進來後agent收到通知，他自己判斷要不要過，然後再去轉送」（`thinking/2026-11/13/eca-as-kernel.md:10`） | 工具 `kernel_gate`；站的收件箱在那隻 agent 的 stack 裡（`proto8/knowledge/aos/kernel.md:64`） | 原樣成立 | 這就是「具備相關功能的aos proc」的現成例子。它的收件箱要算要留的（agent 睡著時信得留著） |
| A10 | 轉交也算 kernel，鏈自然形成；站與站之間一律走 aos-post，共通的只有信封，請求放 body、各類自理 | 使用者 11-11：「而chain這東西就是自然而然形成的，chain上的kernel可以沒有這個概念，他們就是只知道這份請求的src/dst，然後自己做一些處理而已」「然後"請求"格式，他是被包在aos-post格式的body內的。在請求格式之內，就不用多做限制。」（`01-C-47.md:8`） | `kernel.json` 的 `next`、轉交函數 `llm_forward`、整條鏈的劇本測試 | 要改寫（先答題 1） | 新模型有兩條路（socket、寄信）加純文字的 ctl。鏈靠「原樣轉寄同一份請求」成立，要先定請求算訊息還是 ctl 的字 |
| A11 | 一切都可以嵌套；kernel 嵌套堆疊 | 使用者 11-07：「一切都可以嵌套」；11-24：「允許自行設計kernel，從資源到排程，並且允許kernel嵌套堆疊」 | 範本 `llm-team`、`test_nesting` | 原樣成立 | 每一層是一個 aos proc；`procs/<名>/procs/<名>` 本來就是巢狀的形狀 |
| A12 | 初始 kernel＝最小核心＋llm 件＋權限件＋一串可選件 | 使用者 11-20：「兩件+最小核心。然後弄一串可選的，比如需要額外依賴的權限那塊，還有一堆比較麻煩的東西。」選項框「掛同一塊板子」（`thinking/2026-11/20/aos-init-kernel-1120/06-使用者已答.md`） | 起手範本 start-api：llm 掛成根的一列，權限站 `perm/` 附著不掛（`proto8/templates/kernels/README.md:19-32`） | 說得更清楚了 | llm 件、權限件各是 procs 底下一個 proc，可選件就是多掛幾列。最小核心裡的「信箱」要多一條 socket |

**B. 怎麼被找到**

| # | 過去的規劃／定案 | 原本怎麼想（出處、原話） | 程式做到哪 | 放進新模型 | 為什麼 |
|---|---|---|---|---|---|
| B1 | 全樹共用的東西用環境變數指：值是一個資料夾，沒設就報錯不猜，子行程繼承 | N-63（10-28；`proto8/docs/NORMS/10-基礎設施-定義與工作區/07-hub-型環境變數與父子交代/01-N-63-三件事與跟實作對不上的.md:5`） | `AOS_STACK`、`AOS_DAEMON`、`AOS_LLM_KERNEL`、`AOS_KERNEL`、`AOS_CLOCK` | 原樣成立 | 值改寫成從 `AOS_ROOT` 起算的名字（使用者 11-25 選的具名錨點）。細節見報告 06 |
| B2 | `AOS_LLM_KERNEL`＝llm kernel 的 stack；由人設，daemon 不代設 | 使用者 11-05：「用人設吧，你得自己指定。AOS_KERNEL這個命名我感覺他是通用於所有proc的，像是llm請求這塊，感覺要用AOS_LLM_KERNEL，代表llm這個子領域下的，管理呼叫的kernel。」（同檔 `:12`） | `proto8/cpp/aos-llm/src/send/send.cpp:21` | 要改寫（一個詞） | 「stack」改義後要寫成「kernel 這個 proc 的目錄」。活樹的值今天就是 `<根>/procs/llm` 這個形狀 |
| B3 | `AOS_KERNEL`＝一個信箱資料夾；一般 proc 一律寄它，背後是黑盒子；跟 `AOS_LLM_KERNEL` 維持兩個變數 | 使用者 11-11：「我的想法是一律寄到AOS_KERNEL」「寄送出去之後，我們就不管這封信會去哪了，他背後就應該是黑盒子了。」；11-13：「我會覺得AOS_KERNEL他就是在有需要掛一個aos proc的時候，就使用的一個目標，一個通用的，基礎的目標。」「值是信箱」是當時的代定（同檔 `:13`） | 值指到站的 `…/requests`（`kernel.md:52-53`）；活樹沒設 | 對不上（小）→ 題 2 | 新模型裡找人找的是 proc 的目錄（裡面才有 socket、status）。一個變數指目錄、一個指信箱，不是同一種東西 |
| B4 | 狀態在哪用寄信問；aos 不硬性依賴 symlink | 使用者 11-11：「然後kernel給狀態位址...希望不是使用symlink，我不希望aos體系硬性依賴symlink，或許可以折衷？寄信問，取得狀態位址這樣。」（`thinking/2026-11/11/kernel/01-原話與經過.md:59`） | 問句信 `{"procs_state_path": true}`（`proto8/py/aos/daemon_ctl/state_path.py:57`） | 對不上（看怎麼讀）→ 題 5 | 11-25 的 `procs/<名>` 在硬碟、tmpfs 的做法是連到 `/proc/<PID>/cwd` 的 symlink；他同一天也說「如果是fuse的話，那說不定AOS_ROOT就是/proc/12321/procs，並且也不需要symlink」 |
| B5 | `aos-llm ls` 沒設變數時，從 daemon 表上找唯一像 llm kernel 的那一列 | `proto8/knowledge/aos/cli/parts/llm.md:3,16`（看那列的 stack 裡有沒有 `endpoints.json` 與 `requests/`；11-14 做的，commit `efa8227c8`） | 有 | 被新模型取代 | 列出 `$AOS_ROOT/procs`、看各自的 `_metainfo` 就認得出誰是 llm kernel，不用猜檔名（推論） |
| B6 | kernel 的介面分對外與對內，對外的要另外準備一份給別人拿 | 使用者 11-21：「kernel那塊，界面有分對外與對內，interfaces.json中當然兩者都可以有，只是說未來，對外的界面宣告的json，需要另外準備一份，用於讓他人存取」（`thinking/2026-11/21/kernel-宣告進interfaces-1121/README.md:12`） | 只有 `endpoints.json` 這個窗算是；寄件人手上沒有定義夾的路徑 | 說得更清楚了 | proc 的目錄就是那份「對外」：`_metainfo`（我是什麼）、`settings`（東西放哪）、`status`（現在怎樣） |
| B7 | 「寄信問 kernel」的基礎協議：問它吃什麼形狀的資源宣告，框架自動回 | 使用者 11-20：「可以先做寄信問kernel，然後我們的kernel框架也可以弄一個自動回這種信的東西。算是基礎協議吧。」同天下午：「像這種"問某種特定的東西，然後不需要思考或做其他處理(當然，硬要的話也可以，就是用hook)，就是直接回覆特定的東西"的模式很好用。」「我最擔心的就是他每次的回覆都要吃到loop的body的運作時間，會讓整個變慢。」（`thinking/2026-11/20/aos-kask-proto-1120/07-使用者已答.md`） | 沒進 repo（`rg kask proto8/py proto8/cpp` 沒結果）；十四題已答 | 被新模型取代 | 「問固定的東西」＝讀 kernel 目錄裡的一個檔，不佔它那一輪的時間，正好解他擔心的那點。已答的幾題（定義夾一份、stack 有就蓋；沒放就是不給；不過 hook、不記帳）可以原樣當成「那個檔怎麼來」（推論） |

**C. 怎麼跟它說話**

| # | 過去的規劃／定案 | 原本怎麼想（出處、原話） | 程式做到哪 | 放進新模型 | 為什麼 |
|---|---|---|---|---|---|
| C1 | 問腦＝把請求丟給 llm kernel、收回信 | 使用者 10-24：「LLM kernel，也就是把brain這塊弄成一個請求，而不是直接打API，請求會被丟到某個地方，由kernel排隊跑」；11-04：「llm呼叫這塊，我希望是把請求丟到 llm kernel(一個loop)，處理好後收回信」 | agent-fsm 的 wait 格：`aos-llm send` 寄一次，之後每拍 `recv` 看一次 | 要改寫（多一條路） | 活著時一來一回可以在同一條連線上；請求的 body 不用變 |
| C2 | 站著等的人在信裡放一個鎖檔，kernel 試鎖得到＝人走了 | `proto8/py/tools/aos/kernel_llm/docs/01-用法.md:47`（10-24 沙箱那輪定的） | 有 | 被新模型取代（只在 socket 那條路） | 連線斷了就是人走了。寄信那條路照舊 |
| C3 | 回信要另開信箱（`$AOS_STACK/daemon_reply/`、`<kernel>/requests/reply/`、`$AOS_KERNEL/reply/`） | `kernel.md:37`、N-63 | 有 | 被新模型取代（只在 socket 那條路） | 有來有回的連線不需要另開回信的地方 |
| C4 | kernel 不在時，agent 只等、不失敗 | `proto8/knowledge/aos/cli/parts/llm_kernel.md:11` | 信留在 `requests/new/` | 原樣成立，多一步 | 掛了就先問 daemon 信箱在哪，再改寄信。今天 kernel 的位址與收件箱是同一個一直都在的夾，沒有這一步 |
| C5 | kernel 忙或慢，問的人 3 秒後失敗，不改去讀 daemon | 框架圖紙的代定 K-F30、K-F31（`thinking/2026-11/12/kernel-framework/README.md:112-113`）；使用者 11-19 對這個已知限制選「維持現狀，只寫明」 | `state_path.py`；`kernel.md:42-44` | 原樣成立（題 3 會動到） | 「問信箱在哪」若照同一條規矩，kernel 忙時寄給掛著的 proc 的信要晚點再試 |
| C6 | 寄信不回＝呼叫失敗 | 使用者 11-05 晚：「寄信不回，等同於呼叫失敗」 | 有 | 原樣成立 | socket 連不上當場就知道（9p-proc-1125 的實測表） |

**D. 管什麼**

| # | 過去的規劃／定案 | 原本怎麼想（出處、原話） | 程式做到哪 | 放進新模型 | 為什麼 |
|---|---|---|---|---|---|
| D1 | 有限的就是資源，用格數表示；排序＝哪個任務先給哪個資源 | C-09～C-11 | llm kernel 的總格、保留格、包格、後端格與排序 | 原樣成立 | 格數、在飛、排隊變成 kernel 目錄裡看得到的幾行（3.1） |
| D2 | 資源可以是任意東西；請求自己帶一塊 json 宣稱，kernel 對外放話它看什麼 | 使用者 11-13：「他並非基於硬體，而是基於任意資源」；11-20：「給位置和格式。當然，這都是可選的，kernel自己可以選擇不給。」 | 沒進 repo（原型在 repo 外） | 說得更清楚了 | 「位置」有著落了：kernel 目錄裡的一個檔，跟 B7 是同一個（推論） |
| D3 | kernel 替每個 proc 多記一些東西並依此分配；記什麼、怎麼分配都要能自訂 | 使用者 11-19：「排程這塊我們已經有了，但是aos kernel這邊，對於各proc所記錄的東西或許應該多一些，除此之外，kernel自己本身也握有資源分配權」「並且記什麼、怎麼分配，都必須是完全可以自訂的，也就是大家都可以自訂kernel」 | 兩支 hook 的實測，沒進 repo；他答「先不定，讓它自然長」 | 說得更清楚了 | 11-25 定了誰記：proc 的自己報，kernel 記它發出去的。kernel 要看沒經過它的消耗，就去讀那個 proc 目錄裡的檔 |
| D4 | `_metainfo` 要當 kernel 的判斷標準 | 使用者 11-24：「_metainfo我確實打算拿他當kernel的判斷標準，並且有所謂客觀主觀的後續發展。」 | 沒有任何 kernel 讀它（`thinking/2026-11/24/aos的目標-1124/README.md:25`） | 說得更清楚了 | 每個 proc 的目錄裡固定有一份 `_metainfo`，kernel 有固定的地方讀 |
| D5 | cpu、記憶體、行程數的份額在 daemon，kernel 只在轉信時補值或夾值 | 使用者 11-05：「會想要限制特定aos proc所占用的資源。以及daemon/kernel自己本身被限制占用資源，並且會分配份額給proc」 | daemon 做了（rlimit、可選 cgroup）；kernel 站的 `limits`、`users` 表 | 原樣成立 | daemon 是橋，Linux 的事在它。這類數字誰報見邊緣 9 |
| D6 | 跨 agent 的資源鎖往 kernel 想 | 使用者 11-24：「跨agent的資源鎖這塊，可以往kernel那邊想想。」發想推薦「代跑式」，五題等他（`thinking/2026-11/24/跨agent資源鎖-kernel-1124/README.md`） | 零件都在、沒接 | 原樣成立；兩題要重寫 | 代跑的工作＝kernel 底下的 proc，更順。第 3 題（怎麼等）多一種「連線掛著等」，第 4 題（位址怎麼傳）變成 `$AOS_ROOT/procs/<名>` |
| D7 | kernel 要不要拿一個非 LLM 的資源實測一次 | 進度 `aos-goals-1124` 第 ③ 題 | — | 還開著 | 推論：新模型下這個實測可以順便驗「第二種 kernel 也擺得出同一組檔」 |

**E. 怎麼記帳**

| # | 過去的規劃／定案 | 原本怎麼想（出處、原話） | 程式做到哪 | 放進新模型 | 為什麼 |
|---|---|---|---|---|---|
| E1 | 用量從回信的 `usage` 記在 kernel 自己那裡；逐封帳留著，請求原文不留 | 使用者 10-15：「根據token消耗量是否見底來看看說要不要擋」；11-07 裁「留，明寫是翻案（推薦）」；11-04：「舊信根本不用留，就是刪」 | `ledger.jsonl`、`used.json`（`proto8/py/tools/aos/kernel_llm/ledger.py:9`、`budget.py:276`） | 原樣成立 | 這就是「kernel 發出去多少記在 kernel 自己的目錄」 |
| E2 | 每一層的帳是那一層自己看到的；同一筆錢每層各出現一次，加總只加一層；agent 自己那份也是一面鏡子 | 11-07 嵌套設計的概念 3（`thinking/2026-11/07/kernel-nest/README.md`；使用者同天裁了方向題） | agent-fsm 每次問腦在自己的 `observed.jsonl` 記一行（`proto8/py/aos/apps/agent_fsm/wait.py:544`） | 原樣成立 | 就是 proc 自己報、kernel 記自己的。實測逐筆對得上（2.4） |
| E3 | 每個寄件人一份額度；寄件人＝信封上的 `sender`＝寄件人的 stack 路徑，自報不驗 | 10-15 定「濫用：先信任」（他答「隨意」，照建議）；11-19 選項框「照舊自報，風險自擔」 | `budget.py:27` 把它換成相對 kernel stack 的路徑當 key；逐封帳記絕對路徑原樣 | 要改寫 | stack 改義、入口帶 PID 後，絕對路徑不再穩（2.5）。「我是誰」要改用名字那條路 |
| E4 | eca 的花費不經過 llm kernel；要不要報給某台 kernel 沒答 | `thinking/2026-11/19/aos-htop-1119/README.md:16,58`；11-14 部門配額樹的「Claude 電表」他答「都按照推薦」、沒施工 | 兩邊都沒有（2.4） | 被新模型取代（方向） | 不用報給 kernel，自己報在自己的目錄。但今天沒有這個檔（題 4） |
| E5 | 部門配額樹（照寄件人分部門記帳） | 使用者 11-14：「同樣用公司部門這塊來切入，llm呼叫是一種資源，每個部門有其優先級，也會有需求和額度分配」；八題全照推薦 | 沒施工（`thinking/2026-11/22/公司體制-1122/01-現況.md:27`） | 原樣成立 | 記帳樹照寄件人的路徑分，跟 E3 一起改字 |
| E6 | daemon 不管帳 | 使用者 11-25 | daemon 的表沒有用量欄 | 原樣成立 | 今天就是這樣 |

**F. 權限站與查詢**

| # | 過去的規劃／定案 | 原本怎麼想（出處、原話） | 程式做到哪 | 放進新模型 | 為什麼 |
|---|---|---|---|---|---|
| F1 | 權限件＝一台站，寄件人把 `AOS_KERNEL` 指過去；可選、預設不開；是給守規矩的人的規矩，不是牆 | 使用者 11-20 選「加一份選裝、預設不開」「明寫」 | 範本有，活樹沒開 | 原樣成立 | 它是一個普通 aos proc（3.4）。牆的事見報告 15 |
| F2 | 一般 proc 讀狀態＝kernel 給一個狀態位址 | 使用者 11-11 選項框「kernel 給一個狀態位址」 | `aos-agent ctl who`、`ls` 先問再讀；最後由 daemon 答（`proto8/cpp/aos-daemon/src/daemon/mailbox.cpp:187`） | 說得更清楚了 | 11-25 的「去問他的daemon或特定kernel，某個proc的信箱在哪」是同一種問法多問一樣東西 |
| F3 | 寄信給 kernel，kernel 回你要的東西的位置 | 使用者 11-21：「一個很值得走的道路是"寄一封信給kernel，kernel返回他想要存取的daemon的東西的位置"，這可能是kernel幫他取來，放在他能存取的地方，也可能是kernel暫時讓他具有權限，或是兩者皆有」（`thinking/2026-11/21/kernel-攔截daemon存取-1121/README.md:46`） | 實測過讓站把表換成一份抄本 | 原樣成立 | 「問信箱在哪」是這條路第一個正式的用途 |
| F4 | 只防走規矩的存取 | 使用者 11-21：「我覺得原則是只防走規矩的存取，不守規矩的就是要自己承擔風險。真的要硬防，那就要多依賴linux的權限體系」 | — | 原樣成立 | 見報告 15 |
| F5 | `aos-daemon-ctl` 永遠直寄；「只能經過 kernel」只約束 proc | 使用者 11-11 選項框「維持直寄，它就是『指名 daemon』的工具」；11-13「kb-ctl:A*」 | 有 | 原樣成立 | 新模型下「直寄」＝直接對那台 daemon 下 ctl |

### 2.3 進度檔六條各自如何

| 進度條 | 今天卡在哪 | 新模型的影響 |
|---|---|---|
| `aos-init-kernel` | 「一串可選件」有哪些、怎麼裝，待定 | 不擋。可選件有了統一的樣子：多掛一列 proc（推論） |
| `aos-kres` | 等他說：第 5 題「寄信問 kernel」要不要派線、第 8 題那份 json 叫什麼放哪 | 兩題都被新模型接手（B7、D2）。建議先停，名字跟 proc 目錄的字表（報告 18）一起定 |
| `arena-feedback-1124` ③ | 資源鎖五題等他 | 方向不受影響；第 3、4 題的選項照新模型重寫後再問（D6） |
| `eca-main-obs-1124` | core 三件待查（`aos-llm ls` 與窗檔要看得到總格、保留格、在飛、排隊…） | 這幾個數字就是 kernel 的 `status` 該有的行。現在照舊做不衝突，以後搬進 `status` |
| `sol-high-pack` | 配給包寫 `sol-high`，範本改成 `sol` 加思考程度；公司機自己加了一包 | 不受影響。活樹 `kernel.json` 的 13 包裡確實有 `sol-high` |
| `aos-goals-1124` ③ | kernel 要不要拿非 LLM 資源實測一次 | 還開著（D7） |

### 2.4 實測：兩邊的 token 帳對不對得上

做法（只讀）：llm kernel 的 `ledger.jsonl` 每封問腦一行，`id` 是請求信的名字、`sender` 是寄件人的 stack；agent-fsm 每次問腦在自己 stack 的 `observed.jsonl` 記一行，`letter` 是同一封信的名字。用信名對起來比 token 數。

<details><summary>重跑用的程式（純標準庫，只讀；`python3 這支.py ~/aos-home/.stack/procs/llm`）</summary>

```python
import json, os, sys
K = sys.argv[1]                                   # llm kernel 的 stack
def rows(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()] if os.path.exists(p) else []
def tok(u):
    u = u if isinstance(u, dict) else {}
    return u.get("total_tokens") or (u.get("prompt_tokens", 0) + u.get("completion_tokens", 0))
by = {}
for r in {r["id"]: r for r in rows(K + "/ledger.jsonl")}.values():          # 同名只算最後一行
    by.setdefault(r.get("sender"), []).append(r)
for sender, ks in sorted(by.items(), key=lambda kv: -len(kv[1])):            # 每個寄件人一列
    mine = [r for r in rows(os.path.join(sender or "", "observed.jsonl")) if r.get("kind") in ("think", "compact")]
    both = {r["id"] for r in ks} & {r.get("letter") for r in mine}
    print("%5d %5d %5d %12d %12d  %s" % (len(ks), len(mine), len(both), sum(tok(r.get("usage")) for r in ks),
          sum(tok(r.get("usage")) for r in mine), sender if os.path.isdir(sender or "") else "(夾不在) %s" % sender))
```

五欄：kernel 的筆數、它自己記的筆數、兩邊同名的筆數、kernel 的 token、它自己記的 token。

</details>

結果（11-25 12:08 那一次。帳一直在長：12:29 重跑是 4,974 筆對 4,903 筆，差的還是同樣那 71 筆、2,297,885 token）：

| 寄件人是哪種 | 幾個 | kernel 的帳 | 它自己記的 | 對得上嗎 |
|---|---|---|---|---|
| agent-fsm，stack 還在 | 36 | 4,853 筆、266,424,996 token | 4,852 筆、266,407,198 token | 4,852 筆同名、token 數相同；差 1 筆 |
| stack 的夾已經不在 | 3 | 67 筆、2,280,087 token | 沒了 | 只剩 kernel 那邊有 |
| 不是 proc（人在殼裡 `aos-llm ask`） | 2 | 3 筆、0 token | 沒有 | 寄件人是當時所在的資料夾（其中一個是 `/tmp`） |
| 用 Claude Code 當身體的（eca） | — | 0 筆 | 沒有累計用量的檔 | 兩邊都沒有 |
| 合計 | 41 | 4,923 筆、268,705,083 token | 4,852 筆、266,407,198 token | 差 71 筆、2,297,885 token（0.86%） |

- 差的那 1 筆：某棵樹的一隻子 agent 在 09:42:31 被停（結束碼 143），當時停在等腦回話那一格；kernel 09:43:24 才收到那次問腦的結果（跑了 61.6 秒、17,798 token），照記；那隻沒收到，自己沒記。
- 夾不在的 3 隻：11-24 樹搬家以前，stack 在 `~/repo/aos/.stack/procs/` 底下的三隻打雜工。
- eca 那一列的依據：帳裡沒有任何寄件人是 eca 的 stack。活樹 eca-aos 的小格 `claude/` 裡，`live.jsonl` 停在 11-24 13:55（畫面開著時不寫，`proto8/py/aos/agentlib/context_use.py:18`），`turns.jsonl` 每行只有 `answered_at` 與 `text`。

### 2.5 實測：寄件人身分遇到 `/proc/<PID>/cwd`

今天 kernel 認人的做法：信封的 `sender`＝寄件人的 `$AOS_STACK` 轉成絕對路徑（`proto8/cpp/aos-util/src/proc.cpp:109`），逐封帳照原樣記；額度帳把它換成「相對 kernel 的 stack」的路徑（`proto8/py/tools/aos/kernel_llm/budget.py:27`，不解開連結）。把同一段算法搬到一棵「從 `/proc/<PID>/cwd` 進去」的假樹上跑：

| 情形 | 得到的 |
|---|---|
| 寄件人與 kernel 都從 `AOS_ROOT` 那條路寫 | `../mine/procs/main`（跟今天的樣子一樣） |
| 寄件人報真實路徑、kernel 從 `AOS_ROOT` 那條路 | `../../../../../home/…/rootdir/procs/mine/procs/main`（對不起來） |
| 一支從 `AOS_ROOT` 那條路 cd 進去的行程，問自己站在哪 | 真實路徑，不帶 `/proc/<PID>/cwd` |
| 逐封帳記的絕對路徑，根重起前後 | `/proc/2280903/cwd/procs/mine/procs/main` 變成 `/proc/2280971/cwd/procs/mine/procs/main`；舊字串已經走不進去 |

意思：照今天的寫法，根 daemon 一重起，同一隻 proc 在逐封帳裡就變成另一個人；兩邊寫法不一致時，額度帳的 key 會對不起來。

<details><summary>重跑用的程式（純標準庫，只碰自己建的暫存夾，跑完自己收行程）</summary>

```python
import os, subprocess, sys, tempfile, time
here = os.path.dirname(os.path.abspath(__file__))
root = os.path.join(tempfile.mkdtemp(prefix="k14-", dir=here), "rootdir")           # 假的根 daemon 的夾
for p in ("procs/llm", "procs/mine/procs/main"):
    os.makedirs(os.path.join(root, p))
key = lambda sender, stack: os.path.relpath(os.path.abspath(sender), os.path.abspath(stack))   # 同 kernel_llm/budget.py:27
boot = lambda: subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], cwd=root)  # 只是站在那個夾的行程
d1 = boot(); time.sleep(0.2); r1 = "/proc/%d/cwd" % d1.pid                          # 第一次起根：AOS_ROOT
print(key(r1 + "/procs/mine/procs/main", r1 + "/procs/llm"))                        # 兩邊都從 AOS_ROOT 寫
print(key(root + "/procs/mine/procs/main", r1 + "/procs/llm"))                      # 寄件人報真實路徑
os.chdir(r1 + "/procs/mine/procs/main"); print(os.getcwd())                         # 行程問自己站在哪
d1.kill(); d1.wait(); d2 = boot(); time.sleep(0.2); r2 = "/proc/%d/cwd" % d2.pid    # 根重起
print(r1 + "/procs/mine/procs/main", "->", r2 + "/procs/mine/procs/main", os.path.isdir(r1))
d2.kill(); d2.wait()
```

</details>

## 3. 對新介面的含意

### 3.1 kernel 這個 proc 的目錄（以今天的 llm kernel 為例）

使用者定的：每個 aos proc 有 `ctl`、`status`（純文字）、`_metainfo`（json）；談到一個 `settings`（東西放哪）；要留的放 persist。下表拿今天這台 llm kernel 的檔去對。**整張是例子、是推論**，檔名與行名都還沒定（字表見報告 18，三個檔的分工見報告 12）。定義夾＝`~/aos-home/llm/`，stack＝`~/aos-home/.stack/procs/llm/`。

| 新模型裡的東西 | 放什麼 | 今天的對應 | 跟著身體走，還是要留 |
|---|---|---|---|
| `ctl` | 對這台 kernel 下令：停、暫停、恢復 | stack 的 `ctl.json`（這台是 aos-daemon；活樹那夾現在沒有這個檔，沒人下過令） | 身體 |
| `status` | 共通的：狀態、pid、多久一輪、暫停沒。kernel 多的幾行：總格、保留格、在飛幾封、排隊幾封、這一窗用了幾次與幾個 token | `state.json`、`state_flux.json`；`slots.json`；數 `requests/cur/` 與 `requests/new/`；`used.json` 最上面幾個數。`aos-llm ls` 最後一行今天就是這樣湊的：`# kernel: slots N, reserved for high R, in flight F, queued Q` | 身體 |
| `settings` | 我的東西放哪：persist、收件箱、帳、定義夾 | 沒有這個檔。位置靠約定（`<stack>/requests/`）加定義夾 `interfaces.json` 的 `"aos-ledger": {"file": "ledger.jsonl"}` | 身體（內容指到要留的地方） |
| `_metainfo` | 我是什麼：一台 llm kernel、有哪些 hook 點 | 定義夾 `interfaces.json`（`"kernel": {}`、`hooks`、`hookeds`、`aos-ledger`）；程式夾的 `_metainfo.json` | 定義帶來的 |
| socket | 活著時別人連這裡送請求 | 沒有 | 身體 |
| 收件箱 | 掛了、睡了、或這個實作不開 socket 時，請求寄到這裡 | `requests/`（`new/`、`cur/`、`tmp/`、`reply/`）。`cur/<信名>/` 是在飛的那幾件，裡面有 `request.json`、`proc.json`、`reply.json` | 要留（重起後靠它接手，`proto8/py/tools/aos/kernel_llm/docs/02-token-回報與額度.md` 的「訊號」節） |
| 帳（逐封） | 每封問腦一行：誰、哪一包、幾個 token、等多久、跑多久、成功或哪種錯 | `ledger.jsonl` | 要留 |
| 帳（這一窗的合計） | 總數、每包、每個寄件人；額度照它擋 | `used.json` | 要留（壞了能從逐封帳重算） |
| 名額 | 總格、保留格、每個後端幾格 | `slots.json`（每輪照設定重算） | 身體 |
| 排隊 | 誰從什麼時候開始等；各後端現在載著哪一包 | `queue.json` 加 `requests/new/` 裡的信 | 要留 |
| 能挑的端點包 | 代號、快慢、貴不貴、context 多大 | `endpoints.json`（每輪照設定重算，網址這類內部的鍵拿掉） | 身體 |
| 旋鈕 | 格數、額度、每個包怎麼打 | 定義夾 `kernel.json`（每輪重讀，改了不用重起）、`kernel_hookeds.json` | 定義 |
| `procs/` | 它掛出去的工作 | 這台同時是 daemon：`procs/_sweeper`；每次問腦是一列 `llm_<信名>`；另有 `procs_state.json`、`procs_requests/` | 見邊緣 4、5 |

- 掛 proc 的那種站（權限站）多的是：排隊窗 `queue.json`、留著等人點頭的 `hold.json` 與 `decisions/`、轉寄對照 `forwarded.json`、下游回信的 `replies/`（`proto8/py/tools/aos/kernel/README.md:220-227`）。它今天沒有帳：放行過誰、幾次沒有紀錄，要自己寫 hook。
- 推論：今天 kernel 的 `kernel.json` 是旋鈕（改了下一輪生效），使用者說的 `settings` 是「東西放哪」。兩個別叫同一個名字。
- 推論：「現在怎樣」（格、在飛、排隊）放 `status`；累計的帳另開檔。這合他 11-25 說的「好，那目前就只先給status。」與「我在想，能否給出別的？比如token消耗量之類」。

### 3.2 別的 proc 怎麼找到 kernel、怎麼跟它說話

| | 今天（查到的） | 新模型（使用者定的；沒標的是推論） |
|---|---|---|
| 位址寫在哪 | `AOS_LLM_KERNEL`（值＝kernel 的 stack；活樹寫在根的 `.env`，整棵樹繼承）。`AOS_KERNEL`（值＝站的收件箱；活樹沒設） | 使用者給的例子是 `AOS_DAEMON=$AOS_ROOT/procs/repo-aos`；kernel 照同一個樣子就是 `$AOS_ROOT/procs/llm` |
| 位址指到什麼 | 硬碟上一個一直都在的夾 | 使用者：活著的身體；掛了這條路就斷 |
| 送請求 | `aos-llm send` 把一封信放進 `<kernel>/requests/new/` | 使用者：活著走 unix socket；掛了就去問 daemon 或某個 kernel 它的信箱在哪，改寄信 |
| 等回覆 | 回信寄到信封上的回信位址；agent-fsm 每拍（300 毫秒）`aos-llm recv` 看一次；`ask` 站著等 | socket：同一條連線上等。寄信：照舊 |
| kernel 怎麼知道寄件人走了 | 站著等的人鎖著信裡的 `sender.flock`；寄完就走的不判 | socket：連線斷了。寄信：照舊 |
| kernel 多久看一次 | 每 300 毫秒起一支 Python 做一輪 | 沒定（socket 上講什麼還沒談到） |
| kernel 不在時 | 信留在 `requests/new/`，agent 只等不失敗 | 一樣，多一步「問信箱在哪」 |
| 看有哪些端點包、排了幾封 | `aos-llm ls` 讀 kernel stack 裡的 `endpoints.json`、`slots.json`，再數兩個夾 | 讀 kernel 目錄裡的檔（3.1） |
| 往下一層 kernel | 包裡寫下一台的 stack 絕對路徑 | 寫成從 `AOS_ROOT` 起算的名字 |

- 今天的 llm kernel 沒有常駐行程能接 socket。兩種銜接都說得通（推論）：它不開 socket，大家照新模型連不上就改寄信，等於跟今天一樣；或由常駐的那支（aos-daemon、aos-loop）代收、落成一封信，站照舊每輪處理。細節在報告 20。
- 入口照使用者定的走根 daemon 的 PID 時，根 daemon 一掛，`$AOS_ROOT/procs/llm` 整條路就斷，即使 llm kernel 自己還活著。今天不會：位址是硬碟上的夾，根被砍底下照跑（`thinking/2026-11/12/kernel-as-bridge/README.md:45`）。
- 今天投一封信約 10 毫秒（報告 05）。跟問腦的幾秒到幾分鐘比，換成 socket 省的主要是「每 300 毫秒看一次」那段等待，不是投遞本身（推論）。

### 3.3 token 帳兩邊各記

使用者 11-25：「對的，token這塊就是你想的那樣。」（eca-aos 整理成：proc 自己的用量自己報、放在自己的目錄；kernel 發出去多少記在 kernel 自己的目錄；daemon 不管帳。）今天已經是這樣，而且兩邊用同一個信名，逐筆對得起來（2.4）。

**對不上時怎麼看**（推論，依據是 2.4 與 `proto8/py/tools/aos/kernel_llm/docs/02`、`04`）：

- 兩本帳答的是不同的問題。kernel 的帳：「經過我這裡的，我發給誰多少」，額度照它擋。proc 的帳：「我從所有來源一共用了多少」，包含不經過 kernel 的。所以不要求總數相等；能對的只有「這隻經過這台 kernel 的那些信」，用信名一筆一筆對。
- kernel 有、proc 沒有：proc 的夾沒了；在飛時 proc 被停；寄件人不是 proc；有人在信封上寫別人的路徑（kernel 不驗，`docs/04-已知限制.md:17,19`）；工具自己去問腦（寄件人會是工具的小格，不是那隻 agent；推論，活樹的帳裡沒看到）。
- proc 有、kernel 沒有：proc 另有來源（Claude Code、工具直接打 API）；kernel 寫逐封帳失敗只印警告，那行就少了（`docs/02-token-回報與額度.md:28`）；逐封帳不會自己輪替，被人清過。
- 兩邊都有但數字不同：kernel 記的是端點原本回的；回信寄出前的 hook 可以改寄出去的那一份（`proto8/py/tools/aos/kernel_llm/README.md:60`）。
- 端點多算一次錢、兩邊都只記一次：睡醒或被砍之後重掛（`docs/04-已知限制.md:9`）。這種只有端點那邊的帳單看得到。
- kernel 疊了好幾層時，每層各記一次，加總只加一層（`docs/02-token-回報與額度.md:45`）。

**eca 走 Claude Code 不經過 llm kernel**：

- 帳裡 0 筆是正常的，它問的是 Claude Code。過去兩次想補：11-14 的「Claude 電表」（從外面讀 Claude Code 的本機紀錄、按工作區歸戶；使用者答「都按照推薦」，沒施工）；11-19 那條線問過 eca 要不要定期把花費報給某台 kernel（沒有答案）。
- 新模型的答案是第三種：它自己報在自己的目錄。這樣最貴的那一塊才會出現在跟別的 proc 一樣的地方。
- 要注意三件：畫面開著時 aos 這邊沒有任何檔記到用量，數字只在 Claude Code 自己的對話紀錄裡；訂閱制的金額是換算值，不是帳單（`thinking/2026-11/19/aos-htop-1119/02-記什麼-資源清單.md` 第 9 列）；aos 外面用掉的 Claude 額度不屬於任何 proc（11-14 量到主帳號約六成在 aos 外），「自己報」蓋不到，要外面那支電表才看得到。

**proc 死了，它那本帳**：stack 改成「活著的身體」後，自己報的用量如果只放身體，proc 一停就沒了。2.4 那 67 筆就是這種。見題 4。

### 3.4 `$AOS_KERNEL`（權限站）的位置；查詢型的 kernel 跟 daemon 的分工

**它是普通 aos proc 嗎**：是。今天三種擺法背後都已經是一個 proc：`procs-kernel` 是 daemon 表上的一列（aos-loop 每 300 毫秒叫它一輪）；`daemon-kernel` 是一台 daemon 的身體；`kernel_gate` 是某隻 agent 身上的站。新模型要它們多做的只是擺出同一組檔。位址會是某台 daemon 的 `procs/` 底下的一個名字（起手範本今天的寫法是 `AOS_KERNEL=${AOS_DAEMON}/procs/perm/requests`）。

**今天它看得到什麼**：只有兩種信，起停掛拆的請求與「表在哪」的問句（`thinking/2026-11/21/kernel-攔截daemon存取-1121/01-今天kernel攔到什麼.md`）。proc 之間寄信它看不到：`aos-mailbox --to 名字` 直接讀 daemon 的表（同夾 `README.md:9`）。

**新模型多給它一個位置**（推論）：活著時 proc 之間直接連 socket，kernel 不在路上。掛著時寄件人得先問「信箱在哪」，這一問是 kernel 對「proc 之間通訊」唯一站得進去的地方：它可以照實回、回一個它代收的地方、或不回。這正是 F3 那條路。

**分工**（推論；第一列是查到的）：

| 事 | daemon | 查詢型的 kernel |
|---|---|---|
| 知不知道某 proc 的信箱在哪 | 一定知道：它起的，表上每列記著那隻的 stack（今天讀 `procs_state.json` 就行，不需要任何行程活著，報告 05）。新模型下它在 proc 活著時讀過那隻的 `settings` | 不必知道，會問 daemon 就好；也可以自己有一本（跨樹、跨機器時當通訊錄） |
| 回答時能做的 | 照實回；可選：順手叫醒 | 照轉、換一個位置（代收、抄本）、拒絕、先留著等人點頭、記一筆誰問了誰 |
| 誰會來問它 | 沒設 `AOS_KERNEL` 的；指名要它的（今天的 `--daemon`、`aos-daemon-ctl`） | 設了 `AOS_KERNEL` 的 |
| 它不在時 | 那棵樹沒人答得出來 | 寄件人失敗還是改問 daemon，見題 3 |
| 管不管帳 | 不管 | 記自己經手的 |

三種問法，kernel 站不站得進去：

| 問法 | 今天有沒有 | kernel 站得進去嗎 | 代價 |
|---|---|---|---|
| 直接讀 daemon 目錄裡的檔 | 有（表） | 站不進去；FUSE 的話伺服器可以當場決定回什麼 | 最快；daemon 卡住也讀得到 |
| 寄信問 | 有（`procs_state_path`） | 可以 | 要等對方那一輪：daemon 200 毫秒、站 300 毫秒，agent 當的站可能很久 |
| 連 socket 問 | 沒有 | 可以 | 對方要常駐 |

**順手叫醒**：使用者 11-25：「要不要順手叫醒...這是後續的實作細節，我傾向於這是daemon自身的可選設定」。kernel 把問題轉給 daemon 時就照 daemon 的設定；kernel 想更細（只替某些寄件人叫醒）是它自己的政策（推論）。

### 3.5 對著「定了的」逐條

| 定了的 | 對 kernel 的意思 |
|---|---|
| persist 在哪以 proc 自己說的為準 | kernel 的收件箱、帳、排隊、在飛的那幾件都要算要留的。daemon 要趁 kernel 活著讀到它的 `settings`，不然 kernel 一掛，沒人答得出它的收件箱在哪 |
| 支援這套的就是 aos proc | kernel 不必是 aos-loop、aos-daemon 叫起來的站；擺得出這組檔的行程都能當（合 C-47「擺法不限」） |
| 部分用 json | 請求的 body、帳、`_metainfo` 照舊 json；`ctl`、`status` 純文字 |
| `ctl` | 管 kernel 自己（停、暫停）。請求走不走 ctl 是題 1 |
| `status` | kernel 多幾行自己的數字（3.1） |
| token 用量 | 3.3 |
| daemon | llm kernel 今天自己就是一台 daemon：目錄裡多一個 procs 夾 |
| kernel | 總表 A 組 |
| 入口與 `AOS_ROOT` | `$AOS_ROOT/procs/llm`（推論） |
| stack 改義 | 兩處字面要改：`AOS_LLM_KERNEL` 的值（今天寫的是 kernel 的 stack）、寄件人的身分（今天是寄件人的 stack 路徑） |
| 送訊息兩條路 | 3.2 |
| 問信箱時要不要叫醒 | 3.4 最後一段 |

## 4. 邊緣狀況

1. **kernel 不是常駐行程。** 站每 300 毫秒起一次；常駐的是 aos-daemon、aos-loop，或 agent 的身體。socket 由誰聽、站不在的那 299 毫秒誰接，要先定（報告 20）。
2. **kernel 是 agent 時，「活著」不等於「會回」。** `kernel_gate` 的站只在那隻 agent 兩輪之間跑；它在長回合裡時，底下的呼叫 3 秒後失敗（`kernel.md:42-44`，使用者 11-19 選「維持現狀，只寫明」）。新模型下這隻的行程活著，連得上也沒人答。
3. **kernel 自己的請求會繞回自己。** agent 當 kernel 時，自己問腦的信排進自己的隊（`thinking/2026-11/20/aos-kres-1120/README.md` 結論 4）；自己發的起停請求也是（`thinking/2026-11/13/eca-as-kernel.md` 邊緣 13）。新模型不解這題。
4. **跑完才收成品的工作。** llm kernel 把每次問腦掛成一支 proc，成品 `reply.json` 與結束碼留在那支 proc 的 stack，kernel 下一輪來收（`proto8/py/tools/aos/kernel/runner.py:133`）。stack 改成「活著的身體」後，行程一結束那條路就沒了：成品得寫在要留的地方（今天剛好是，那個 stack 就是收件箱裡那封信的資料夾），結束碼只能問 daemon。
5. **短命的工作也是 proc。** 一次問腦一列，活樹到今天 4,923 次。每一列都要擺 `ctl`、`status`、站進自己的夾、建一條連結嗎？
6. **在飛的請求跨過 kernel 重起。** 今天靠 `requests/cur/` 接手。socket 那條路收了還沒落檔就死，那封就沒了；問腦可能已經花了錢。使用者 11-24 對這類說過「持久性/單點故障沒差，我們可以定期保存。」
7. **寄件人身分**（2.5）：帶 PID 的絕對路徑不能當「我是誰」。
8. **proc 一死，它自己報的帳跟著沒了**（2.4）；kernel 的帳若不在 persist 也一樣。兩本帳互為備份的前提是各自放在要留的地方。
9. **cpu、記憶體誰報。** 使用者說 proc 自己報、daemon 不管帳，講的是 token。agent-fsm 每一格是短命行程，量不到自己跨格的 cpu；Linux 那邊的累計在 cgroup，握在 daemon 手上（`proto8/cpp/aos-daemon/docs/09-份額.md`）。這種「只有橋看得到的數字」放誰的目錄，沒人說過。
10. **根一掛，找 kernel 的路全斷**（3.2）。
11. **kernel 掛著時有人要問腦。** 先問 daemon 收件箱在哪。daemon 今天對 `llm` 那列本來就會自動重起；他說的「要不要順手叫醒」那個設定，對 kernel 等於多一個拉它起來的時機。
12. **整棵樹繼承 `AOS_KERNEL` 的老坑還在。** 寫在根的 `.env`，llm kernel 也會繼承，把問腦的工作繞去權限站（`proto8/templates/kernels/README.md:31`，11-20 實跑撞過）。`AOS_ROOT` 可以全樹繼承，`AOS_KERNEL` 不行。
13. **kernel 的目錄誰都讀得到。** 逐封帳有每個寄件人的用量，收件箱裡看得到別人的請求內容（`proto8/py/tools/aos/kernel_llm/docs/04-已知限制.md:18`）。放到 `$AOS_ROOT/procs/llm/` 之後更好找。見報告 15。
14. **寄件人眼中的 kernel 不是 aos proc**（別台機器的服務、只有一個信箱的腳本）：照 C-47 與 A6 那句算 kernel；11-25 的字面沒講。
15. **kernel 疊好幾層時**，下層看到的寄件人是上層那台 kernel（11-07 已裁）。proc 自己報的帳在最底下那隻，kernel 的帳每層一份，「加總只加一層」照舊。
16. **「問信箱在哪」如果跟今天問表一樣只等 3 秒**，kernel 忙的那幾秒寄給掛著的 proc 的信就失敗，寄件人要自己再試。

## 5. 要問使用者的

**題 1：請求（掛 proc、問腦、問位置）算「訊息」，還是 ctl 的字？**
過去定的是站與站之間轉寄同一封信（A10）；今天 daemon 的「加一列、拿掉一列」也是這種信。11-25 定了 ctl 吃純文字，daemon 自己的 ctl 還沒談。

- a. `ctl` 只管這個 proc 自己（停、暫停…），純文字。請求照舊是帶 json body 的訊息，活著走 socket、掛了走寄信，兩條路同一份 body；kernel 的鏈照舊轉寄同一份。
- b. 常用的請求也給純文字的字（例：對 daemon 的 ctl 寫一行「加哪一列」），複雜的才用 json 訊息。
- c. 請求全部改成寫 ctl。

推薦 a。問腦的請求天生是一大包 json，kernel 的鏈也靠「原樣轉寄同一份」成立；b、c 會有兩種寫法要對齊。

**題 2：`AOS_KERNEL`、`AOS_LLM_KERNEL` 以後指什麼？**
今天一個指信箱、一個指 kernel 的 stack（B2、B3）。

- a. 兩個變數都留，值都是「那台 kernel 這個 proc 的目錄」（例 `$AOS_ROOT/procs/llm`、`$AOS_ROOT/procs/perm`），收件箱與 socket 到目錄裡照約定找。
- b. 照舊：一個指目錄、一個指信箱。
- c. 不要變數，kernel 用固定的名字。

推薦 a。活著要連 socket、要看 `status`，都得先拿到目錄；c 跟他 11-05 說的「用人設吧，你得自己指定」相反。

**題 3：問「某個proc的信箱在哪」時，設了 `AOS_KERNEL` 而它不回，怎麼辦？**
他 11-25 的原話是「去問他的daemon或特定kernel」。今天問表的規矩是：設了就只問 kernel，3 秒沒回就失敗，不改去讀 daemon（C5）。

- a. 照今天的規矩：有 `AOS_KERNEL` 就只問它，問不到就失敗；沒設才問 daemon。
- b. 先問 kernel，等不到就改問 daemon。信比較不會卡住，但守規矩的 proc 也等於能繞過 kernel。
- c. 這一問不算要過 kernel 的請求，一律直接問 daemon（或直接讀它目錄裡的檔）。

推薦 a。跟「背後就應該是黑盒子」「只防走規矩的存取」同一條線；代價是 kernel 忙時，寄給掛著的 proc 的信要晚點再試。

**題 4：proc 自己報的用量放哪？eca 的用量誰報？**
實測對不上的 71 筆裡 67 筆是「proc 的夾沒了」；eca 是最貴的一塊，兩邊都沒帳（2.4、3.3）。

- a. 用量算「要留的」，放 persist。eca 由它的身體每回合把 Claude Code 給的用量抄一份到自己的目錄，樣子跟 agent-fsm 那份一樣。兩本帳都只是各自看到的，對不上時用信名逐筆對，不設誰為準。
- b. 用量檔放身體就好（死了就沒了），要查歷史看 kernel 的帳。eca 不報，照 11-14 的「Claude 電表」從外面讀。
- c. 經過 kernel 的以 kernel 的帳為準，proc 只報沒經過 kernel 的那部分。

推薦 a。b 會讓 eca 一停，它花了多少就只剩外面那支電表知道；c 要每個 proc 先分清楚哪些經過了 kernel。

**題 5：symlink 那句怎麼讀？**（報告 16 可能也問，綜合時併成一題）
他 11-11 說過「我不希望aos體系硬性依賴symlink」；11-25 的 `procs/<名>` 在硬碟、tmpfs 的做法是 symlink，FUSE 不用。

- a. 介面只規定「`procs/<名>` 走得進那個 proc 的目錄」，不規定是不是 symlink：硬碟實作可以是真資料夾（今天就是）或連結，FUSE 不用連結；「問位置」那條路留著，當不靠連結的走法。11-11 那句照舊成立。
- b. 收回 11-11 那句：這套就是靠 symlink。
- c. 不用 symlink：硬碟實作維持真資料夾，`/proc/<PID>/cwd` 只當入口那一跳。

推薦 a。兩句話都保得住，也不擋 FUSE。

## 6. 沒查到／沒把握的

- 10 月以前（proto6、proto7）的 kernel 規劃沒翻；他 11-12 自己說「不用去翻」。
- 只看了公司這台的活樹，家機那棵沒看。
- 對帳只比了 token 總數與信名，沒比進、出、快取各欄；真端點回的 `usage` 欄位差異沒驗。
- eca 在 Claude Code 裡面再開的子 agent，用量記在同一份對話紀錄還是別處，沒查。
- 3.3 裡「工具自己去問腦」那一條是照寄件人的算法推的，活樹的帳裡沒看到這種寄件人。
- 寄信問 kernel（11-20）、資源基底（11-20）、Claude 電表（11-14）的原型都在 repo 外的暫存夾，我只讀了紀錄，沒看程式。
- 資源鎖五題他答了沒：進度檔寫「五題等使用者」；信箱不准碰，沒查。
- socket 上講什麼還沒定，所以 3.2 的「活著走 socket」只寫到形狀；`kernel_gate` 在新模型下的行為是推論。
- 沒重跑任何 kernel 的測試。N-42 整條仍標「草稿」。
- 3.1 的身體／要留怎麼分，是照「重起後還要不要」推的，沒有他的話。
