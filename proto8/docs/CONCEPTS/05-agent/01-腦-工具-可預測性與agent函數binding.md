← [回入口 05-agent.md](../05-agent.md)｜段落：腦、工具、可預測性、agent＝函數＋binding｜上一份：—｜下一份：[01-續-C-22](01-續-C-22.md)

## 腦、工具、可預測性

- **C-19** agent 的簽名＝腦（模型）＋記憶（核心人格、近期記憶）＋手腳（工具）。（2.17）核心人格（system 文字）這隻自己也能換——`self_system`／`aos-agent system` 寫 stack 那份、定義不動（[thinking self-system](../../../thinking/2026-11/11/self-system/README.md)）。
- **C-20** agent 是複合型任務（外迴圈便宜、叫的模型與工具貴），所以要被排程；最核心的一題是「很多 agent 時誰先用腦」。（2.18、2.19）
  使用者 11-07「agent可以成千上萬個，反正可以sleep」，原話與嵌套的部分見 [C-47](../04-kernel.md)。（出處 [proto8/thinking/2026-11/07/arknights-kb/README.md](../../../thinking/2026-11/07/arknights-kb/README.md)）
- **C-21** 可預測性有主體性，不是任務的屬性，是觀察者的認識。（2.14、2.15）
<a id="c-22"></a>
- **C-22**（提高 agent 可預測性的方法）在 [01-續-C-22](01-續-C-22.md)。
- **C-22b** 可預測性不只是函式本身的：同一函式在不同狀況、不同（例如老舊）硬體上跑，可預測性不一樣。節點＝函式內部＋它所在的執行環境，合起來才是執行節點。（3g.13c）
- **C-23** agent 內部怎麼設計是後面的事，先把底打好。（2.20）
- **C-40** agent 要能當拋棄式函式用：引用一個設好的資料夾（標頭檔）、填幾個引數、讓它跑起來，執行環境在引用者這邊。library 做 binding 讓這件事簡單。（3g.9、3g.10）
<a id="c-42"></a>
- **C-42**（工具＝被引用的標頭檔、agent 也可以是工具）在 [01-續-C-42](01-續-C-42.md)。

## agent＝函數＋binding

- **C-46** agent 的使用＝函數＋binding：`agent_call(system, history, engine, tools)`；綁好就是 `agent_bob`，用時 `agent_bob.call(history, engine_args, tools_append)`。具體是一個 `bob/` 資料夾（定義：system、腦、工具、表），**呼叫時不變**，所以 bob 是可重複使用的函數。「呼叫時不變」指一次呼叫期間不變；兩次呼叫之間可以換版（[C-84](03-C-84.md) 自動換上），換上前有 proc 正在用那份定義就不換、等它跑完。已定；實作排在 evolve-design 的 promote 那步。（11-07 使用者裁定，傍晚選項框 ltn-4 選推薦，[lift-to-norms](../../../thinking/2026-11/07/lift-to-norms/README.md)）history 累積的地方（**stack**）是另一個參數，很像函數本體的 stack〔落成 `$AOS_STACK/history.jsonl`，P-41〕。**tools＝函數的包裝**，對 call 來說是「傳進去、可供它使用的函數」（像高階函數的參數）；bob/ 裡綁的 tools 只是預設值；tools 裡可以是另一個 agent 的呼叫（agent 當工具＝呼叫一次 bob），所以能一層層組合。（10-15 使用者定，概念層；[thinking 10-15 §11](../../../thinking/2026-10/15/topics/04-agent當函數.md#11-agent-當函數binding當工具)）
  **agent 當函數是概念上的，不是形式上的**（不用 frame 資料夾、`frame.json`（`parent` 鏈）、`args.json` 進、`ret.json` 出、「放同名檔＝綁定」這類形式）。使用者 10-16：「我不喜歡 args.json／ret.json。我知道這是昨天我說『把 agent 當函數用』的直觀體現，但這極致體現了 AI 的蠢蛋之處。把 agent 當函數用，不是說形式上，而是在概念上，不要皮似神不似。我們現在就是把 JSON＋資料夾當 Lisp 的 list，這就是一個函數啊，何必再造一個體系？」（[稿 § 一](../../../thinking/2026-10/16/agent-inherit/01-三分鐘看懂.md#一使用者原話10-16整理版)）**資料夾（程式）本身就是函數**（C-68；「Lisp 的 list」比喻用 table，C-71）；呼叫＝`aos-exec [--ws WS] XXX [args...]`（N-58）；資料夾（bob）呼叫時不變；**stack**（`$AOS_STACK`）就是函數的環境、像呼叫堆疊，狀態落在這裡，**放哪由呼叫方決定**（10-15 原話：「agent在呼叫時，可以選擇frame要放哪」；C-67）；這次的話放工作區（慣例 `new/`，P-11）；工具的地址與參數見 C-61。binding（這次換腦、加工具）落在設定檔：腦＝定義裡的 `llm.json`（`model`＝llm kernel 的能力包代號；包就是能力，換模型＝換代號，P-23；brain 把它填進請求信 body 的 `endpoint`），工具＝`tools.json`；stack 裡同名副本（`$AOS_STACK/llm.json`、`tools.json`）蓋過定義，所以呼叫方給它的 stack 放副本就換得了（P-23、P-15）；往哪個 kernel 問腦＝hub `AOS_LLM_KERNEL`（N-63，一路繼承，P-39）。思考本身也是 aos 函數、llm 設定包成代號：使用者 11-04 晚「brain url那塊我不喜歡，我希望llm呼叫，或者說思考，這本身也是用aos函數」「各種llm設定也可以包裝，這樣寄信的時候只要寫簡單的代號就可以」，[thinking 11-04 think-as-function](../../../thinking/2026-11/04/think-as-function/README.md)（細節 fable 代定、可翻案）；鍵名 `model` 出自使用者 11-10 晚「3.把fsm認的endpoint這個key，也改名爲model吧...麻煩的話就算了。」（[self-tools 05](../../../thinking/2026-11/10/self-tools/05-llm設定改名與ls.md)、[tonight-rulings](../../../thinking/2026-11/10/tonight-rulings/README.md) 第 8 題）。
  **徹底切割（C-52）**：agent 這層**只看到自己的工具清單**（名字、說明、參數），工具裡面在幹嘛——是不是另一個 agent、它的 stack 放哪、綁了什麼腦——agent 一概不管、不傳、不繼承；子 agent 只看自己的 stack、看不到呼叫方的（沒有 `parent` 鏈）。要換子 agent 的腦，是叫它那一行的事（一律給它的 stack 放 `llm.json` 副本換代號，P-39；`AOS_LLM_KERNEL` 只當 hub、不拿來換腦，使用者 11-04 晚選「只留 llm.json 代號」，[thinking 11-04 think-as-function 07](../../../thinking/2026-11/04/think-as-function/07-實作結論.md#使用者裁定11-04-晚選項)）（使用者：「agent他就是看到自己的工具，工具在幹嘛他就不管，拜託，乾淨，完全切割，徹底切割，不得有任何殘留。」）。
  同一隻跑久了，工具會被它自己（`self_tools`）改進覆蓋層——定義（函數本體）照樣不變、漂移只在 stack，`aos-agent ctl state` 會印出覆蓋層的改動（[feat-proto 01](../../../thinking/2026-11/05/feat-proto/01-self-tools.md)、[02](../../../thinking/2026-11/05/feat-proto/02-endpoint-packs.md) 代定 4）。工具要知道「叫我的是哪隻」＝**`aos-agent ctl who`**：拿自己的 `$AOS_STACK` 查 daemon 的表、找 stack 包住它的那列（經 daemon 表這個機制看上層，不從路徑往上爬；沒掛 daemon 的不支援，N-63）。
- **C-50** agent＝狀態機＋各狀態跑的 inst，複雜度集中在那些 inst（使用者：「agent基於狀態機，在某狀態下跑某個inst，所以複雜度主要集中在那些inst」）。「程式方面的實作可以擠在一坨，共用一些lib，但是在實際的資料夾布局和json那塊仍要保持單純」。（10-15 收工後意見 1～3，[thinking 意見 1～4](../../../thinking/2026-10/15/opinions-1-4.md)）
  **一個 agent 的定義＝一個資料夾**（C-68），入口 `_entry`（`$AOS_ENTRY`）；裡面的檔互相用相對路徑指、從這個資料夾算（起跑 cwd 就是它，N-59），不靠 `$ref`；檔少一點、把設定寫成一份大 JSON 也行（單子可內嵌，P-27）。agent 資料夾**可以帶 loop 當入口**（`aos-loop loop.json`，P-05、P-06；使用者 10-19，[ideas § 1](../../../thinking/2026-10/19/ideas/README.md)）。工具各是一個資料夾程式（C-61）。葉子程式（`date` 這類本來就是指令的）照舊用指令名；**資料夾程式之間互指不靠 PATH**（C-61）。
  **aos-agent 做成範本**（使用者 10-23；只產生標準 agent 資料夾，跑的時候仍靠 aos-loop＋aos-fsm，不是一支包了邏輯的程式；[thinking 10-23 agent 與 kernel](../../../thinking/2026-10/23/agent-kernel.md)）。

| 續檔 | 條號 |
|---|---|
| [01-續-C-22](01-續-C-22.md) | C-22 |
