← [回入口 CONCEPTS.md](../CONCEPTS.md)｜主題：**agent**｜概念：本檔｜規範：agent 的一次一格與工具在 [NORMS 資料夾程式與執行](../NORMS/10-基礎設施-定義與工作區.md)（N-50、N-53）；慣例整套在 [CONVENTION](../CONVENTION.md)；agent 是用 fsm 組出來的（一個資料夾程式，C-50），fsm 的概念與規範在基礎設施——[CONCEPTS § fsm](03-基礎設施.md#fsm)、[NORMS 組合子 § fsm](../NORMS/07-基礎設施-組合子.md#fsm)｜實作：[impls](../impls/README.md)（10-23 起 C++ 是唯一實作；原指 Python 的 bin）、[demo](../demo/README.md)（agent-bob 叫 cathy 叫 stamp、agent-ann）；腦的工具呼叫（`tool_calls`）現無實作，見 [NORMS 待定](../NORMS/08-待定.md)〔10-23 有了：慣例 [P-41](../CONVENTION/02-題目stack停錯腦.md)、範本 [demo/agent-dan](../demo/README.md)〕

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

- **C-46** agent 的使用＝函數＋binding：`agent_call(system, history, engine, tools)`；綁好就是 `agent_bob`，用時 `agent_bob.call(history, engine_args, tools_append)`。具體是一個 `bob/` 資料夾（定義：system、腦、工具、表），**呼叫時不變**，所以 bob 是可重複使用的函數。history 累積的地方（**stack**）是另一個參數，很像函數本體的 stack〔10-23 落成 `$AOS_STACK/history.jsonl`，P-41〕。**tools＝函數的包裝**，對 call 來說是「傳進去、可供它使用的函數」（像高階函數的參數）；bob/ 裡綁的 tools 只是預設值；tools 裡可以是另一個 agent 的呼叫（agent 當工具＝呼叫一次 bob），所以能一層層組合。（10-15 使用者定，概念層；[thinking 10-15 §11](../thinking/2026-10-15-topics/04-agent當函數.md#11-agent-當函數binding當工具)）
  **10-16 改：agent 當函數是概念上的，不是形式上的**（10-15 收工後那套 frame 資料夾＋`frame.json`（`parent` 鏈）＋`args.json` 進、`ret.json` 出、「放同名檔＝綁定」不要了）。使用者：「我不喜歡 args.json／ret.json。我知道這是昨天我說『把 agent 當函數用』的直觀體現，但這極致體現了 AI 的蠢蛋之處。把 agent 當函數用，不是說形式上，而是在概念上，不要皮似神不似。我們現在就是把 JSON＋資料夾當 Lisp 的 list，這就是一個函數啊，何必再造一個體系？」（[稿 § 一](../thinking/2026-10-16-agent-inherit.md#一使用者原話10-16整理版)）**10-19 的意思**：**資料夾（程式）本身就是函數**（C-68；「Lisp 的 list」比喻 10-19 晚改用 table，C-71）；呼叫＝`aos-exec DIR [WS]`（10-21 起寫成 `aos-exec [--ws WS] XXX [args...]`，N-58）；資料夾（bob）呼叫時不變；**stack**（`$AOS_STACK`）就是函數的環境、像呼叫堆疊，狀態落在這裡，**放哪由呼叫方決定**（10-15 原話：「agent在呼叫時，可以選擇frame要放哪」仍成立；C-67）；這次的話放工作區（慣例 `new/`，P-11；10-23 改名，原 `inbox/`）；工具的地址與參數見 C-61。binding（這次換腦、加工具）現況是環境變數 `AOS_BRAIN_*`（P-23），呼叫方在叫它的那一行覆寫即可（P-39）。
  **10-15 深夜加嚴（C-52 徹底切割）**：agent 這層**只看到自己的工具清單**（名字、說明、參數），工具裡面在幹嘛——是不是另一個 agent、它的 stack 放哪、綁了什麼腦——agent 一概不管、不傳、不繼承；子 agent 只看自己的 stack、看不到呼叫方的（10-16 起沒有 `parent` 鏈）。要換子 agent 的腦，是叫它那一行的事（環境變數覆寫，P-39）（使用者：「agent他就是看到自己的工具，工具在幹嘛他就不管，拜託，乾淨，完全切割，徹底切割，不得有任何殘留。」）。
- **C-50** agent＝狀態機＋各狀態跑的 inst，複雜度集中在那些 inst（使用者：「agent基於狀態機，在某狀態下跑某個inst，所以複雜度主要集中在那些inst」）。「程式方面的實作可以擠在一坨，共用一些lib，但是在實際的資料夾布局和json那塊仍要保持單純」。（10-15 收工後意見 1～3，[thinking 意見 1～4](../thinking/2026-10-15-opinions-1-4.md)）
  **10-19 改**：**一個 agent 的定義＝一個資料夾**（C-68），入口 `_entry`（`$AOS_ENTRY`；10-19 晚改，原 `.aos/exec`；10-23 改名，原 `_exec`）；裡面的檔互相用相對路徑指、從這個資料夾算（起跑 cwd 就是它，N-59），不靠 `$ref`；檔少一點、把設定寫成一份大 JSON 也行（單子可內嵌，P-27）。agent 資料夾**可以帶 loop 當入口**（`aos-loop loop.json`，10-21 下午一度改成 `aos-loop --cfg loop.json`、傍晚改回 `aos-loop loop.json`，P-05、P-06；使用者 10-19，[ideas § 1](../thinking/2026-10-19-ideas.md)）。工具各是一個資料夾程式（C-61）。葉子程式（`date` 這類本來就是指令的）照舊用指令名；**資料夾程式之間互指不靠 PATH**（C-61）。
  **10-23 使用者：aos-agent 做成範本**（只產生標準 agent 資料夾，跑的時候仍靠 aos-loop＋aos-fsm，不是一支包了邏輯的程式；[thinking 10-23 agent 與 kernel](../thinking/2026-10-23-agent-kernel.md)）。

## agent 的工具（10-16 使用者定，10-19 改）

出處：[稿 § 四](../thinking/2026-10-16-agent-inherit.md#四使用者決定10-16)、[ideas § 4、§ 10](../thinking/2026-10-19-ideas.md)。名詞：資料夾程式、stack、小格、工作區，見 [CONCEPTS 基礎設施 § 資料夾程式、工作區與 stack](03-基礎設施.md#資料夾程式工作區與-stack10-19)。規範 N-50、N-53；慣例 P-11（題目與答案）、P-17（小格）、P-25、P-32、P-33（工具）。

- **C-61** **工具的地址不用 PATH**：工具是資料夾程式，放在呼叫它的那一格自己的資料夾裡（例 `act/tools/cathy/`），格裡寫 `aos-exec tools/<名>`——從自己 cwd 算的相對路徑、永遠零個 `..`（P-25、P-33），兩份定義一起搬也不斷；**工具一律做成資料夾程式**（`date` 這種也是），所以叫每個工具都做同一件事：給它一個小格（它自己的 stack，P-17）、`aos-exec` 它。工具裡是不是另一個 agent，呼叫的格不知道（C-52）。**工具的參數怎麼進（args、stdin、或 stack 裡的檔）由工具自己的說明定**，aos-exec 保證 args 與 stdin 原樣送到（P-26）。例外：aos 自己的指令（`aos-exec`、`aos-loop`、`aos-fsm`、`aos-inst`〔10-22 bin 版也刪了；10-23 整個 Python 版都刪了，只剩 impls 的 C++ 版〕；impls 線沒有 `aos-inst`，[ideas § 20](../thinking/2026-10-19-ideas.md)；loop／fsm 照 § 23 重寫／新做）入口裡直接寫指令名（N-59、P-39）——那是 aos 的指令，不是工具；**10-19 晚改：aos 的程式都不動 PATH**（原「由 aos-exec 把 `bin/` 放進 PATH」拿掉，使用者「也套用，都不動path吧」，[ideas § 24](../thinking/2026-10-19-ideas.md)），這些指令由呼叫者自己放進 PATH。PATH 其餘的只留給人在終端打指令。（使用者 10-16 夜：「可以不使用PATH嗎？」→ 看完提案：「好!」）〔10-23 註：腦可以叫的工具另有 `tool.json`（給模型看的說明），`arguments` 從 stdin 進、stdout 出，P-41〕

## agent 就是一台狀態機（10-16 使用者定）

- **C-62** **agent 的定義就是一台狀態機；這台狀態機怎麼跑、由誰跑，概念上都不管**（接 C-18、C-39）。aos 自己的 agent 怎麼跑是規範的事（[N-53](../NORMS/10-基礎設施-定義與工作區.md)：被外面的 loop 一次一次驅動）；別家的 agent（例 Claude Code）是一個行程持續跑，概念上同樣是 agent。（使用者 10-16：「agent的定義就是一個狀態機，至於這個狀態機怎麼跑、由誰跑，都無所謂。這是概念。但是我們的規範會說，為了讓agent方便審視自己，所以agent就是一個被人驅動的狀態機，需要外面有人用loop驅動他。這是我們的aos agent，至於我們常見的claude code，他們就是一個process持續執行，那是他們愛的。」，[KISS 重審拍板 4](../thinking/2026-10-16-kiss-recheck.md#使用者拍板10-16)）
