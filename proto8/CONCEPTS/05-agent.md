← [回入口 CONCEPTS.md](../CONCEPTS.md)｜主題：**agent**｜概念：本檔｜規範：沒有專屬的條；agent 是用 fsm 組出來的（一個定義資料夾，C-50），fsm 的概念與規範在基礎設施——[CONCEPTS § fsm](03-基礎設施.md#fsm)、[NORMS 組合子 § fsm](../NORMS/07-基礎設施-組合子.md#fsm)｜實作：思考介面與工具＝inst（實作慣例，還不是規範）在 [lib agent.md](../lib/agent.md)（現成格庫 `aos_agent_lib.py`；10-15 收工後的新布局已照 C-46／C-50 做好：定義資料夾＋frame、agent 當工具＝`sh -c` 三步，`aos_agent_call.py` 退場）；fsm 基礎實作在 [lib fsm.md](../lib/fsm.md)，同步版 demo 在 [demo/fsm](../demo/fsm/README.md)

# agent

使用者 10-15：「把 fsm 也跟 tasks 放一起」——agent 狀態機那幾條（C-18、C-25、C-39）跟著 fsm 移到[基礎設施](03-基礎設施.md#fsm)。

## 腦、工具、可預測性

- **C-19** agent 的簽名＝腦（模型）＋記憶（核心人格、近期記憶）＋手腳（工具）。（2.17）
- **C-20** agent 是複合型任務（外迴圈便宜、叫的模型與工具貴），所以要被排程；最核心的一題是「很多 agent 時誰先用腦」。（2.18、2.19）
- **C-21** 可預測性有主體性，不是任務的屬性，是觀察者的認識。（2.14、2.15）
- **C-22** 提高 agent 可預測性的方法：當 S 表示式拆開，能寫死的節點換成程式，降低走進不可預測節點的機率。（2.16）
- **C-22b** 可預測性不只是函式本身的：同一函式在不同狀況、不同（例如老舊）硬體上跑，可預測性不一樣。節點＝函式內部＋它所在的執行環境，合起來才是執行節點。（3g.13c）
- **C-23** agent 內部怎麼設計是後面的事，先把底打好。（2.20）
- **C-40** agent 要能當拋棄式函式用：引用一個設好的資料夾（標頭檔）、填幾個引數、讓它跑起來，執行環境在引用者這邊。library 做 binding 讓這件事簡單。（3g.9、3g.10）
- **C-42** 工具＝被引用的標頭檔；agent 也可以是工具；aos 體系的每一樣（daemon、tick、task、inst、kernel）都基於 inst、都是 shell 指令，所以都是 agent 的工具——自我迴圈改進的閉環。（3g.12、3g.13）

## agent＝函數＋binding

- **C-46** agent 的使用＝函數＋binding：`agent_call(system, history, engine, tools)`；綁好就是 `agent_bob`，用時 `agent_bob.call(history, engine_args, tools_append)`。具體是一個 `bob/` 資料夾（定義：system、腦、工具、表），**呼叫時不變**，所以 bob 是可重複使用的函數。history 累積的地方（**frame**）是另一個參數，很像函數本體的 stack。**tools＝函數的包裝**，對 call 來說是「傳進去、可供它使用的函數」（像高階函數的參數）；bob/ 裡綁的 tools 只是預設值；tools 裡可以是另一個 agent 的呼叫（agent 當工具＝呼叫一次 bob），所以能一層層組合。（10-15 使用者定，概念層；[thinking 10-15 §11](../thinking/2026-10-15-topics/04-agent當函數.md#11-agent-當函數binding當工具)）
  **10-15 收工後改（意見 3、4，[thinking 意見 1～4](../thinking/2026-10-15-opinions-1-4.md)）**：call／binding 不寫專用程式，用 json＋資料夾＋inst 做，照 Lisp 的環境來想。frame＝一個資料夾、就是被叫者跑的 cwd，**放哪由呼叫方決定**（使用者：「agent在呼叫時，可以選擇frame要放哪」）；呼叫方用 inst 的 `cwd` 指定，預設（可改）工具呼叫＝呼叫者 `work/<n>/` 新號碼資料夾、直接呼叫＝當下 cwd。frame 裡 `frame.json`（frame 資料夾的身分檔，原名 `env.json`；10-15 晚使用者「都按照推薦」改名，env 只留給環境變數，盤點 P2）的 `parent` 指回定義資料夾（上一層環境），`args.json`＝實引數，放同名的檔／資料夾＝綁定（history、腦、追加工具；tools 資料夾逐項合併＝追加＋同名蓋過，「整份取代」先不支援），`ret.json`＝回傳（錯＝N-29 形狀，沒有＝沒跑完）。找名字：先找 frame、找不到照 `parent` 往上找。被叫者走進 `end` 狀態時寫 ret.json 並停掉自己的 loop。
  **10-15 深夜加嚴（C-52 徹底切割）**：agent 這層**只看到自己的工具清單**（名字、說明、參數），工具裡面在幹嘛——是不是另一個 agent、它的 frame 放哪、綁了什麼腦——agent 一概不管、不傳、不繼承；frame 裡的綁定只到這一層（子 agent 沿自己的 `parent` 找、看不到呼叫方的 frame）。要換子 agent 的腦，是那張工具 inst 自己的事（使用者：「agent他就是看到自己的工具，工具在幹嘛他就不管，拜託，乾淨，完全切割，徹底切割，不得有任何殘留。」）。
- **C-50** agent＝狀態機＋各狀態跑的 inst，複雜度集中在那些 inst（使用者：「agent基於狀態機，在某狀態下跑某個inst，所以複雜度主要集中在那些inst」）。「程式方面的實作可以擠在一坨，共用一些lib，但是在實際的資料夾布局和json那塊仍要保持單純」：定義資料夾只放 fsm.json（表）、loop.json（怎麼拍）、每格一張 inst、預設的腦、系統提示、工具；資料夾是正本（單檔可互通，C-51）；葉子程式用指令名（在 PATH），不寫相對腳本路徑。（10-15 收工後意見 1～3，[thinking 意見 1～4](../thinking/2026-10-15-opinions-1-4.md)）
