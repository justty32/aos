# 2026-10-16 agent 的「擴張」與「當函數」：Lua 式繼承在 JSON inst 體系怎麼用、不造 args.json／ret.json

← [討論紀錄](README.md)｜前情：[inst-exec 第四版](2026-10-15-inst-exec-v4.md)（本稿改掉它「工具一律走 frame：args.json 進、ret.json 出」那段）、[意見 1～4](2026-10-15-opinions-1-4.md)（agent＝fsm＋inst、binding 用 json＋資料夾）、[topics/04 agent 當函數](2026-10-15-topics/04-agent當函數.md)、[同像性](2026-10-15-homoiconic.md)、[10-14 fsm 原話](2026-10-14-json-entry/06-fsm.md)（「像 C++ class 的繼承、函數可以被覆蓋」）｜概念：[C-46、C-50](../CONCEPTS/05-agent.md)、[C-34、C-36、C-49](../CONCEPTS/03-基礎設施.md)、[C-48、C-52、C-55、C-56](../CONCEPTS/01-設計理念.md)｜規範：[N-12、N-43](../NORMS/01-總則.md)、[N-27](../NORMS/03-基礎設施-inst.md)、[N-28、N-44](../NORMS/04-基礎設施-loop與daemon.md)、[N-36～N-40](../NORMS/07-基礎設施-組合子.md)、[N-45](../NORMS/06-基礎設施-命令列與指示詞.md)｜現況程式：lib agent.md（已刪，見 git 歷史 aa2fec1f）、frame.md、fsm.md、loop.md

> **這是 AI（Fable）的提案稿，還沒拍板。** 只有第一節是使用者的話；其餘都是提案，等使用者點頭才改概念、規範、程式。
>
> 注意：[KISS 彙整](2026-10-15-kiss/README.md)裡「都照推薦」那句，使用者 10-16 說是當時懶得想才說的、要重看；所以本稿**不把彙整當已定前提**，碰到時會標出來。第四版「工具一律走 frame（args.json 進、ret.json 出）」使用者 10-16 否定了（見第一節第 2 段）。
>
> **10-16 晚補**：使用者看完第二節後說他想的 Lua 繼承其實是「一手接一手的轉手鏈」（原話在 [§ 二之二](#二之二兩條路並排轉手鏈shebang-式vs-加-keylua-式10-16-晚補ai-提案)），並新定一條原則「寫什麼就做什麼、不埋暗規則」。二之二把兩條路並排比較，第二節 2.4（內建預設表）、2.5（沒寫 stdin 就餵整份）兩段照新原則**撤回**，拍板點已更新。
>
> **10-20 清理**：照 [user.md](../../wf/workflows/common/user.md#討論紀錄只留原文決定結論2026-10-12-夜改) 只留原話、決定、結論。AI 的分析、比較、被推翻的方案已刪（舊版在 git 歷史：`git show 0b7758b7:proto8/thinking/2026-10-16-agent-inherit.md`）：「三分鐘看懂」只留（五）（使用者說它「算定了」）；第二節整節刪；二之二、二之三只留原話；拍板點與第五～八節濃縮成結論與「沒拍板」清單。本稿這套做法 10-19 已整套作廢（見 [proto8 README](../README.md)）。

## 三分鐘看懂（五）：/ws 保持乾淨——一般工具站在工作區、agent 工具站在自己的 frame（10-16 夜重想）

一次一件事。**工作區**＝/ws，你的檔；**frame**＝跑的時候才往裡放東西的資料夾（history、狀態、每次叫工具開的小格）。

- bob 站在 frame（例 `/bob1/`）跑；frame 裡兩條捷徑：`.aos → 定義`、`ws → /ws`。/ws 一個字都不多。
- 每次叫工具，工具格開一個小格 `calls/1/`，裡面也放一條 `ws → ../../ws`，每個工具都一樣，工具格不問對方是誰。
- **一般工具（write、date）站在工作區**：它的 inst 裡有一行 `"cwd": "ws"`——aos 給的工具範本本來就寫好這行，設計者不用想；寫 `now.py` 就是 `/ws/now.py`。
- **agent 工具（brush）站在自己的小格**：它的入口不寫 cwd，照 inst 本來的規矩就站在小格＝它的 frame，history 記在那；要碰工作區走 `ws/…`，它的工具再往下也是同一個 /ws。

要你點頭的兩件：**①「預設站哪」只靠工具自己入口那一行字（有 `cwd: ws`＝工作區、沒有＝自己的 frame），工具格與門房一律同一個動作**；**②那一行由範本給，不是門房或 inst 偷改預設**（偷改＝同一份 inst 在不同地方跑會不一樣，是暗規則）。細節在第八節 3。

## 一、使用者原話（10-16，整理版）

1. **agent 用 aos-agent，JSON 裡內嵌 aos-fsm 的東西；想想 Lua 的物件導向**：「agent 那塊我有新想法：可以不純用 aos-fsm。就如同 aos loop 是 inst 的擴張——有點類似 Lua 的物件導向繼承方式——我們也可以用 aos-agent，那個 JSON 格式中就是內嵌 aos-fsm 的東西。Lua 的物件導向這塊請 Fable 思考一下，在我們這套 JSON inst 體系下可以怎麼應用。」
2. **不要 args.json／ret.json；agent 當函數是概念上的，不是形式上的**：「我不喜歡 args.json／ret.json。我知道這是昨天我說『把 agent 當函數用』的直觀體現，但這極致體現了 AI 的蠢蛋之處。把 agent 當函數用，不是說形式上，而是在概念上，不要皮似神不似。我們現在就是把 JSON＋資料夾當 Lisp 的 list，這就是一個函數啊，何必再造一個體系？」
3. **KISS 是最高原則，但也是最後原則**：「本質上是希望提出的設計在滿足各類需求和原則後，最後能回頭思考，把一些多餘的東西清掉。」（所以不能拿 KISS 當抄近路的理由：先把需求和其他原則滿足，最後才清。）

## 二之二、兩條路並排：轉手鏈（shebang 式）vs 加 key（Lua 式）（10-16 晚補，AI 提案）

### 0. 使用者原話（10-16 晚，整理版）

「Lua 繼承那塊，其實我是在想：好比說 `bob/inst.json` 是 `{"argv": ["aos-inst"], "stdin": "agent.json"}`，然後默認我們都先 `cd` 到 `bob/`，再 `cat inst.json | aos-inst`（這就是 aos-exec 語法糖的作用）。然後 `bob/agent.json` 也是一個 inst 格式：`{"argv": ["aos-inst"], "stdin": "agent-fsm.json"}`，那個 `agent-fsm.json` 又是另一個 inst 格式。至於怎麼讓 agent 的工作目標換成我們 `cd` 到 `bob/` 之前的資料夾，那就另外再說……感覺有點怪。」

同日新定的原則（C-56 補充）：「不要用這種方式添加規則，不直觀，這等同於埋雷。大家都預期『我給啥檔案，他就是往這個檔案塞東西』，你還要人家記『如果給的是這個檔案，那他會幹別的事情』，這太糟糕了。」——**寫什麼就做什麼；不拿暗規則去換少寫一個 key。**

## 二之三、`aos-exec WD TARGET`（10-16 晚再補，AI 提案）

### 0. 使用者原話（10-16 晚，整理版）

「其實 aos-exec 我覺得可以用另一個使用方式：`aos-exec WD TARGET`，也就是 `aos-exec . bob/`。」（頂層攤了三個邊緣：定義裡的相對路徑從哪算、WD 跟 inst 自己的 `cwd` 撞了聽誰的、WD 必不必填；使用者「好」。）

## 三、要使用者拍板的點（每點一句＋推薦＋理由＋後果；10-16 晚更新，含 WD）

10-16 晚～夜陸續攤的 24 點。已定的決定寫在[第四節](#四使用者決定10-16)，這裡只補它沒寫到的細節；沒拍板的留題目與當時的推薦（10-16 進了 NORMS 待定，10-19 整套作廢時清掉）。理由與後果拿掉；第 5、7、8、15、20 點被後來的決定推翻，刪。

**已定的細節**（決定本身見第四節）

- 4. 拿掉 args.json／ret.json（frame.json 跟著不要）。同點的「`aos agent` stdin＝這次的話」被第四節「stdin 只放食譜」推翻。
- 14. 食譜與廚房的接法＝A 捷徑：廚房掛 `.aos → 食譜`，食譜自稱 `.aos/x`；`aos-agent-init` 寫這條捷徑（糖）；食譜收進 `.aos/`；v4「aos-exec 不寫檔」鬆一格（第五節 3）。
- 16. 食譜當指令：食譜裡一個兩行 stub（`#!/usr/bin/env -S aos exec .`）＋PATH 的 bin 一條捷徑；`aos exec` 解開捷徑、取所在資料夾當食譜、WD 沒 `.aos` 就掛（掛好就跑）；需 `env -S`（第六節 2）。後來第七節定不用 PATH，stub＋PATH 只留給人在終端打指令。
- 17. 工具參數分兩層：tool 格照 N-27 把 arguments 當 stdin 餵工具；agent 當工具時收 stdin 的是門房 `aos exec`；`aos agent -` 那層 stdin 仍只放食譜（使用者「感覺 OK，就先這樣」）。當時寫的「門房由 stub 上的 `--say` 旗標把 stdin 放進廚房、跑完印回答」，`--say` 後來不要了（第七節 3 的註）。
- 18. 推廣到所有東西：任何「定義＋這次在哪做」都是「`.aos/` 食譜＋廚房」、一律 `aos exec WD TARGET`；C-50 改成「食譜＝一個 .aos/ 資料夾」（第六節 4、5）。
- 19. 不用 PATH：地址放在呼叫者食譜的 `.aos/tools/<名>`（相對捷徑），工具格站在廚房叫門房 `aos exec work/<n> .aos/tools/<名>`；工具一律是食譜資料夾、`tools.json` 退場（第七節 2）。
- 21. frame 與工作區分開：站在 frame 跑，執行時的東西都在 frame；規範的「工作區（cwd）」改叫 frame（同夜再改名 stack，見第四節）。
- 22. 「預設站哪」只靠工具自己入口那一行：一般工具的 inst.json 寫 `"cwd": "ws"`（範本給；後來改成 `"cwd": {"$env": "AOS_WS"}`，見第四節），agent 的入口不寫＝站自己的 frame；能不能寫＝/ws 的 Linux 權限；門房、inst 的「沒寫 cwd＝叫的人站的地方」不偷改。使用者「默認 ws 是工具的 cwd」「brush 默認自己的 frame」「風險設計者自管」。站在 ws 的工具只能是 argv 程式＋stdin 那種（第八節 3）。
- 24. frame 指到哪是呼叫方的自由，寫成概念條（第八節 3b）。

**沒拍板的**（題目＋當時的推薦）

- 1. 定義長什麼樣：甲 轉手鏈（cd 進 bob/、七個檔一手接一手）／乙 加 key（一份 JSON 加 `brain`／`tools`／`system` 三個 agent 級 key）／丙 合起來（agent.json＝一張 fsm、每格 stdin 寫在裡面、`aos agent` 只當邊界）。推薦丙。
- 2. 表一定寫、每格 stdin 一定寫；程式不藏預設表、不替格補 stdin（lib 放一份範本 agent.json 給人抄或 `$ref`）。推薦是。
- 3. binding＝另一份 JSON；拿掉「資料夾放同名檔蓋過定義」與 parent 鏈；資料夾只放狀態（history、窗、work）。推薦拿掉。
- 6、13. `aos exec WD TARGET` 不默認 cd 進定義資料夾，WD 必填（不設預設 `.`）。推薦必填。
- 9. 格庫瘦身：intake／done／route 消失，think 自己回 next，`aos agent fsm` 刪。推薦是。（連錯計數：第四節已定 agent 不數。）
- 10. 輸入的形狀：stdin 一份 JSON＝user 訊息的內容（字串照放、物件照 JSON 文字放），不收整則訊息物件；空 stdin＝沒新話、接著跑。推薦是。
- 11. 定義裡的相對路徑一律從 WD 算（照 aos-inst 現行規矩；要指自己旁邊的檔＝絕對路徑、內嵌、或 `$ref` 載入時攤平）。推薦是。
- 12. inst 自己的 `cwd` 從 WD 往下算（不是 WD 蓋過、不是報錯）。推薦是。
- 18 的其餘：N-35 改成「檔＝所在資料夾、資料夾＝自己、掛到 WD/.aos」；刪 `AOS_DIRNAME`、exec 的 `檔#/位置`、`aos agent TARGET` 入口。推薦是（第六節 5）。
- 21 的其餘：`work/<n>` 改成 frame 裡的 `calls/<n>`；frame 的位置由叫的人指定（`aos init FRAME 定義 工作區`）。推薦是。
- 22 的其餘：每個小格都放 `ws → ../../ws`（工具格一律同一個動作、不問對方是誰）。推薦是。
- 23. 參數與回答都不經門房旗標：工具格把 arguments 放成小格的 `prompt.json`＋照 N-27 餵 stdin；回答靠定義入口最後一步 `say`（入口＝`seq(run: loop 拍 agent.json, say)`，agent.json 不含 loop，N-53）；門房只剩掛與跑；「agent 當工具誰包 loop」＝入口包。推薦是（第八節 3）。

## 四、使用者決定（10-16）

- 正規參數入口是 stdin，`aos agent 路徑`、`aos-exec WD TARGET` 這類 argv 寫法都是語法糖（使用者：「argv:[aos,agent,agents/brush]，其實，我一直覺得argv這塊的用法...就像我早期說的，正規參數入口就是stdin，像是aos-exec WD TARGET這個用法是語法糖...」）。
- **agent 的 stdin 只放一份，這份是食譜（定義）**（使用者：「stdin只放一份，這份要食譜。」）。
- **「這次的話」放在廚房（工作區）裡，使用時指定廚房的位置**；以後可能做類似 aos-exec 的語法糖，例如 `aos-agent-say`、`aos-agent-init`（使用者：「放在廚房裡，然後使用的時候指定廚房的位置。以後可能會做類似aos-exec那樣的語法糖，比如aos-agent-say, aos-agent-init...」）。
- **agent 當函數是概念上的**：JSON＋資料夾就是 Lisp 的 list、本身就是函數，不造 args.json／ret.json（frame.json 那套跟著不要）——原話在[第一節](#一使用者原話10-16整理版)第 2 段。
- 以下四條是 10-16 夜在第五～七節之後陸續定的，原本記在各節末尾，10-16 收進本節（第二～七節其餘都是 AI 提案，沒列在本節的不算定了；落成見 [CONCEPTS C-46、C-50、C-57～C-61](../CONCEPTS.md)、[NORMS N-46～N-51](../NORMS/10-基礎設施-定義與工作區.md)，沒點頭的進 [待定](../NORMS/08-待定.md)）。
- **食譜與廚房的接法選「捷徑」**（第五節候選 A：廚房放 `.aos → 食譜的 .aos` 的 symlink，食譜裡互指一律寫 `.aos/x`；使用者：「捷徑。這塊細說」）。
- **第六節前兩項同意**：食譜裡放 shebang stub＋PATH 上放捷徑（bob 的工具寫 `{"argv": ["brush"]}`）；「食譜 `.aos/`＋廚房 cwd」一律 `aos exec 廚房 食譜`，推廣到所有東西（使用者：「何等美麗的閉環，這就像是lisp的repl，/ws就是那個啥...」「前兩項我都OK」）。
- **工具參數走門房（`aos exec`）的 stdin，分兩層**：使用者問「關於工具的參數不能再走stdin這塊，這是為啥？」——答：stdin 只放食譜指的是 agent 程式那一層；工具行程（門房 `aos exec`）那一層的 stdin 是空的，照 N-27 收參數，由 stub／旗標明寫把它放進廚房（第六節 2 的 4、5）。使用者：「還是不太懂，但感覺OK，就先這樣吧，以後再來搞懂。」
- **不用 PATH（第七節）**：brush 的地址寫在 bob 食譜裡的相對捷徑（`.aos/tools/brush`）；工具格站在自己廚房叫門房 `aos exec work/<n> .aos/tools/x`；**工具一律做成食譜資料夾**（`date` 也是 `.aos/tools/date/`）（使用者：「可以不使用PATH嗎？」→ 看完第七節：「好!」）。PATH 只留給人在終端用。
- **agent 是被外面驅動的狀態機、定義不含 loop、連錯不數**（10-16，在 [KISS 重審拍板 4](2026-10-16-kiss-recheck.md#使用者拍板10-16) 定）：使用者：「agent的定義就是一個狀態機，至於這個狀態機怎麼跑、由誰跑，都無所謂。這是概念。但是我們的規範會說，為了讓agent方便審視自己，所以agent就是一個被人驅動的狀態機，需要外面有人用loop驅動他。」所以本稿第二節 3.5 第 4、5 步、3.6、拍板點 7、第七節 3 裡「`aos agent -` 自己一拍一拍跑到 end（才吐回答）」**不採用**：`aos agent` 每次被叫只走一拍，由外面的 loop 驅動（落成 C-62、N-53）。

- **指標＝捷徑**（10-16 夜，第八節之前定）：工具要影響呼叫者的工作區，像 C 函數影響外部變數一樣要透過指標——由呼叫方遞一條指向工作區的捷徑進去，不是工具自己伸手出去；能不能寫由 Linux 權限管（C-64）。（使用者：「除此之外，C語言函數想要影響外部變數，那也是透過指標」→ 頂層問「指標＝一條指向工作區的捷徑？」→「那就是捷徑」）。名字、放哪、誰掛、唯讀怎麼表達是第八節的提案，還沒定。
- **一般工具預設站在工作區、agent 工具預設站在自己的 frame**（10-16 夜，看了第八節第一版後）：「還要『端菜』，我還以為就是直接把ws當作工具指令的cwd呢」→ 頂層：工具的 inst 自己寫 `"cwd": "ws"` →「對，我覺得這樣會更方便。風險就設計者自己管控」；再補：「我是覺得不用『遞』，而是就是默認true，默認ws就是工具的cwd...可以嗎？」「同樣用捷徑？」「brush這種agent工具，那就是他的cwd默認是他自己的frame。」→ 第八節重想（兩種預設各寫在哪見第八節 3）。
- **frame 指到哪是呼叫方的自由**（10-16 夜）：「只是我們可以偷偷把它的frame設成ws」「我們可以自由管控他的frame要在哪裡，從而達到各種神奇效果」——frame 放哪由呼叫方決定、agent 不知道也不必知道（C-52）；指到 ws 也合法（代價：history、狀態、`.aos` 都落進 ws，ws 不再乾淨、可能撞名，是呼叫方自己的選擇）；這是概念層刻意保留的自由度，例子與邊緣見第八節 3b。
- 同時說的（原話，第八節要處理）：「我記得先前還有一個叫做frame的概念，也就是agent當函數，函數運行時候的heap(還是stack?反正就是運行時才會往其中放資料的)，可以指定某個資料夾當heap。用捷徑也不錯。然後我不喜歡/ws底下出現一個work/，這太突兀了，工作區會變得不乾淨。」
- **frame 與工作區分開（看完第八節「三分鐘看懂（五）」）**：使用者：「我覺得不錯。不過是不是可以採用環境變數？所以cwd: WS? 具體命名幫我想想。」——（五）的內容算定了：frame 與工作區分開、/ws 零殘留、工具格與門房對每個工具一律同一動作、一般工具入口 inst 寫一行站工作區、agent 工具不寫＝站自己的 frame、那一行由範本給不偷改預設、frame 放哪是呼叫方的自由。**名詞**：原本稿／條文把 cwd 叫「工作區」的，改叫 **frame**；「工作區」留給使用者的成品區。（落成 C-65～C-67、N-56；`calls/<n>/` 小格命名、每個小格放 `ws` 捷徑、`aos init` 引數、`say`、入口包 loop 仍是提案，進[待定](../NORMS/08-待定.md)）
- **工作區位置用環境變數 `AOS_WS`、讀它用 `$env`**：頂層提名 `AOS_WS`（ws＝workspace，進縮寫表），並指出 `"cwd": "WS"` 字面替換是暗規則；使用者：「可以用$env啊」。頂層指出跟 N-45（設計不靠指示詞）衝突，給 A（`$ref` 仍只是拆檔便利；`$env` 讀執行當下的環境，可以當正式機制，像 shell 的 `$HOME`）／B（維持 N-45、改用 `cwd_env` key）；使用者：「A」。所以一般工具的入口寫 `"cwd": {"$env": "AOS_WS"}`（由 aos 的工具範本給好）。（落成 N-45 改、N-55、N-56、C-48 改、abbr.json 加 `ws`）
- **frame 改名 stack**（10-16 夜，上一條之後）：使用者：「不過frame那塊能不能換成stack(或heap)?。」→ 頂層推薦 **stack**（每次呼叫疊一層 `calls/<n>/`、結束收掉＝呼叫堆疊；大家一看就懂；frame 其實是 stack 裡的一層），**heap** 保留給以後跨呼叫的共用記憶（第八節提過的 `mem` 捷徑）→ 使用者：「好！」。所以概念與規範裡指「執行時站的資料夾」的 frame 一律改叫 stack；本稿其餘各節是當時的討論，照原樣留著 frame 這個字。（落成：C-46、C-58～C-61、C-65～C-67、N-47～N-56、待定、名詞表改字；名詞表加 stack／heap 兩列）

## 五、自然組合的機制（找）（10-16 夜，AI 提案）

### 0. 使用者原話（10-16 夜，整理版）

「哇，可是我不想用 `$ref`……」「JSON 大沒關係的基礎，就是因為我們有 `$ref`……我也不想用絕對路徑。我也不想要用小工具編譯，我想要依靠機制自然組合。我也不想用暗規則……」→ 請 Fable 去找那個新機制。

### 1. 題目（使用者給的情境）

```
/ws/                      ← 廚房，cwd 在這
  prompt.json             {"role": "user", "content": "幾點？"}
/agents/bob/              ← 食譜
  inst.json               {"argv": ["aos", "agent", "-"], "stdin": "agent.json"}
  agent.json              fsm 形狀；格的 stdin 指 tools.json
  tools.json              工具（含 shell 工具）
$ cd /ws && aos-exec . ../agents/bob
```

卡點：`"stdin": "agent.json"`、`"stdin": "tools.json"` 是從 cwd 算的，站在 /ws 找不到。被否決的：一份大檔、`$ref`、絕對路徑、編譯工具、「定義路徑從所在檔算」（同一個 key 兩種規則）。

### 3. 候選 A：廚房裡掛一條捷徑指向食譜（symlink＝最便宜的 Plan 9 bind）

使用者選這條（第四節）。食譜收進 `<定義>/.aos/`；廚房（cwd）放一條捷徑 `.aos → 食譜的 .aos`；食譜裡**所有**互指一律寫 `.aos/x`、從廚房算，站在廚房就找得到。沒有新規則：`.aos/` 是 N-35 已有的、捷徑是 `ln -s`。

```
/agents/bob/.aos/                      ← 食譜搬進 .aos/ 底下（bob/ 本身就是一個示範廚房）
  inst.json     {"argv": ["aos", "agent", "-"], "stdin": ".aos/agent.json"}
  agent.json    {"start": "intake", "state": "fsm/state.json", "end": ["done"],
                 "states": {
                   "intake": {"val": {"argv": ["aos", "agent", "intake"], "stdin": "prompt.json"}, "next": "think"},
                   "think":  {"argv": ["aos", "agent", "think"], "stdin": ".aos/tools.json", "timeout_ms": 200000},
                   "tool":   {"val": {"argv": ["aos", "agent", "tool"], "stdin": ".aos/tools.json"}, "next": "think"}}}
  tools.json    {"brain": {"argv": ["aos", "brain", "openai", "--model", "gpt-x"]}, "system": "你是 bob…",
                 "tools": {"date": {"argv": ["date", "+%H:%M"], "_tool": {…}}}}

$ cd /ws
$ aos-agent-init . ../agents/bob            # ＝ ln -s ../agents/bob/.aos .aos   （語法糖；廚房多一條捷徑，食譜一字不動）
$ aos-exec . .                              # ＝ aos inst - < .aos/inst.json    （WD＝.、TARGET＝.：廚房就是 TARGET，N-35 找到 .aos/inst.json）
{"id": …, "code": 0, …}                     # stdout＝N-30 結果；回答在廚房：
$ cat history.json                           # […, {"role": "assistant", "content": "三點整。"}]（之後 aos-agent-say 語法糖印最後一則）

/ws/  .aos→/agents/bob/.aos  prompt.json  history.json  fsm/state.json  work/1/
```

- 這次的話：intake 格的 stdin 是 `prompt.json`，接進廚房的 history.json；回答留在廚房 history.json（之後 `aos-agent-say` 糖印最後一則）；`aos-exec` 的 stdout 只是 N-30 結果。
- 在食譜自己的資料夾裡跑：`cd /agents/bob && aos-exec . .`，`.aos/` 本來就在、不用捷徑。同一份食譜、兩個廚房同時跑＝兩條捷徑指同一處，互不相干。
- 鬆掉的條件：`aos-agent-init` 會往廚房寫一條捷徑（v4「aos-exec 不寫檔」鬆一格）。

## 六、捷徑：agent 當工具與推廣到一般函數（10-16 夜，AI 提案）

### 0. 使用者原話（10-16 夜，整理版）

「捷徑。這塊細說。」→ 細說後：「太優雅，太美了，這就是我要的。可以的話針對 4（agent 當工具：bob 叫 brush，工具在 `work/<n>/` 跑、那裡也要一條捷徑），還有非 agent 函數的情況再去多思考。」

### 2. 邊緣 4：bob 叫 brush——誰、怎麼在 `work/<n>/` 掛捷徑

使用者「前兩項我都 OK」（第四節；地址後來改成不用 PATH，見第七節）。

- tool 格做的事不變、不知道工具是不是 agent（C-52）；掛捷徑由工具自己完成，靠 Unix 本來就有的 **shebang** 與 **PATH**：brush 的食譜裡放兩行的 stub `brush`＝`#!/usr/bin/env -S aos exec .`；PATH 的 bin 裡放 `brush → ../brush/.aos/brush`（相對捷徑，唯一寫「brush 在哪」的地方）；bob 的工具寫 `{"argv": ["brush"], …}`，跟 `date` 一樣。
- 跑起來：tool 格在 `work/3/` 跑 `{"argv": ["brush"], "stdin": <arguments>}` → 核心照 PATH 找到 stub、看到 `#!`，變成 `aos exec . /agents/bin/brush` → `aos exec`：TARGET 是檔＝解開捷徑、所在資料夾 `/agents/brush/.aos` 就是食譜；WD `.`＝`work/3/`，沒有 `.aos` 就掛上（算出來的絕對路徑），灌 `.aos/inst.json`。brush 自己的鍋碗（prompt.json、history.json、fsm/state.json、work/1/）都在 `work/3/`。
- 參數分兩層（10-16 夜，使用者「感覺 OK，就先這樣」）：tool 格照 N-27 把 arguments 當 stdin 餵給 stub 跑起來的門房 `aos exec`；裡面那層 `aos agent -` 的 stdin 仍只放食譜（第四節）；intake 格的 stdin 是 `prompt.json`。對 `date` 這種一般工具沒有門房，stdin 就是參數。當時由 stub 上的 `--say` 旗標把 stdin 放進廚房、跑完印回答——`--say` 後來不要了（第七節 3 的註）。
- 鬆掉的條件：exec 會往 WD 寫一條捷徑；exec 解開 TARGET 的 symlink；shebang 要 `env -S`（GNU coreutils 8.30 起）；exec 的 stdout 讓食譜的話透出來（碼透明轉交）。

### 3. 其他邊緣（一句一條）

（以下都沒拍板，10-16 進了待定。）

- **一個廚房一份食譜**：是，`.aos` 只有一條；想在同一處跑兩份就開兩個廚房（子資料夾）。exec 遇到 `.aos` 已存在且指別處＝`RecipeConflict`，不覆蓋。
- **捷徑相對還是絕對**：`aos init WD TARGET` 照人打的字寫（打相對就相對，廚房和食譜一起搬不壞）；exec 從 PATH stub 算出來的寫絕對（stub 本來就是絕對找到的）。
- **捷徑斷了**：`.aos` 指到不存在的地方＝exec 入口錯 `RecipeMissing`（stderr 一份 N-29、退 1；C-53 的「入口檢查」）；跑到一半食譜被搬走＝那一格自己報讀不到，照 N-38。
- **在食譜自己的資料夾裡跑**：`cd /agents/bob && aos exec . .aos`——`.aos` 本來就在，不用掛。這就是使用者最初「cd 到 bob/」的那個預設。
- **init 要不要建 WD**：`aos init` 建（mkdir＋掛）；`aos exec` 要求 WD 已存在（tool 格、daemon 本來就會先開資料夾）。
- **`AOS_DIRNAME`**：食譜裡寫死 `.aos`，這個環境變數沒用了→刪（見 5）。

### 4. 推廣：不是 agent 的東西怎麼用同一招

使用者「前兩項我都 OK」（第四節）。招式只有一個：**食譜＝一個 `.aos/` 資料夾（入口 inst.json，其餘檔互叫 `.aos/x`）；廚房＝cwd；`aos exec WD TARGET`。** inst 體系裡每樣東西照舊跑、一個 key 都不用改：一支工作（inst）、tasks 流水線（seq 站在廚房起 `.aos/fetch`）、fsm、loop（長壽 agent＝廚房掛 loop 食譜）、daemon 的子項（daemon 先開 `loops/1/`，stub 在那裡掛好就跑）、kernel 的判官（一份 agent 食譜，跟工具一樣）都成立；腦、`date` 這種純指令不需要食譜。卡住的只有一處，是刻意的：一個廚房一份食譜（`.aos` 只有一條），要兩個就開兩個廚房。

```
/jobs/report/.aos/
  inst.json          {"argv": ["aos", "seq", ".aos/fetch", ".aos/render"]}
  fetch/inst.json    {"argv": ["curl", "-s", "-o", "raw.json", "https://example/api"]}
  render/inst.json   {"argv": ["python3", ".aos/render/render.py"], "stdin": "raw.json", "stdout": "report.json"}
  render/render.py
$ mkdir /out/1016 && cd /out/1016 && aos exec . /jobs/report/.aos
/out/1016/  .aos→/jobs/report/.aos  raw.json  report.json
```

### 5. 這樣之後可以刪的、要改字的

- 已定：C-50 改字——定義＝一個 `.aos/` 資料夾（入口 inst.json；想寫成一份大 JSON 也行，那只是檔少一點）；資料夾是食譜，檔之間用 `.aos/x` 互叫，不靠 `$ref`（使用者 10-16 夜「不想用 $ref」「依靠機制自然組合」）。frame 殘骸（frame.json、parent 鏈、`aos_frame.py`、args.json／ret.json）刪（第四節）。
- 沒拍板（推薦刪或改）：`AOS_DIRNAME`（固定 `.aos`）；aos-exec 的 `檔#/位置`（留給 `$ref`）；`aos agent TARGET`／`aos agent WD TARGET` 入口（食譜一律 `aos exec` 跑）；三張 `sh -c` 工具 inst 與 `AOS_DEMO`；N-35 改成一句「TARGET 是檔＝它所在的資料夾、是資料夾＝它自己（裡面要有 inst.json）；exec 把它掛成 WD 的 `.aos`」；C-51 的隱藏資料夾例外就是 `.aos`。

## 七、不用 PATH：地址放哪（10-16 夜，AI 提案）

### 0. 使用者原話（10-16 夜，整理版）

「何等美麗的閉環，這就像是 Lisp 的 REPL，/ws 就是那個啥……前兩項我都 OK。」接著問：「可以不使用 PATH 嗎？」（PATH 是整台機器的環境，換環境可能找不到。）頂層攤了兩個放法（地址寫在 bob 的食譜裡、或寫在廚房），使用者「好」。

### 2. 更自然的做法：工具格不走進小廚房，站在自己廚房叫門房

使用者看完說「好!」（第四節）。工具格站在廚房不動，把小廚房當 WD、把食譜裡的捷徑當 TARGET 交給門房，路徑全從廚房算，沒有深度問題（不會出現 `../../…`），也沒有 PATH：

```
/agents/
  bob/.aos/
    inst.json          {"argv": ["aos", "agent", "-"], "stdin": ".aos/agent.json"}
    agent.json         …（think、tool 兩格，見第六節）
    tools/
      date/inst.json   {"argv": ["date", "+%H:%M"], "_tool": {"description": "報現在時間", "parameters": {…}}}
      brush → ../../../brush/.aos          ← 畫筆的地址：一條相對捷徑，寫在 bob 自己的食譜裡
  brush/.aos/
    inst.json          {"argv": ["aos", "agent", "-"], "stdin": ".aos/agent.json"}
    agent.json  tools/palette/inst.json

/ws/                   ← bob 的廚房（.aos → /agents/bob/.aos）
  prompt.json  history.json  fsm/state.json
  work/3/              ← 工具格開的小廚房
    .aos → /agents/brush/.aos             ← 門房掛的（從 /ws/.aos/tools/brush 解出來）
    prompt.json  history.json  fsm/state.json  work/1/
```

- 工具格對**每一個** tool_call 做一模一樣的事（站在 /ws）：`mkdir work/3`，`aos exec work/3 .aos/tools/brush`（stdin＝模型給的 arguments；stdout 最後一份＝結果）。門房把 `.aos/tools/brush` 解成 `/agents/brush/.aos`、掛成 `work/3/.aos`、灌 `.aos/inst.json`。
- **工具一律是食譜資料夾**（`date` 也是 `.aos/tools/date/inst.json`），`tools.json` 不需要了：工具清單＝`ls .aos/tools/`，說明＝各自 inst.json 裡的 `_tool`；inline 的工具 inst 要搬成 `.aos/tools/<名>/inst.json`。
- 畫筆看不到 bob、不需要 PATH；位置是 bob 的事、掛是門房的事、裡面是畫筆的事（C-52）。人在終端想打 `brush`，第六節的 stub＋PATH 捷徑照樣能用，體系內部不靠它。
- 捷徑的目標是相對的（`../../../brush/.aos`），bob 與 brush 要在同一棵樹下一起搬。

### 3. `--say` 在這裡怎麼擺

> **10-16 夜註**：(a) 裡「`aos agent -` 跑到 end 吐回答」被 N-53 否決；回答怎麼回去改看第八節 6（入口最後一步 say），`--say` 旗標不要了、`--prompt` 留。

（第八節 6 在 10-20 清理時已刪，沒拍板的部分併進第八節 3 最後一條。）

### 4. 頂層那兩個放法怎麼樣

選「一、地址在 bob 食譜裡」（`.aos/tools/brush → …`），就是上面第 2 段；「二、地址在廚房」不選。

## 八、工作區與 frame 分開（10-16 夜重想，AI 提案；「指標＝捷徑」「工具可直接 cwd: ws、風險設計者自管」已定）

### 0. 使用者原話（10-16 夜，整理版）

「交給 Fable 把幾種方向走一遍。然後我記得先前還有一個叫做 frame 的概念，也就是 agent 當函數，函數運行時候的 heap（還是 stack？反正就是運行時才會往其中放資料的），可以指定某個資料夾當 heap。用捷徑也不錯。然後我不喜歡 /ws 底下出現一個 work/，這太突兀了，工作區會變得不乾淨。」

「除此之外，C 語言函數想要影響外部變數，那也是透過指標。」→「那就是捷徑」（已定：指標＝一條指向工作區的捷徑）。

看了第一版第八節後：「還要『端菜』，我還以為就是直接把 ws 當作工具指令的 cwd 呢」→ 頂層：工具的 inst 自己寫 `"cwd": "ws"` →「對，我覺得這樣會更方便。風險就設計者自己管控」「讓 Fable 重新思考」。再補：「我是覺得不用『遞』，而是就是默認 true，默認 ws 就是工具的 cwd……可以嗎？」「同樣用捷徑？」「brush 這種 agent 工具，那就是他的 cwd 默認是他自己的 frame。」「只是我們可以偷偷把它的 frame 設成 ws」「我們可以自由管控他的 frame 要在哪裡，從而達到各種神奇效果」

題目：/ws 是使用者的資料夾，叫 bob「幫我在這個資料夾寫一個 python 腳本」，`now.py` 要落在 /ws；/ws 不能被弄髒。照今天全部定案：stdin 只放定義（C-58）、捷徑接定義（C-59）、門房（C-60）、工具＝定義資料夾、地址在呼叫者定義裡（C-61）、agent 一次一拍由外面 loop 驅動（N-53）、SIGTERM 優雅收工（N-52）、結果看 JSON（C-63）、權限借 Linux（C-64）。

### 1. 兩個東西、兩條捷徑

| | 工作區 | frame |
|---|---|---|
| 是什麼 | 使用者的檔、成品要留的地方（/ws） | 跑的時候才往裡放的：history.json、fsm/state.json、loop 的窗、每次叫工具開的小格 `calls/<n>/` |
| 誰決定在哪 | 使用者站的地方 | 叫的人指定（「可以指定某個資料夾當 heap」） |
| 跟 C 比 | 外部變數 | 函數跑起來的 stack frame（續聊＝同一個 frame 再跑；要忘記＝換一個） |

站在 frame 跑；執行時的東西都在 frame，工作區保持乾淨（第四節；frame 同夜改名 stack）。當時提的 frame 裡兩條捷徑（`.aos`＝我的定義、`ws`＝我被遞進來的工作區）中，`ws` 那條後來改成環境變數 `AOS_WS`、讀它用 `$env`（第四節）。

### 3. 兩種「預設」寫在哪，才不是暗規則

使用者看完「三分鐘看懂（五）」說「我覺得不錯」（第四節）。

- 一般工具**預設**站在工作區、agent 工具（brush）**預設**站在自己的 frame——「預設」落在工具自己的入口那一行：一般工具的 inst.json 寫 `"cwd": "ws"`（後來改成 `"cwd": {"$env": "AOS_WS"}`，第四節），agent 的入口不寫＝站在小格＝它的 frame。只有兩種寫法：有＝工作區、沒有＝自己的小格。`_tool` 不加 `"ws": true` 簽名（使用者「不用『遞』」）。
- **「默認」由範本提供**：aos 自帶的工具（`aos write`…）與工具範本寫好這行，設計者抄範本就不用想；agent 範本沒這行。門房、inst 的「沒寫 `cwd`＝站在叫它的人站的地方」不偷改（偷改＝同一份 inst 在不同地方跑會不一樣，是暗規則）。
- 站在 ws 的工具拿不到自己的 `.aos/`（`.aos/x` 從 /ws 算就不在）：站在 ws 的工具＝靠 argv 程式＋stdin 的那種（`aos write`、`date`、`git`…）；要帶自己的檔就留在小格。
- 沒拍板（第四節括號裡列的提案）：每個小格放 `ws → ../../ws`；門房的 `--prompt`／`--say` 不要（參數＝工具格放小格的 `prompt.json`＋照 N-27 餵 stdin；回答＝定義入口最後一步 `say`；入口 `inst.json` 可以含 loop 與 say，agent.json 不含 loop）；小格叫 `calls/<n>`；frame 由叫的人指定（`aos init FRAME 定義 工作區`）。

### 3b. frame 指到哪是呼叫方的自由（概念層的一句）

frame 放哪由叫的人決定，被叫的 agent 不知道也不必知道（C-52）——這是刻意留下的自由度：**「frame 在哪」只是一條捷徑的指向**，改指向就得到不同效果，規則一條都不用加。例子與各自的邊緣：

| 怎麼指 | 效果 | 邊緣 |
|---|---|---|
| **frame＝ws**（叫 brush 時小格就做成指向工作區的捷徑，或人直接 `aos init /ws /agents/bob/.aos /ws`） | agent 直接在使用者的資料夾裡跑，history、狀態留在那裡，像「就地辦公」 | `.aos`、`ws`、`prompt.json`、`history.json`、`fsm/`、`loop/`、`calls/` 全落進 /ws——ws 不再乾淨；跟使用者同名的檔會撞（例使用者自己有 `history.json`）。frame 裡那條 `ws` 要不要有：**要**，掛成 `ws → .`（指回自己），這樣它底下工具的 `../../ws` 照樣接得上，規則不變。這些都是呼叫方自己的選擇與風險 |
| **兩個 agent 共用一個 frame** | 共享 history＝共享記憶、接力辦同一件事 | 兩個同時跑會互寫 history、fsm 狀態撞窗（N-39 不防護）；一個跑完換另一個才安全。`.aos` 只能指一份定義，兩個 agent 定義不同就得其中一個不經門房、或各自小格 |
| **frame 放 tmpfs／暫存目錄** | 用完即丟、不留痕跡 | 當機就沒了（想復原的別放這） |
| **frame 長期保留** | 下次指同一個 frame＝接著聊 | `calls/` 會一直堆，要自己清 |
| **frame 放在別人唯讀能看的地方**（C-64：擁有者可寫、群組只讀） | 旁人（人、kernel、另一個 agent）隨時能審視它的 history 與狀態，而改不了 | 看的人要遵守「只讀」是權限保證的，不是規矩保證的 |
| **frame 的 `ws` 指到唯讀的資料夾** | agent 只能看不能改那個工作區 | 工具寫檔會失敗、agent 要自己處理那個錯（C-53） |
| **frame 的 `ws` 指到另一個 agent 的 frame** | 讓 A 去整理 B 的 history（審視、摘要） | 這就是「上層伸手進下層」，刻意用才做；B 同時在跑就會互寫 |

一句話：**定義不動、規則不動，只換捷徑的指向**——這就是「資料夾＝空間、捷徑＝指標」帶來的自由（C-30、C-59）。
