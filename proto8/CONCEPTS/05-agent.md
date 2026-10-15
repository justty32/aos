← [回入口 CONCEPTS.md](../CONCEPTS.md)｜主題：**agent**｜概念：本檔｜規範：沒有專屬的條；agent 是用 fsm 組出來的（例：一份 agent.json），fsm 的概念與規範在基礎設施——[CONCEPTS § fsm](03-基礎設施.md#fsm)、[NORMS 組合子 § fsm](../NORMS/07-基礎設施-組合子.md#fsm)｜實作：思考介面與工具＝inst（實作慣例，還不是規範）在 [lib agent.md](../lib/agent.md)（現成格庫 `aos_agent_lib.py`：think／tool 兩格，不是 agent 本體，設定＝fsm 給的 stdin：fsm 設定本身＋`fsm_state`）；fsm 基礎實作在 [lib fsm.md](../lib/fsm.md)，同步版 demo 在 [demo/fsm](../demo/fsm/README.md)

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

- **C-46** agent 的使用＝函數＋binding：`agent_call(system, history, engine, tools)`；綁好就是 `agent_bob`，用時 `agent_bob.call(history, engine_args, tools_append)`。具體是一個 `bob/` 資料夾（定義：system、腦、工具、表），**呼叫時不變**，所以 bob 是可重複使用的函數。history 累積的地方（**frame**）是另一個參數，很像函數本體的 stack，可以跟實際的 cwd 不一樣。**tools＝函數的包裝**，對 call 來說是「傳進去、可供它使用的函數」（像高階函數的參數）；bob/ 裡綁的 tools 只是預設值；tools 裡可以是另一個 agent 的呼叫（agent 當工具＝呼叫一次 bob），所以能一層層組合。（10-15 使用者定，概念層；相對路徑是技術問題，規範慢慢來；[thinking 10-15 §11](../thinking/2026-10-15-topics/04-agent當函數.md#11-agent-當函數binding當工具)；實作 [lib agent.md](../lib/agent.md#agent-當函數當工具)）
