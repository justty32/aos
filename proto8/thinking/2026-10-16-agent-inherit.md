# 2026-10-16 agent 的「擴張」與「當函數」：Lua 式繼承在 JSON inst 體系怎麼用、不造 args.json／ret.json

← [討論紀錄](README.md)｜前情：[inst-exec 第四版](2026-10-15-inst-exec-v4.md)（本稿改掉它「工具一律走 frame：args.json 進、ret.json 出」那段）、[意見 1～4](2026-10-15-opinions-1-4.md)（agent＝fsm＋inst、binding 用 json＋資料夾）、[topics/04 agent 當函數](2026-10-15-topics/04-agent當函數.md)、[同像性](2026-10-15-homoiconic.md)、[10-14 fsm 原話](2026-10-14-json-entry/06-fsm.md)（「像 C++ class 的繼承、函數可以被覆蓋」）｜概念：[C-46、C-50](../CONCEPTS/05-agent.md)、[C-34、C-36、C-49](../CONCEPTS/03-基礎設施.md)、[C-48、C-52、C-55、C-56](../CONCEPTS/01-設計理念.md)｜規範：[N-12、N-43](../NORMS/01-總則.md)、[N-27](../NORMS/03-基礎設施-inst.md)、[N-28、N-44](../NORMS/04-基礎設施-loop與daemon.md)、[N-36～N-40](../NORMS/07-基礎設施-組合子.md)、[N-45](../NORMS/06-基礎設施-命令列與指示詞.md)｜現況程式：[lib agent.md](../lib/agent.md)、[frame.md](../lib/frame.md)、[fsm.md](../lib/fsm.md)、[loop.md](../lib/loop.md)

> **這是 AI（Fable）的提案稿，還沒拍板。** 只有第一節是使用者的話；其餘都是提案，等使用者點頭才改概念、規範、程式。
>
> 注意：[KISS 彙整](2026-10-15-kiss/README.md)裡「都照推薦」那句，使用者 10-16 說是當時懶得想才說的、要重看；所以本稿**不把彙整當已定前提**，碰到時會標出來。第四版「工具一律走 frame（args.json 進、ret.json 出）」使用者 10-16 否定了（見第一節第 2 段）。
>
> **10-16 晚補**：使用者看完第二節後說他想的 Lua 繼承其實是「一手接一手的轉手鏈」（原話在 [§ 二之二](#二之二兩條路並排轉手鏈shebang-式vs-加-keylua-式10-16-晚補ai-提案)），並新定一條原則「寫什麼就做什麼、不埋暗規則」。二之二把兩條路並排比較，第二節 2.4（內建預設表）、2.5（沒寫 stdin 就餵整份）兩段照新原則**撤回**，拍板點已更新。

## 三分鐘看懂（只講現在要決定的三件事，其他都「之後再看」）

把 bob 想成一張食譜（定義）和一個廚房（工作區）。食譜永遠不改；每次下廚都在某個廚房裡，鍋碗（history、窗、work/）留在那個廚房。現在只要決定三件事：

1. **食譜怎麼寫**：推薦「一份 agent.json、長得就是一張 fsm 表，每一格把自己要的腦／工具／系統提示寫在格裡面」（丙）。另一條路是「七個小檔一手接一手」（甲，你 10-16 晚想的那個），它要先 cd 進食譜的資料夾才跑得動，所以鍋碗會留在食譜旁邊——就是你說的「怪」。
2. **怎麼叫 bob**：推薦 `echo '"幾點？"' | aos agent 廚房 食譜`——stdin 是這次的話、stdout 是它的回答、廚房是第一個引數（你說的 `WD TARGET`）。不造 args.json／ret.json，因為 stdin／stdout／cwd 本來就是這三樣。
3. **暗規則一律不要**：表要寫出來、每格的 stdin 要寫出來；程式不藏預設表、不替格偷塞東西。想省事就抄 lib 的範本檔或用 `$ref` 拆檔，那是看得見的。

這三件拍了，下面十幾個拍板點大多就跟著定了（它們只是把這三件事落到各條規範上）。其他——換腦怎麼寫、工具格怎麼跑、loop 放不放定義裡、WD 的三個邊緣——**之後再看**，推薦都寫在第三節，不急。

## 三分鐘看懂（二）：食譜裡的檔互相用相對路徑，站在廚房找不到——怎麼辦（10-16 夜）

你已經定了：stdin 只放食譜、這次的話放廚房。剩下一個卡點：食譜裡的檔互相指（inst.json → agent.json → tools.json）用相對路徑，站在廚房（/ws）就找不到。你不要大檔、不要 `$ref`、不要絕對路徑、不要編譯、不要暗規則。第五節找了四條路，只有兩條走得通，要你決定一件事：

1. **廚房裡放一條捷徑指向食譜**（推薦）：`aos-agent-init . ../agents/bob` 在廚房做一個 `.aos → /agents/bob/.aos` 的 symlink；食譜裡的檔一律寫 `.aos/agent.json`、`.aos/tools.json`，站在廚房就找得到。沒有新規則——「資料夾裡的 `.aos/` 放 inst.json」是 N-35 本來就有的，symlink 是檔案系統本來就有的（Plan 9 的 bind 最便宜的版本）。鬆掉的條件只有一個：aos-agent-init 會在廚房寫**一個**捷徑。
2. **用繼承來的檔案描述子當廚房的把手**（備案）：aos-exec 把廚房開成 fd 3，整串定義在 /agents/bob 裡一手接一手轉，碰廚房的地方寫 `/dev/fd/3/…`（跟你接受過的 `/dev/stdin` 同一類）。零新檔；但要改一條 inst 現行規矩（stdin 路徑從 aos-inst 站的地方算，像 shell 的重導）、aos-inst 不能關掉繼承的 fd，而且食譜裡會有一堆 `/dev/fd/3`。

其他兩條（每層各寫一次 cwd、環境變數）都在最後一格斷掉或要 `$env`，第五節有走一遍。**要決定的只有：捷徑（1）還是把手（2）。**

## 一、使用者原話（10-16，整理版）

1. **agent 用 aos-agent，JSON 裡內嵌 aos-fsm 的東西；想想 Lua 的物件導向**：「agent 那塊我有新想法：可以不純用 aos-fsm。就如同 aos loop 是 inst 的擴張——有點類似 Lua 的物件導向繼承方式——我們也可以用 aos-agent，那個 JSON 格式中就是內嵌 aos-fsm 的東西。Lua 的物件導向這塊請 Fable 思考一下，在我們這套 JSON inst 體系下可以怎麼應用。」
2. **不要 args.json／ret.json；agent 當函數是概念上的，不是形式上的**：「我不喜歡 args.json／ret.json。我知道這是昨天我說『把 agent 當函數用』的直觀體現，但這極致體現了 AI 的蠢蛋之處。把 agent 當函數用，不是說形式上，而是在概念上，不要皮似神不似。我們現在就是把 JSON＋資料夾當 Lisp 的 list，這就是一個函數啊，何必再造一個體系？」
3. **KISS 是最高原則，但也是最後原則**：「本質上是希望提出的設計在滿足各類需求和原則後，最後能回頭思考，把一些多餘的東西清掉。」（所以不能拿 KISS 當抄近路的理由：先把需求和其他原則滿足，最後才清。）

## 二、提案（AI，未拍板）

### 0. 一句話

**agent.json 就是一張 fsm.json 多三個 key（`brain`、`tools`、`system`）；`aos agent` 這支程式只做兩件小事：把 stdin 收進 history、把整份 agent.json 當每一格的 stdin（Lua 的 `self`），其餘全是 fsm。呼叫 agent＝`aos agent bob.json`：stdin 是這次的話、stdout 是它的回答、cwd 是它的 frame——這三樣 POSIX 本來就有，不用再造 args.json／ret.json。**

### 1. 先把需求攤開（KISS 是最後原則，所以先看要滿足什麼）

這些是概念層已經說過、本稿要全部接住的：

| 需求 | 出處 |
|---|---|
| 一個設好的 agent 可以重複用，呼叫時定義不變；執行環境在呼叫者這邊 | C-40、C-46 |
| 可以直接叫（人在命令列）、也可以當別的 agent 的工具（巢狀） | C-42、C-46 |
| 同一段對話可以續聊；也可以整段綁一份 history 進去 | C-46、意見 1～4 |
| 這次呼叫換腦、加工具（binding） | C-46 |
| 長壽的 agent（一直被求值）與用完即丟的 agent（跑完就結束）都要能寫 | C-39、C-40 |
| agent 這層只看到自己的工具清單，不知道工具裡是不是另一個 agent；什麼都不往下傳 | C-52 |
| 被殺一半可以重來 | N-38、N-20 |
| 定義是 JSON 正本、零指示詞也成立、不靠環境變數、少用 sh | C-50、N-45、user.md |
| 每層只說自己：結束碼 0／1，錯在 stderr 一種形狀 | N-43、N-29 |

### 2. A：Lua 那套在這裡是什麼

#### 2.1 Lua 的物件導向兩分鐘（比喻）

Lua 沒有 class 這個字，只有 **table**（一包 key→value，就是 JSON 物件）。所謂繼承是這樣做的：

- 一個 table 可以掛一張「找不到時去哪找」的小紙條（metatable 的 `__index`）。你問 `bob.brain`，bob 自己沒有 `brain` 這格，Lua 就照紙條去 `Agent` 這張 table 找；`Agent` 也沒有就再往上。這叫**委派**：自己沒有就問上面那個。
- `setmetatable(bob, {__index = Agent})` 就是「bob 掛到 Agent 底下」＝繼承。
- 方法也只是 table 裡的一格（值是函數）。`bob:think()` 就是「找 `think` 這格、找到了就跑」。子 table 自己寫一格同名的，就把上面的遮掉＝覆蓋。
- 重點：**找的動作是 Lua 執行器在做，不是 table 自己做**；table 只是資料。

#### 2.2 aos 現在已經有兩種「擴張」，先分清楚

使用者說「aos loop 是 inst 的擴張」，其實現況有兩種長相不同的擴張：

| | 包（has-a） | 加 key（is-a，格式超集） |
|---|---|---|
| 例子 | `loop.json` 裡有一格 `inst`，裝一張 inst | `daemon.json`＝`loop.json` 的所有 key 同義，再多 `children` 等（N-28） |
| 跑起來 | 外層是一支程式，內層是**另一支程式**（子行程） | **同一支程式家族**，daemon 的程式就是 loop 的程式加東西（`Daemon(Loop)`） |
| 一份合法的內層丟給外層能不能跑 | 不能（inst 不是 loop） | 能（loop.json 直接丟給 aos-daemon 也要能跑） |
| 像 Lua 的哪個 | 一個 table 的某格裝另一個 table | **`__index` 委派**：子表長得像父表多幾格，父表認得的 key 歸父表處理 |

Lua 的繼承是右邊那種。所以「aos-agent 的 JSON 內嵌 aos-fsm 的東西」我推薦走右邊：**agent.json 跟 fsm.json 是攤平的同一份，fsm 認得的 key（`start`、`states`、`end`、`state`）照 fsm 的意思，agent 多的三個 key（`brain`、`tools`、`system`）歸 agent**。不是 `{"fsm": {...}, "brain": ...}` 那種包一層。理由：
- C-48 本來就這樣說（json-families 使用者自己舉的例子：「agent.json 既是 fsm 表又放 brain／tools」）。
- 這跟 N-28 是同一招，體系裡只要記一次：**「某程式的 JSON＝它底下那支程式的 JSON 加幾個 key；同名 key 同義；預設值可以不同」**。

#### 2.3 Lua 的「找不到往上找」在 aos 有三個可能的落點，各自判

**落點 ①：格式層（key 的意思往上找）——採用。**
agent 認得的 key 自己處理，不認得的交給 fsm 的程式碼，fsm 也不認得的忽略（C-48）。「忽略」就是 Lua 找到底回 nil。這條鏈是**由程式的血統決定**（agent 的程式是 fsm 程式的子類，像 `Daemon(Loop)`），不是 JSON 裡寫一個 `__index`。所以 JSON 不多任何 key、N-45 零機制也成立。

**落點 ②：定義與呼叫之間（bob.json 是類、frame 是實例）——只留「狀態」那一半。**
Lua 的實例 table 一開始是空的，欄位都在類那邊找；寫東西才落在實例上。對應 aos：bob.json 是類（永遠不寫）、frame（cwd）是實例（history.json、state 窗都落在這）。這一半已經是 C-46、不用改。
但 Lua 實例還能**遮住**類的欄位（同名蓋過）。aos 以前靠這招做 binding：frame 放 `brain.json` 蓋過定義的腦（C-46「放同名檔＝綁定」、v4 的 F「cwd 的檔 ＞ stdin 定義」）。**本稿推薦拿掉這一半**：binding 改成「換一份 JSON」（見 2.5）。理由：定義歸 JSON、狀態歸資料夾，兩邊各一種東西，不要定義也能從資料夾來；而且 frame 查找鏈（`frame.json` 的 `parent`）v4 已決定退場，沒有鏈就沒有「往上找」。

**落點 ③：跑起來的巢狀層之間（內層格往外層找設定）——不採用。**
這是 C-52 明講不行的（「內層 fsm 不繼承外層設定」N-40、「什麼都不往下傳、不繼承」）。Lua 的鏈是**定義時**的事；aos 跑起來的每一層是各自的行程，層與層之間沒有鏈。一句話記：**繼承在寫 JSON 的時候、不在跑的時候。**

#### 2.4 誰負責找：程式，不是通則（**第二段「內建預設表」10-16 晚撤回**，見 § 二之二 5）

Lua 由執行器統一做 `__index`。aos 沒有執行器，每支程式就是自己那份 JSON 的解讀者。所以：
- **沒有共用的「找 key」通則**；`aos agent` 的程式自己做：先拿自己的三個 key，再把整份丟給 fsm 的程式碼（同一行程，像 daemon 重用 loop 的拍引擎）。
- 「預設值」也放在程式裡（Lua 的類 table 住在程式庫裡，不住在每個實例）：agent.json **沒寫 `states` 就用 `aos agent` 內建的那張表**（think ⇄ tool），沒寫 `state` 就用 `fsm/state.json`。這跟 N-28「同名 key 同義、預設值可不同；`inst` 在 daemon 選填、在 loop 必填」是同一回事。要自己的表就自己寫 `states`，寫了就蓋過（Lua 的覆蓋）。
  - 跟 N-36「表一定明寫」有沒有打架？沒有：fsm 的程式收到的永遠是明寫的表（agent 補上的）；fsm 從不猜。「明寫」的對象是 fsm，不是 agent 的作者。這是要拍板的（第三節 2）。

#### 2.5 Lua 的 `self`：每一格看到整份 agent.json（**「沒寫 stdin 就餵整份」10-16 晚撤回**，見 § 二之二 5；binding＝換一份 JSON 那段照留）

Lua 呼叫方法會把物件自己當第一個參數傳進去（`self`）。aos 的格是子行程，它的「參數」就是 stdin（N-12）。所以：**`aos agent` 把整份 agent.json 當每一格的 stdin**（格自己寫了 `stdin` 就照它的，不蓋）。think 從裡面拿 `brain`、`system`、`tools`，tool 格拿 `tools`，其他 key 不認就忽略（C-48）。
- 這不是「fsm 替格共用設定」（N-37 不准的那個）：是 **agent** 在把表交給 fsm 程式之前，先把自己這一層的東西填進自己這一層的格。fsm 的程式碼一樣不碰格的 stdin。
- 需要 inst 的 `stdin_inline`（v4 的 D，已定）把一份物件用管線餵進去，不落檔。
- binding（這次呼叫換腦）就是：**拿 bob.json 換掉 `brain` 這格，得到另一份 JSON，灌進去**。零機制、N-45 乾淨。嫌大 JSON 要重抄？那是指示詞（`$ref`）與資料夾當 object（C-51）的事：bob 拆成 `bob/brain.json`、`bob/tools/`、`bob/states.json`，新的那份只有 `brain` 不 `$ref`。設計本身只認「一份完整 JSON」。

#### 2.6 跟概念、規範對照

| 條 | 相容？ | 說明 |
|---|---|---|
| C-52 上層不知道下層、不繼承 | 相容 | 鏈只在定義裡（agent→fsm 的 key 意思），不跨行程；格（子行程）仍然只拿到 stdin、不往外找 |
| C-48 私有 key、值的雙形 | 就是它 | agent 的三個 key 是 fsm 格式上的私有 key；格的 `{"val", "next"}` 不動 |
| C-55 布局成長 | 相容、不相干 | C-55 是一個值往下長（純值→物件）；本稿是一份 JSON 往旁邊長（多 key）；bob.json 長大成 `bob/` 照 C-51／C-55 |
| N-28 daemon ⊇ loop | 同一招 | 體系裡第二個例子：agent ⊇ fsm。KISS 彙整 3.2 想把 N-28 翻掉（daemon 不繼承 loop）——若採本稿，**不要翻**，兩處同一招一次記住 |
| N-45 不靠指示詞 | 相容 | JSON 裡沒有 `extends`／`__index` 這種 key；拆檔才用 `$ref` |
| N-36／N-37 fsm 只管狀態→inst、不碰格 stdin | 相容 | fsm 程式碼不變；填 stdin 的是 agent，在 fsm 之前 |
| 10-14 拍板「fsm 不做繼承、沒有 extends、沒有搜尋路徑」 | 相容 | JSON 層仍沒有；繼承只在程式血統與預設值 |
| C-50「定義＝一張 inst（loop 包 fsm 包格）」 | **要改** | 定義＝一張 agent JSON（fsm 加三個 key），**不含 loop**；要反覆拍是呼叫方包 loop 的事（見 3.6） |
| C-46「放同名檔＝綁定」、v4 的 F | **要改** | binding＝另一份 JSON；資料夾只放狀態（history、窗、work） |

#### 2.7 例子：bob 一份 JSON（零指示詞）

```jsonc
// /agents/bob.json —— 一張 agent＝一張 fsm 多三個 key。fsm 的 key 沒寫＝用 aos agent 的預設（下面那段）
{
  "system": "你是 bob，會報時，也會叫畫筆備顏料。",
  "brain":  {"argv": ["aos", "brain", "openai", "--base-url", "http://localhost:4000/v1", "--model", "gpt-x"],
             "timeout_ms": 120000},
  "tools": {
    "clock": {"argv": ["clock"], "timeout_ms": 5000,
              "_tool": {"description": "報現在時間", "parameters": {"type": "object", "properties": {}}}},
    "brush": {"argv": ["aos", "agent", "/agents/brush.json"], "timeout_ms": 300000,
              "_tool": {"description": "叫畫筆（另一個 agent）備顏料",
                        "parameters": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]}}}
  }
}
```

跟 `aos agent` 內建預設攤在一起（＝不寫 `states` 時實際跑的那張；想改就自己寫這四個 key）：

```jsonc
{
  "start": "think", "state": "fsm/state.json", "end": ["done"],
  "states": {
    "think": {"argv": ["aos", "agent", "think"], "timeout_ms": 200000},            // 叫腦；有 tool_calls 回 {"next": "tool"}，否則 {"next": "done"}
    "tool":  {"val": {"argv": ["aos", "agent", "tool"], "timeout_ms": 600000}, "next": "think"}   // 跑工具、接 tool 訊息
  }
}
```

- 腦的設定走旗標（N-22 鏡射），**不要**像 v4 例子那樣用 `stdin_inline` 放腦的設定——腦的 stdin 要留給 think 餵的請求，兩樣會撞。
- `brush` 那格的 `argv` 裡有路徑 `/agents/brush.json`：這是**程式的引數**（跟 `clock` 寫指令名一樣是資料），不是 inst 體系的 TARGET key；為什麼得用路徑見 3.5。嫌路徑醜就把 brush 裝成指令（一個 shebang 檔 `brush`＝`aos agent /agents/brush.json`，放 PATH），`argv` 就寫 `["brush"]`——C-42「每樣都是 shell 指令」。
- 拆檔版（只是 `$ref` 便利、意思不變）：`bob/agent.json` 裡 `"brain": {"$ref": "brain.json"}`、`"tools": {"$ref": "tools.json"}`……`aos agent bob/` 照 N-35 的找法找 `bob/agent.json`。

### 3. B：agent 當函數——神，不是皮

#### 3.1 這套體系裡「呼叫」本來就是什麼

Lisp 的 `(bob "幾點")` 是一個 list（資料），丟給 eval 才算；算的時候有一個環境，算完回一個值。aos 對這三樣本來就各有一個東西：

| Lisp | aos 本來就有的 | 出處 |
|---|---|---|
| list（函數本體） | bob.json（或 `bob/`）：JSON＋資料夾就是 list | C-35、C-50 |
| eval | 跑它：`aos agent bob.json`；對資料夾求值＝執行這個資料夾 | C-34 |
| 傳參數 | 那支行程的 **stdin** | N-12 |
| 回傳值 | 那支行程的 **stdout**（結束碼輔助） | N-12 |
| 環境／stack frame | **cwd**：history、窗、work 都落在這；求值還回來的是一個正在變動的資料夾 | C-34、C-46 |

「皮」是什麼：把 `args.json`、`ret.json` 這兩個**名字像函數語法**的檔放進資料夾，等於在資料夾上畫「參數」「返回」兩個字。「神」是什麼：list 被求值、環境被改變、stdin 進 stdout 出——這些本來就在。所以本稿把 `args.json`、`ret.json`、`frame.json` 三個檔全拿掉，一個新檔都不造。

#### 3.2 agent 的三個通道：定義歸 JSON、狀態歸資料夾、這次的話走 stdin／stdout

- **定義**（bob.json）：永遠不寫。
- **狀態**（cwd＝frame）：`history.json`（對話）、`fsm/state.json`（走到哪一格）、`work/<n>/`（每次工具的工作資料夾）。這就是 C-39 說的「agent 是一條很長的 list，持續被求值」——list 裡會變的那幾個元素（context、記憶）住在資料夾裡；C-34 的「結果＝資料夾的變化」就是 history 長了一則。
- **這一次的輸入**：`aos agent` 的 **stdin**，一份 JSON；agent 把它當一則 user 訊息接進 history（字串照放、別的照 JSON 文字放）。空的 stdin＝沒有新話，從上次停的地方接著跑（被殺重來、長壽 agent 都用這個）。
- **這一次的輸出**：`aos agent` 的 **stdout**，一份 JSON＝最後一則 assistant 訊息（OpenAI 形狀，跟腦的 stdout 同形）。出錯＝stdout 沒東西、stderr 一份 N-29、退 1——「找不到結果＝沒有結果」（N-12），不用 `ret.json` 裡放 `{"error"}`。

所以**一個 agent 的簽名跟一顆腦長一樣**（訊息進、assistant 訊息出），只差它自己記 history。同像性稿說過「stdin／stdout 同一份 schema 的 inst 可以互換」——agent 跟腦在簽名上是同一類東西，這不是巧合，是 C-18「agent 是函式也是計算任務」。

#### 3.3 每一種用法怎麼自然成立

| 用法 | 怎麼寫 | 靠哪條 |
|---|---|---|
| 直接叫 | `cd workspace && echo '"幾點？"' \| aos agent /agents/bob.json` → stdout 一則回答；`workspace/history.json` 多兩則 | N-12、C-34 |
| 續聊 | 同一個 cwd 再叫一次、stdin 給新的話 | history 在 frame |
| 整段綁 history | 先把 `history.json` 放進 cwd 再叫（狀態本來就住資料夾） | C-46 |
| 這次換腦、加工具 | 換一份 JSON：bob.json 的 `brain`／`tools` 改掉再 `aos agent` 它 | 2.5 |
| 當工具（painter 叫 brush） | painter 的 `tools.brush`＝`{"argv": ["aos", "agent", "/agents/brush.json"]}`；tool 格對它跟對 clock 做一模一樣的事 | 3.4 |
| 巢狀的 history 放哪 | brush 跑在 painter 的 `work/<n>/`，所以 `work/<n>/history.json`——子 frame 住在父 frame 裡，像 stack 往上長；painter 不讀它（回答走 stdout 回來了） | C-46「frame 像 stack」、C-52 |
| 用完即丟 | `aos agent` 自己把 fsm 一拍一拍跑到 `end` 才結束；上限＝包它那張 inst 的 `timeout_ms`（一次呼叫一把尺） | C-40、Q13「深度靠各層 timeout_ms」 |
| 長壽 | `loop.json`＝`{"inst": {"argv": ["aos", "agent", "/agents/bob.json"]}, "times": null, …}`：每拍一趟、stdin 空、靠 idle 類的格去看信箱 | C-39、C-36 |
| 被殺一半 | 重跑 `aos agent`（stdin 空）：fsm 的 state 窗還在，從那格接著；冪等不保證 | N-38、N-20 |
| 每層只說自己 | agent 的 stdout 只有回答；fsm 每拍那行是 agent 內部的事、不往外吐；工具的 stderr 不讀 | N-43、C-52 |

#### 3.4 工具格：對每一張工具只做一件事

tool 格對 `tools` 裡每一張 inst：**在 `work/<n>/` 跑它，stdin＝模型給的 arguments（內嵌，不落檔），stdout 接起來、取最後一份當結果**，包成 tool 訊息回給模型。這就是 N-12，也是 N-27「子程式的參數走 stdin」的原意。
- 工具是 `clock`：stdin 是 `{}`、stdout 是時間。
- 工具是另一個 agent：stdin 是 `{"question": "備紅色"}`，`aos agent` 把它當 user 訊息，stdout 是 assistant 訊息。tool 格**完全不知道**這張跟 clock 有什麼不同（C-52）。
- `work/<n>/` 留著：它是工具的工作資料夾；工具若是 agent，它自動就是子 agent 的 frame——不用誰去「決定它是不是 frame」。

這跟 v4 的 G（「tool 格不碰工具的 stdin／stdout，只靠 args.json／ret.json」）相反，照使用者 10-16 的話改。

#### 3.5 `aos agent` 這支程式做什麼（全部；**10-16 晚改**：第 1 步的「補內建預設」與第 3 步整個拿掉，見 § 二之二 4、5——只剩讀 TARGET、收話、拍到 end、吐回答）

```
aos agent TARGET          # TARGET＝agent.json 或資料夾（找 agent.json，N-35 的找法）；cwd＝frame
  1. 讀 TARGET → 一份 dict；fsm 的四個 key 沒寫就補內建預設（2.4）
  2. stdin 有東西 → 當一則 user 訊息接進 cwd/history.json（先暫存再改名，N-05）
  3. 每一格沒寫 stdin 的 → stdin_inline＝整份 dict（self，2.5）
  4. 用 fsm 的程式碼一拍一拍跑（同一行程），直到走進 end；哪一拍出錯 → stderr 一份、退 1
  5. 把 history.json 最後一則 assistant 訊息吐到 stdout、退 0
```

為什麼定義要從 TARGET（路徑）來、不從 stdin 來：**stdin 要留給「這次的話」**。loop／fsm 的 stdin 是它們的設定，所以它們當不了「stdin＝問題」的函數——這就是 v4 被逼出 args.json 的根本原因。agent 要在 N-12 的意義上是一個函數，就得把定義從別的門送進來；不靠環境變數、不靠 cwd 放檔，只剩路徑這一扇門。這跟 `aos exec TARGET` 是同一類（人與上層會直接叫的入口才收 TARGET；`aos inst`／`loop`／`fsm` 只吃 stdin）。另一條路（乙）：stdin 收兩份 JSON、第一份是定義、第二份是話——定義就能內嵌進工具 inst，但 tool 格得知道「把 arguments 接在工具原本的 stdin 後面」，規則多一條，且使用者說過不要濫用內嵌。推薦甲（見第三節 5）。

#### 3.6 loop 不再是定義的一部分

v4 把 bob 寫成「inst(loop(fsm(格)))」：定義裡含 loop，靠 `stop_on_end`（N-44）讓 loop 看到 fsm 結束就停。本稿裡 agent 自己跑到 end，所以：
- 定義＝fsm 加三個 key，**不含 loop**。要不要反覆、隔多久，是呼叫方的事（它包一個 loop／daemon），跟 C-36「inst（求值一次）→ loop（持續求值）」的層次一致：agent 是「求值一次」那一層的東西。
- `stop_on_end` 沒有人用了（它是為 agent 定義資料夾的 loop.json 加的）→ 可以清（第四節）。

#### 3.7 格庫變成什麼

| 現在 | 提案 | 為什麼 |
|---|---|---|
| intake（args.json → history） | **消失**：`aos agent` 第 2 步 | 參數走 stdin |
| done（寫 ret.json） | **消失**：`aos agent` 第 5 步；`done` 只是 `end` 裡的一個名字 | 結果走 stdout |
| route（看有沒有 tool_calls） | **併進 think**：think 叫完腦直接回 `{"next": "tool"}` 或 `{"next": "done"}` | 少一格、少一拍 |
| think、tool | 留；設定從 stdin（self）拿，不再 `lookup()` cwd／parent | 2.5 |
| `aos agent fsm` 子命令、`aos_frame.py` 的 chain／lookup | **消失** | 沒有 parent 鏈 |
| `halt_after`／`halted` | 清：腦錯＝think 退 1、fsm phase 不動、agent 退 1；呼叫方要重試就再叫一次 | N-38、每層只說自己（這條 KISS 彙整 4.5 也是這樣推，這裡是獨立推出來的） |

### 4. KISS 最後回頭看：這樣設計之後，哪些變多餘

需求（第 1 節）全部接住之後，再看可以清掉的：

1. `args.json`、`ret.json`、`frame.json`（`parent` 鏈）、`aos_frame.py`、「cwd 同名檔蓋過定義」（v4 F）——四樣做的是同一件事（把東西從呼叫方傳給被叫方），stdin／stdout／cwd 已經在做。
2. intake、done、route 三格、`aos agent fsm` 子命令、think 的連錯計數。
3. N-44 `stop_on_end`（loop 不必再認得 fsm 的結束那行；loop 回到「只包一個 inst、跑幾次」）。
4. 五份一模一樣的 demo 表（fsm.json、cells/）：有內建預設表之後，demo 的 agent 各只剩 `brain`／`system`／`tools` 三個 key。
5. v4 批次 2 裡「工具一律走 frame」「children／格只收內嵌」那幾條要改寫；`stdin_inline` 留（self 要用）。
6. 留著不清的：`work/<n>/`（工具的工作資料夾，也是子 frame）、`_tool`、fsm 的 state 窗（被殺重來靠它）、N-28 的「格式超集」路數（本稿多用了一次）。

## 二之二、兩條路並排：轉手鏈（shebang 式）vs 加 key（Lua 式）（10-16 晚補，AI 提案）

### 0. 使用者原話（10-16 晚，整理版）

「Lua 繼承那塊，其實我是在想：好比說 `bob/inst.json` 是 `{"argv": ["aos-inst"], "stdin": "agent.json"}`，然後默認我們都先 `cd` 到 `bob/`，再 `cat inst.json | aos-inst`（這就是 aos-exec 語法糖的作用）。然後 `bob/agent.json` 也是一個 inst 格式：`{"argv": ["aos-inst"], "stdin": "agent-fsm.json"}`，那個 `agent-fsm.json` 又是另一個 inst 格式。至於怎麼讓 agent 的工作目標換成我們 `cd` 到 `bob/` 之前的資料夾，那就另外再說……感覺有點怪。」

同日新定的原則（C-56 補充）：「不要用這種方式添加規則，不直觀，這等同於埋雷。大家都預期『我給啥檔案，他就是往這個檔案塞東西』，你還要人家記『如果給的是這個檔案，那他會幹別的事情』，這太糟糕了。」——**寫什麼就做什麼；不拿暗規則去換少寫一個 key。**

### 1. 先把兩條路各自的 bob 寫出來（零指示詞）

**甲、轉手鏈**：每個檔都是一張 inst，只說兩件事——「用哪支程式跑我」（`argv`）、「我的內容在哪個檔」（`stdin`）。像 Unix 的 shebang（檔頭 `#!python3` 說「拿 python3 跑我」），一手接一手。使用者原話前兩環的 `argv` 都是 `aos-inst`，那是純轉手（只能改「怎麼跑」：`cwd`、`envs`、`timeout_ms`、串流）；要變成會跑的 bob，鏈底下總得接到 loop／fsm／格，所以完整長這樣：

```
/agents/bob/
  inst.json    {"argv": ["aos", "inst", "-"], "stdin": "agent.json", "timeout_ms": 600000}      ← 第一環（純轉手）
  agent.json   {"argv": ["aos", "loop", "-"], "stdin": "loop.json"}                               ← 第二環
  loop.json    {"inst": {"argv": ["aos", "fsm", "-"], "stdin": "fsm.json"},
                "times": 20, "stop_on_end": true, "ctl": "loop/ctl.json", "state": "loop/state.json"}
  fsm.json     {"start": "think", "state": "fsm/state.json", "end": ["done"],
                "states": {"think": {"argv": ["aos", "agent", "think"], "stdin": "think.json"},
                           "tool":  {"val": {"argv": ["aos", "agent", "tool"], "stdin": "tool.json"}, "next": "think"}}}
  think.json   {"system": "你是 bob…", "brain": {"argv": ["aos", "brain", "openai", "--model", "gpt-x"]},
                "tools": {"clock": {"argv": ["clock"], "_tool": {…}}}}
  tool.json    {"tools": {"clock": {"argv": ["clock"], "_tool": {…}}}}
```

叫它：`cd /agents/bob && cat inst.json | aos inst -`（＝`aos exec /agents/bob`）。所有相對路徑（`stdin: "agent.json"`、`stdin: "think.json"`、`loop/ctl.json`、`fsm/state.json`）都從 cwd 算，所以**一定要先 cd 進 bob/**；於是 history.json、work/、兩扇窗也落在 bob/ 裡。這次要問的話沒有地方放（最外層的 stdin 已經是設定），只能先在 bob/ 裡寫好 history.json 再跑。回答在 bob/history.json 最後一則；stdout 是最外層 aos-inst 的 N-30 結果（`{"code": 0, …}`），不是回答。

**乙、加 key**（第二節的寫法，一份 JSON；例子在 2.7）：agent.json＝fsm.json 多 `brain`／`tools`／`system` 三個 key，`aos agent` 把它們餵給格。叫它：`cd workspace && echo '"幾點？"' | aos agent /agents/bob.json`，回答在 stdout、資料落 workspace。

### 2. 並排比較

| 比什麼 | 甲 轉手鏈 | 乙 加 key |
|---|---|---|
| 定義長什麼樣 | 一個資料夾、七個小檔，每檔只說「拿誰跑、內容在哪」 | 一份 JSON（可用 `$ref` 拆成資料夾，意思不變） |
| 像哪種繼承 | **Lisp 的環境／Unix 的 shebang**：外層整份轉手給內層，只能改「怎麼跑」（cwd、timeout、串流），**不能部分蓋過內容** | **Lua 的 `__index`**：子表比父表多幾個 key，同名蓋過 |
| 換腦／加工具（部分蓋過） | 做不到「只改一格」：要嘛整個資料夾複製一份改 think.json；要嘛 `bob2/` 裡放新的 think.json、其餘用 symlink 指回 `bob/`（檔案系統替你做 `__index`，看得見、零 aos 機制；但使用者 10-15 說過 symlink＝「懶得 copy」） | 換一份 JSON（改 `brain` 那格）；嫌抄太長就 `$ref` 其餘部分 |
| 定義路徑 vs 資料路徑（cwd） | **混在一起**：`stdin: "think.json"`（定義）和 `state: "fsm/state.json"`（資料）都從 cwd 算，所以 cd 進 bob/ 之後工作就落在 bob/——使用者說的「怪」就是這個 | 分開：定義沒有任何執行期相對路徑（內容都在 JSON 裡），資料路徑從呼叫者 cwd 算；**不 cd** |
| 甲要「不 cd、在呼叫者 cwd 跑」得多什麼 | 三條路都不乾淨：(a) 定義檔的 `stdin` 寫絕對路徑——定義就不能搬家；(b) aos-exec 替你把路徑改絕對——它得猜哪個 `stdin` 是定義、哪個是資料（兩者長一樣），**這就是「給這個檔案它會幹別的事」的暗規則**，違反寫什麼就做什麼；(c) 環境變數——使用者不要 | 不用多任何東西 |
| 行程數（叫一次 bob 到腦） | exec → inst → inst → loop → inst → fsm → 格 → 腦，約 7 層（每多一環轉手多一支 aos-inst） | agent → 格 → 腦，3 層 |
| 結果怎麼回到呼叫者 | 走資料夾（C-34）：呼叫者讀 bob/history.json 最後一則；stdout 一層包一層都是 N-30 結果，要讓內層的話透出來得每層寫 `"stdout": "/dev/stdout"` | 走 stdout（N-12）：一份 assistant 訊息 |
| 訊號／逾時 | 每環一把尺，SIGTERM 一層轉一層（aos-inst 會轉給子程式），層多就慢 | 包它那張 inst 的 `timeout_ms` 一把尺；agent 收到 SIGTERM 收格 |
| 當別人的工具 | tool 格拿到的是最外層的 N-30 結果，不是回答；要拿回答得去讀子 frame 的 history.json＝tool 格得知道它是 agent → **撞 C-52** | tool 格對它跟對 clock 一樣（stdin 進、stdout 出） |
| C-52 每層只看自己 | 每環只看自己的 stdin 檔 ✓；但「結果走資料夾」讓呼叫者得伸手進被叫者的 frame ✗ | ✓ |
| N-12 stdin＝參數、stdout＝結果 | 最外層 stdin 是設定、stdout 是 N-30——bob 這個「函數」的參數與結果都不在 stdio 上 ✗ | ✓ |
| N-45 零指示詞 | ✓（全是執行期路徑，沒有 `$ref`） | ✓（`$ref` 只是拆檔） |
| C-56 寫什麼就做什麼 | 每條路徑都是字面的 ✓；只有 aos-exec「默認 cd」是一個要記的動作，而且記了之後「工作落在定義資料夾」還是會讓人意外 | 2.4「沒寫 `states` 就用內建表」、2.5「沒寫 `stdin` 就餵整份」**兩條都是暗規則 ✗**（下面 5 撤回） |
| KISS 最後回頭看 | 七個檔、七層行程做一件事；`stop_on_end` 還是要 | 一份 JSON、一支邊界程式；但原稿多了兩條暗規則要清 |

### 3. 甲為什麼「感覺有點怪」——一句話

Unix 的程式是**用 PATH 找到、在呼叫者的 cwd 跑、靠「自己在哪」找自己的附屬檔**。甲把「自己在哪」和「在哪工作」綁成同一個 cwd，所以不是定義跑進工作區、就是工作落進定義區。要拆開這兩件事，aos 只有兩條不埋雷的路：定義路徑寫絕對（定義不能搬），或**定義裡根本沒有執行期路徑**（內容直接在 JSON 裡）。後者就是第四版「JSON 是正本」與 N-45 的立場：把甲的每個 `stdin: "x.json"` 換成 `stdin_inline`＋內容，鏈就攤成一份 JSON——**甲攤平之後就是乙的資料形**。兩條路不是對立，是同一份東西的「拆檔用執行期路徑」vs「拆檔用載入期 `$ref`」；差別只在前者要 cd、後者不用。

### 4. 第三種：把兩邊合起來（推薦）

拿甲的「每個檔只說拿誰跑、內容在哪」當**邊界**（只留一環：`aos agent` 這支程式），拿乙的「內容在 JSON 裡、不 cd」當**定義**，而且照新原則把乙的兩條暗規則拿掉：

```jsonc
// /agents/bob/agent.json —— 就是一張 fsm.json，零 agent 級私有 key；每格的 stdin 自己寫、寫在裡面
{"start": "think", "state": "fsm/state.json", "end": ["done"],
 "states": {
   "think": {"argv": ["aos", "agent", "think"], "timeout_ms": 200000, "stdin_inline": true,
             "stdin": {"system": "你是 bob，會報時，也會叫畫筆備顏料。",
                       "brain":  {"argv": ["aos", "brain", "openai", "--base-url", "http://localhost:4000/v1", "--model", "gpt-x"]},
                       "tools":  {"clock": {"argv": ["clock"], "timeout_ms": 5000, "_tool": {…}},
                                  "brush": {"argv": ["aos", "agent", "/agents/brush"], "timeout_ms": 300000, "_tool": {…}}}}},
   "tool":  {"val": {"argv": ["aos", "agent", "tool"], "timeout_ms": 600000, "stdin_inline": true,
                     "stdin": {"tools": {"clock": {…同上…}, "brush": {…同上…}}}},
             "next": "think"}}}
```

- **同一份檔兩支程式都能跑**：`aos fsm /agents/bob/agent.json` 跑一拍（純狀態機）；`aos agent /agents/bob/agent.json` 把它當函數跑（stdin 收話 → 接進 history → 一拍一拍到 `end` → 最後一則 assistant 訊息吐 stdout）。這就是 N-28「loop.json 丟給 daemon 也能跑」那招，只是這次**一個 key 都沒多**。
- **沒有暗規則**：表要寫、每格的 stdin 要寫；`aos agent` 不藏預設表、不替格補 stdin。`tools` 在 think 與 tool 兩格各寫一次（第四版 N 本來就定「照寫兩次」）；要共用就拆檔：`"stdin": {"$ref": "think.json"}`、`"tools": {"$ref": "tools.json"}`——載入時從檔所在資料夾攤平、攤完零路徑，所以**不 cd**，資料落呼叫者 cwd。
- **部分蓋過**＝換一份 JSON（抄一份改 `brain`）；用 `$ref` 拆檔的話只抄 think.json 那一小塊。沒有 symlink、沒有鏈。
- **aos-exec 不 cd**（跟第四版一樣）；甲那種「默認 cd 進定義資料夾」不做。要在定義資料夾裡工作，人自己 cd。
- 其餘照第三節：stdin＝話、stdout＝回答、cwd＝frame、工具格只做 stdin／stdout／`work/<n>/`、agent 自己跑到 end、定義不含 loop。

跟甲比：少六支轉手行程、結果走 stdout、不 cd、當工具不撞 C-52。跟乙比：少兩條暗規則、少三個 agent 級 key、`aos_agent` 程式更薄（只剩收話、拍到 end、吐回答）。代價：think 與 tool 兩格的 `tools` 要寫兩次（或 `$ref`）。

### 5. 回應頂層的兩個疑點（照「寫什麼就做什麼」重看）

- **原拍板點 2「表沒寫＝程式內建整張預設表」→ 撤回，改成「表一定寫」。** 讀 bob.json 看不出它會跑哪些狀態，就是埋雷。要省事的辦法是 lib 放一份範本 `agent.json`，複製去改、或 `$ref` 它的 `states`——範本是檔案、看得見，不是程式裡藏的預設。
- **原拍板點 7「格沒寫 stdin＝自動餵整份 agent.json」→ 撤回，改成「每格的 stdin 自己寫」。** 「沒寫 stdin 平常是 /dev/null、在 agent 裡卻變成整份定義」正是「同一個 key 在不同地方幹不同事」。跟著撤的是 agent 級的三個 key `brain`／`tools`／`system`：它們存在的理由就是要靠那條暗規則送進格裡；拿掉暗規則它們就沒事做，內容直接寫在格的 stdin 裡（第四版 N 的寫法）。
- 順手照同一把尺再看原稿其餘各點：拍板點 10（stdin 一份 JSON＝user 訊息內容，字串照放、別的照 JSON 文字放）是一條寫明的規則、同一個輸入永遠同一種處理，不算暗規則，維持；拍板點 6（空 stdin＝沒新話、接著跑）也是寫明的一條，維持。

## 二之三、`aos-exec WD TARGET`（10-16 晚再補，AI 提案）

### 0. 使用者原話（10-16 晚，整理版）

「其實 aos-exec 我覺得可以用另一個使用方式：`aos-exec WD TARGET`，也就是 `aos-exec . bob/`。」（頂層攤了三個邊緣：定義裡的相對路徑從哪算、WD 跟 inst 自己的 `cwd` 撞了聽誰的、WD 必不必填；使用者「好」。）

### 1. 它在說什麼

兩個引數就是兩件事：**WD＝在哪工作（廚房）、TARGET＝定義在哪（食譜）**。這正好把二之二說的「怪」拆開——甲的毛病是定義路徑與資料路徑共用一個 cwd；WD 把「在哪工作」明寫成引數，就不必靠 cd、也不必靠環境變數。寫什麼就做什麼：`aos exec . bob/`＝「站在 `.`，跑 bob/ 這份定義」。

### 2. 跟丙合起來（推薦的組合）

丙的定義裡沒有任何執行期相對路徑（格的內容都在 JSON 裡），所以 WD 只有一個意思：資料落哪。同一個 bob：

```
/agents/bob/agent.json          ← 二之二 4 那份（一張 fsm 形狀的 agent.json，零指示詞、零執行期路徑）
~/ws/                           ← 廚房；空的，或已經有上次的 history.json

$ cd 隨便哪裡
$ echo '"幾點？"' | aos agent ~/ws /agents/bob        # 入口都同一形：WD TARGET；TARGET 是資料夾就找 agent.json
{"role": "assistant", "content": "三點整。"}           # stdout＝回答

~/ws/history.json  ~/ws/fsm/state.json  ~/ws/work/1/   # 資料全落 WD；/agents/bob/ 一個字都沒動
```

- painter 把 brush 當工具：`"brush": {"argv": ["aos", "agent", ".", "/agents/brush"], "_tool": {…}}`——WD 寫 `.`，就是 tool 格給它的 `work/<n>/`（子 frame）。工具格仍然不知道這是 agent。
- 一般的 inst 走 `aos exec WD TARGET`：讀 TARGET 那張 inst（檔或資料夾找 inst.json），站在 WD 跑。
- 所以「凡是收 TARGET 的入口（`aos exec`、`aos agent`）都長 `WD TARGET`」，一次記住；`aos inst`／`loop`／`fsm` 照第四版只吃 stdin、沒有引數。

### 3. 跟甲合起來會怎樣

```
$ aos exec ~/ws /agents/bob
  → 讀 /agents/bob/inst.json＝{"argv": ["aos", "inst", "-"], "stdin": "agent.json"}
  → 站在 ~/ws 跑它 → 第二環 aos-inst 從 ~/ws 找 agent.json → 找不到，斷在第二環
```

WD 只救得了 aos-exec 親手讀的**那一張**；第二環起每支程式都是從 pipe 收到設定、不知道「定義檔在哪」，只知道自己站在 WD。要讓甲在 WD 跑得動，只剩一條路：**定義檔之間互指的路徑全部寫絕對**（`"stdin": "/agents/bob/agent.json"`、`"stdin": "/agents/bob/think.json"`…），資料路徑（`loop/ctl.json`、`fsm/state.json`、`work/`）維持相對→落在 WD。這樣能跑、鍋碗也會留在廚房，但食譜搬家就全壞，而且七層行程、結果不在 stdout、當工具撞 C-52 那三樣都還在。所以 WD 跟丙是天生一對，跟甲只是勉強湊合。

### 4. 三個邊緣：選項、推薦、後果

**(1) 定義裡的相對路徑從哪算**
- A. **一律從 WD 算**（跟 aos-inst 現在的規矩一樣：`cwd`、`stdin`、`stdout` 都從它站的地方算）。定義要指自己旁邊的檔，就寫絕對路徑、或內嵌、或用 `$ref` 在載入時攤平（`$ref` 本來就從檔所在算，是已有的糖）。**推薦 A**：零新規則；丙完全合；甲要寫絕對（它本來就有這個問題）。
- B. 從定義檔所在算：aos-exec 讀到那張 JSON 後把相對路徑接上 TARGET 的資料夾再交出去。問題：`stdin: "think.json"`（定義）和 `stdout: "loop/state.json"`（資料）長一模一樣，aos-exec 得規定「哪些 key 算定義」——**暗規則**，而且只救第一環。不推薦。
- C. 兩種路徑用不同寫法明寫（例如定義路徑另加記號）：等於自己發明一個小指示詞，N-45 說設計不靠它。不推薦；要拆檔用 `$ref` 就夠。
- 後果（選 A）：規範只要一句「aos-exec／aos agent 站在 WD 跑，路徑規矩照 aos-inst」。

**(2) WD 跟 inst 自己的 `cwd` 撞了**
- (a) WD 蓋過 inst 的 `cwd`：寫了的 key 被默默忽略，違反寫什麼就做什麼。
- (b) 兩個都寫＝報錯：多一條錯誤路徑，而且這個情況本來有自然的意思。
- (c) **inst 的 `cwd` 從 WD 往下算**：WD 是「我站哪」，inst 的 `cwd` 是「從這裡再走到哪」——跟 aos-inst 現行「`cwd` 從呼叫者的 cwd 算」一字不差。**推薦 (c)**：零新規則。後果：寫 `aos exec ~/ws bob/`、bob 的 inst 又寫 `"cwd": "sub"`，就在 `~/ws/sub` 跑；絕對的 `cwd` 照舊是絕對。

**(3) WD 必不必填**
- 必填：`aos exec . bob/` 多打兩個字；不會有「`aos exec bob/` 的 bob/ 到底是 WD 還是 TARGET」的歧義；寫什麼就做什麼。**推薦必填**。
- 選填、預設 `.`：省兩個字，換一條「一個引數時它是 TARGET」的規則。不推薦。
- 後果：第四版「`aos-exec TARGET` 必填（A）」改成「`aos-exec WD TARGET` 兩個都必填」；`aos agent` 同形。

### 5. 一句話

WD 讓「不 cd、在呼叫者的廚房工作」有了一個明寫的位置，正好補上甲缺的那一塊；但它只管 aos-exec 親手讀的那一張，定義裡若還有執行期相對路徑（甲的鏈），第二環起還是斷——所以 WD 跟「定義裡沒有執行期路徑」（丙）要一起選。

## 三、要使用者拍板的點（每點一句＋推薦＋理由＋後果；10-16 晚更新，含 WD）

1. **三條路選一條**：甲 轉手鏈（cd 進 bob/、七個檔一手接一手）／乙 加 key（一份 JSON 加三個 agent 級 key＋兩條暗規則）／丙 合起來（agent.json＝一張 fsm、每格 stdin 寫在裡面、`aos agent` 只當邊界）。**推薦：丙。** 理由：不 cd、結果走 stdout、當工具不撞 C-52、零暗規則；甲攤平之後本來就是丙的資料形。後果：C-50 改成「定義＝一張 agent.json（fsm 形狀），不含 loop」；KISS 彙整 3.2（daemon 不繼承 loop）不必照做，N-28 那招留著（丙是它的第二個例子）。
2. **表一定寫、每格 stdin 一定寫；程式不藏預設表、不替格補 stdin**（原 2、7 兩點撤回）。**推薦：是。** 理由：寫什麼就做什麼。後果：lib 放一份範本 agent.json 給人抄或 `$ref`；agent 級 `brain`／`tools`／`system` 三個 key 不要了；think／tool 兩格的 `tools` 寫兩次或 `$ref`。
3. **binding＝另一份 JSON；拿掉「資料夾放同名檔蓋過定義」與 parent 鏈**；資料夾只放狀態（history、窗、work）。**推薦：拿掉。** 理由：定義一種來源、狀態一種住處；N-45 零機制也成立。若選甲則替代＝symlink 資料夾。後果：C-46「放同名檔＝綁定」改成「換一份 JSON」；`aos_frame.py` 刪。
4. **參數與結果：拿掉 args.json／ret.json；`aos agent` stdin＝這次的話（一份 JSON 當 user 訊息內容）、stdout＝最後一則 assistant 訊息、cwd＝frame。** **推薦：是。** 理由：使用者 10-16 原話；N-12＋C-34 本來就有；甲做不到這點（最外層 stdin 是設定）。後果：C-46、N-27 第二句改字；v4 的 G 作廢；agent 跟腦同簽名。
5. **定義怎麼給 `aos agent`**：`aos agent WD TARGET`（路徑；stdin 留給話；agent 可裝成指令）／stdin 兩份（定義、話）。**推薦：WD TARGET。** 理由：stdin 一個意思；跟 `aos exec` 同形一次記住；工具 inst 的 argv 寫 `".", "/agents/brush"` 跟 `clock` 一樣是資料。後果：v4「TARGET 這東西都拿掉」多一個例外（跟 aos-exec 同類）；工具若是 agent 得用路徑或裝成指令。
6. **aos-exec 不默認 cd 進定義資料夾；要站哪用 WD 明寫**（`aos exec WD TARGET`，兩個都必填）。**推薦：是。** 理由：寫什麼就做什麼；定義與工作區分開。後果：第四版 A「`aos-exec TARGET` 必填」改成兩個引數都必填；要在定義資料夾裡工作就寫 `aos exec bob/ bob/`。
7. **agent 自己跑到 `end` 才結束、上限只靠包它那張 inst 的 `timeout_ms`；定義不含 loop，長壽＝呼叫方包 loop。** **推薦：是。** 理由：C-40 用完即丟、C-36 的層次；一次呼叫一把尺。後果：N-44 `stop_on_end` 可刪；C-50「怎麼拍（loop）」那半句刪。
8. **tool 格對每張工具只做「cwd＝work/<n>/、stdin＝arguments、stdout 最後一份＝結果」**；agent 當工具＝`{"argv": ["aos", "agent", "/路徑"]}` 或裝成指令。**推薦：是。** 理由：N-12、N-27 原意；C-52 徹底不知道工具裡是什麼。後果：v4 G、KISS 2.7 改寫；三張 `sh -c` 工具 inst 改成一行 argv，`AOS_DEMO` 可退場。
9. **格庫瘦身：intake／done／route 消失，think 自己回 next，`aos agent fsm` 刪，連錯計數刪。** **推薦：是。** 理由：這些格做的事要麼進了 `aos agent` 的兩步，要麼跟「每層只說自己」重複。後果：agent.md、agent_lib.md、frame.md 三份併成一份。
10. **輸入的形狀**：stdin 一份 JSON＝user 訊息的內容（字串照放、物件照 JSON 文字放），不收整則訊息物件；空 stdin＝沒新話、接著跑；要綁整段對話就放 history.json。**推薦：是（一條寫明的規則）。** 替代＝也認 `{"role", "content"}` 整則訊息（多一形）。後果：模型給工具的 arguments（物件）直接就是子 agent 的輸入，不用轉。
11. **定義裡的相對路徑一律從 WD 算**（照 aos-inst 現行規矩；定義要指自己旁邊的檔＝絕對路徑、內嵌、或 `$ref` 載入時攤平）。**推薦：是（二之三 4 的 A）。** 理由：零新規則；B「從定義檔所在算」要分哪些 key 是定義＝暗規則。後果：甲若要在 WD 跑，定義檔互指全寫絕對。
12. **inst 自己的 `cwd` 從 WD 往下算**（不是 WD 蓋過、不是報錯）。**推薦：是（二之三 4 的 (c)）。** 理由：跟「`cwd` 從呼叫者的 cwd 算」一字不差。後果：無新規則。
13. **WD 必填**（不設預設 `.`）。**推薦：必填。** 理由：少一條「一個引數時它是 TARGET」的規則、沒有歧義。後果：多打兩個字。
14. **食譜裡的相對路徑怎麼在廚房成立**：A 廚房掛捷徑 `.aos → 食譜`（食譜自稱 `.aos/x`；`aos-agent-init` 寫一條捷徑）／B 廚房開成 fd 3、碰廚房寫 `/dev/fd/3/…`（改 inst 串流路徑規矩、不關 fd）。**推薦：A（第五節）。** 後果：aos-agent-init 糖；食譜收進 `.aos/`；v4「aos-exec 不寫檔」鬆一格。
15. **agent 之間怎麼互指**（painter 的工具是 brush）：裝成 PATH 上的指令 stub（位置只在 stub 裡）vs 食譜裡寫相對位置。**推薦：stub（C-50 葉子用指令名的延伸）。** 之後再看。

## 四、使用者決定（10-16）

- 正規參數入口是 stdin，`aos agent 路徑`、`aos-exec WD TARGET` 這類 argv 寫法都是語法糖（使用者：「argv:[aos,agent,agents/brush]，其實，我一直覺得argv這塊的用法...就像我早期說的，正規參數入口就是stdin，像是aos-exec WD TARGET這個用法是語法糖...」）。
- **agent 的 stdin 只放一份，這份是食譜（定義）**（使用者：「stdin只放一份，這份要食譜。」）。「這次的話」放哪還沒定。
- **「這次的話」放在廚房（工作區）裡，使用時指定廚房的位置**；以後可能做類似 aos-exec 的語法糖，例如 `aos-agent-say`、`aos-agent-init`（使用者：「放在廚房裡，然後使用的時候指定廚房的位置。以後可能會做類似aos-exec那樣的語法糖，比如aos-agent-say, aos-agent-init...」）。

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

要過的關：寫什麼就做什麼（C-56 補充）、零指示詞（N-45）、零絕對路徑、不編譯、每層只管自己（C-52）、少用 sh、stdin 是正規入口（N-12）、stdin 只放食譜（四）。

### 2. 卡點的本質（一句）

在最後真正幹活的那一格（think／tool），**同時**需要兩個地方：食譜（讀 tools.json）和廚房（寫 history、開 work/）。一個行程只有一個 cwd，所以這兩個地方裡一定有一個要靠**別的東西**指到——不是路徑（否決了），就只能是檔案系統或行程本來就有的機制：捷徑（symlink／bind）、繼承的檔案描述子、環境變數。下面四條各走一遍。

### 3. 候選 A：廚房裡掛一條捷徑指向食譜（symlink＝最便宜的 Plan 9 bind）

N-35 本來就說：TARGET 是資料夾時先找 `<資料夾>/.aos/inst.json`。所以把**廚房**當 TARGET，廚房的 `.aos/` 就是食譜——用一條捷徑掛進來：

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

- 每一層都站在廚房；食譜裡**所有**互指都寫 `.aos/x`，從廚房算，剛好對上。沒有任何 key 被賦予第二種意思；`.aos/` 這個名字是 N-35 已有的，捷徑是 `ln -s`。
- prompt 怎麼進 history：intake 格的 stdin 就是 `prompt.json`（N-12：話走 stdin），接進 cwd 的 history.json。回答怎麼回終端：留在廚房 history.json（四：話放廚房；C-34：結果＝資料夾的變化）；aos-exec 的 stdout 只是 N-30。
- 在食譜自己的資料夾裡跑也成立：`cd /agents/bob && aos-exec . .`——bob/ 自己就有 `.aos/`，不用捷徑（這就是使用者原本「cd 到 bob/」的那個預設，只是把定義收進 `.aos/`）。
- 同一份食譜、兩個廚房同時跑：兩條捷徑指同一處，互不相干。
- 子 agent 當工具：tool 格開 `work/<n>/`，brush 的工具 inst＝`{"argv": ["aos-agent-init", ".", "<brush 在哪>"]…}` 得先掛再跑——「brush 在哪」又是一個位置。Unix 的答案是 **PATH**：把 brush 裝成一個指令（一個 stub `brush`＝`aos-agent-init . /agents/brush && aos-exec . .`），工具 inst 寫 `["brush"]`，跟 `date` 一樣；位置只寫在 stub 裡（安裝品，不在食譜裡）。這是 C-50「葉子用指令名」的延伸，另拍。
- **鬆掉的條件**：aos-agent-init 會往廚房寫一條捷徑（v4「aos-exec 不寫檔」鬆一格；使用者自己已預告 init 糖）。食譜自稱 `.aos/`——是看得見的慣例，不是暗規則；建議食譜裡直接寫 `.aos`、不跟 `AOS_DIRNAME` 變。
- 跟 C-30／C-51 的關係：「空間可以掛進外部東西、像 Plan 9」——symlink 就是最小的 bind。跟 C-36「node＝loop 服務的資料夾」、C-39「agent 是一個資料夾」對得上：**廚房就是 agent 這個 node，`.aos/` 是它的食譜。**

### 4. 候選 B：繼承的檔案描述子當廚房的把手（`/dev/fd/3`）

整串定義在 /agents/bob 裡一手接一手轉（相對路徑自然成立），廚房由 aos-exec 開成 fd 3 傳下去，碰廚房的地方寫把手：

```
/agents/bob/
  inst.json    {"argv": ["aos", "agent", "-"], "stdin": "agent.json"}
  agent.json   {"start": "intake", "state": "/dev/fd/3/fsm/state.json", "end": ["done"],
                "states": {
                  "intake": {"val": {"argv": ["aos", "agent", "intake"], "cwd": "/dev/fd/3", "stdin": "/dev/fd/3/prompt.json"}, "next": "think"},
                  "think":  {"argv": ["aos", "agent", "think"], "cwd": "/dev/fd/3", "stdin": "tools.json", "timeout_ms": 200000},
                  "tool":   {"val": {"argv": ["aos", "agent", "tool"], "cwd": "/dev/fd/3", "stdin": "tools.json"}, "next": "think"}}}
  tools.json   同上

$ cd /ws && aos-exec . ../agents/bob      # ＝ (cd /agents/bob && aos inst - < inst.json) 3< /ws   ：把廚房開成 fd 3、站在食譜跑
```

- 每一層都站在食譜；fd 3 是 Unix 預設會繼承的（像 stdin），不用傳、不用寫；要進廚房的格寫 `"cwd": "/dev/fd/3"`，要碰廚房檔案的寫 `/dev/fd/3/…`。`/dev/fd/3` 不是地址、是把手，跟已接受的 `/dev/stdin` 同類；廚房搬去哪都一樣。
- think 格同時要 `stdin: "tools.json"`（食譜）和 `cwd: /dev/fd/3`（廚房）：這要求 **stdin 路徑從 aos-inst 站的地方算、`cwd` 只給子程式**——也就是 shell 的規矩（`(cd d && prog) < f`，重導在父層開好才換目錄）。inst 現行是「串流從解出來的 cwd 算」，要改這一條。
- **鬆掉的條件**：改 inst 一條現行規矩（上面那條）；aos-inst／loop／fsm 起子程式時不關掉繼承的 fd（Python 預設會關，程式要改）；食譜裡每個碰廚房的地方都多一截 `/dev/fd/3`；Linux 的 `/proc` 魔法（本機 WSL2 沒問題）。零新檔、零捷徑。
- 子 agent 當工具：brush 的 stub 一樣（`aos-exec . /agents/brush` 開 work/<n>/ 當 fd 3）。

### 5. 候選 C：每層各寫一次 `cwd`／aos-exec 用 `--cwd` 旗標——在最後一格斷

`aos-exec . ../agents/bob`＝`cd /agents/bob && aos inst --cwd /ws - < inst.json`（N-22 鏡射旗標是現成的）：頂層 inst 站在食譜讀 agent.json、進廚房跑 `aos agent -`。到這裡都好。但 aos-agent 站在廚房起 think 格，格的 `"stdin": "tools.json"` 從廚房算→找不到；寫 `"cwd": "../agents/bob"`？那是把廚房到食譜的相對位置寫死，跟絕對路徑一樣。**最後那一格同時要兩個地方，單靠 cwd 給不了。**（這也是二之三「WD 只救 aos-exec 親手讀的那一張」的另一種說法。）

### 6. 候選 D：環境變數——要 `$env`

`AOS_KITCHEN=/ws` 傳下去，格要用就 `"cwd": {"$env": "AOS_KITCHEN"}`——指示詞，N-45 不靠它；讓格庫程式自己讀環境變數＝暗規則。使用者兩個都不要。真的 Plan 9 bind／mount namespace 也一句帶過：要權限或 user namespace，不是「自然組合」。

### 7. 並排與推薦

| | A 捷徑 | B 把手 | C 各寫 cwd | D 環境變數 |
|---|---|---|---|---|
| 食譜裡的字 | `.aos/x` | `x` 與 `/dev/fd/3/…` 兩種 | 要寫死相對位置 | `$env` |
| 誰站哪 | 全在廚房 | 全在食譜、葉子進廚房 | 頂層食譜、其餘廚房 | — |
| 要改什麼 | init 寫一條捷徑 | inst 串流路徑規矩、不關 fd | — | — |
| 暗規則 | 無（`.aos` 是 N-35、捷徑看得見） | 無（但 fd 3＝廚房是要記的約定） | 無 | 有 |
| 斷在哪 | 不斷 | 不斷 | 最後一格 | N-45 |
| 跨平台 | 任何檔案系統 | 要 `/dev/fd`／`/proc` | — | — |

**推薦 A。** 它一個 key 都不加、一條 inst 規矩都不改，全靠 N-35 的 `.aos/` 加一條 `ln -s`；而且把「廚房＝agent 的 node、`.aos/`＝食譜」這件事講得很直觀（`ls -la` 就看得見是哪份食譜）。唯一鬆的條件是 init 糖會寫一條捷徑，使用者已預告要做 init。B 留著當備案：零寫檔，但要改 inst 一條規矩、食譜裡一堆 `/dev/fd/3`。
