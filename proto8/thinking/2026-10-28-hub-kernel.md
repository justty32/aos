# 2026-10-28 aos-hub 下一步：常駐 aos-kernel 管所有 CLI 實例、pause 與 stop

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)｜前情：[10-27 aos-hub（demo）](2026-10-27-claude-switch.md)、[10-26 playground](2026-10-26-playground.md)（`_entry` 叫 claude、經 aos-mcp 接工具）｜使用者筆記：[user-advice/20261027](../user-advice/20261027.md)（使用者的資料夾，不改）｜程式：[extras/cli_hub](../extras/eca_hub/README.md)（10-28 下午照這裡的決定改完）｜後續：[10-28 hub-adapter](2026-10-28-hub-adapter.md)（say／listen 協議、適配表、副產物、實作與實跑）

> 10-30 起 aos-hub 改做 aos-eca-hub，見 [eca](2026-10-30-eca.md)。

規矩見 [thinking/README](README.md)：只留使用者原文、決定、結論。

## 使用者原文

### 10-27 晚的筆記（整理版，全文見 [user-advice/20261027](../user-advice/20261027.md)）

- **一輪對話＝一個函數**：agent 的一輪＝「輸入之後，到 agent 不再叫工具、吐出回覆為止」。參數三個：endpoint（最容易出錯，404 之類都要處理）、prompt（初始 prompt 加後續插話的入口，像串流）、tools（外部函式庫，最靈活）。途中可能被插話、被暫停去做別的；最終回覆以外的訊息是副產物。
- **先拿 claude code cli 當這個函數**：別人已經做好了，還有 TUI；缺點是吃記憶體和 CPU，但起步先用它上手。現有的 aos loop／fsm 靈活，但這次不談它。
- **`_entry` 是一個小腳本**：擬好啟動 claude code cli 的旗標、接上 MCP 的 json、啟動；aos 的其他函數經 **aos-mcp** 接進去。
- **一個環境變數指向一個資料夾，裡面跑一個 aos-kernel**，管所有納進 aos 的這類實例：記哪個資料夾有實例在跑；閒太久就關掉、歷史存到那個資料夾；給使用者查詢與存取的指令。
- 筆記裡的指令（當時叫 `aos-ccc`）：`state`（這個資料夾是不是納管的實例）、`open [資料夾]`（打開 TUI）、`ls`（列出所有在跑的實例與所在資料夾）、`stop`（把實例暫停）；靠 shell 的快捷鍵 **Ctrl-]：退出 TUI 但不結束實例**。這些都靠那個環境變數和跑著的 aos-kernel；跟 kernel 用 IPC 溝通——「這些是技術細節，現在先不考慮」。
- kernel **或許**會限制同時在跑的實例數，甚至看當前跟 claude 的連線數來限（一個帳號同時打一堆請求過去不太好）。
- **aos-mcp 是一個小包裝，跑在 aos-tools 上**；aos-tools 還在規劃，是把 aos 函數跟「當前資料夾 agent 的 tools 註冊表」關聯起來管理的橋。
- 擔心的事：claude code cli 的 session 存哪裡？開新 session，舊 session 的歷史怎麼辦？之前規劃在 aos loop／fsm agent 上做 aos-say／listen 跟 agent 交流，能不能跟這個有機結合——「可能不太行」。
- claude code cli 的問題：一輪跑起來，不 open 進去看，就只能事後翻 history；看是 `_entry` 腳本那邊處理，還是 aos-mcp 記一下都可以。

### 10-28（逐字）

頂層拿筆記跟 10-27 的 aos-hub 對照後，使用者回：

> 其實應該還是要aos-hub。因為不只claude code cli，可能也要包括pi coding agent, codex之類。kernel掛掉後這些依賴於他的指令就報錯，限制數量這塊之後實作時再說。應該要有pause和stop兩種。舊的，應該會在AOS_HUB這個路徑下，對，把AOS_CLAUDE_CODE_CLI_HUB那個路徑改成這個。

頂層接著把五處跟原則對不上的地方攤給他（①常駐 kernel 後狀態以誰為準 ②名字撞 CONCEPTS 的 kernel ③舊對話搬到全機的 `AOS_HUB` ④pause／stop 的解讀 ⑤`AOS_HUB` 沒設怎麼辦），他回：

> 首先是筆記中那段pseudo code，其中的prompt那塊，確實應該換成stdin/out，可以把它當queue，然後在迴圈中做queue.pop(), queue.push()。然後像這種別人做好了的agent程式，他和我們aos loop/fsm agent的差別，就在於我們的aos loop/fsm agent我們可以靈活地掌握底層，所以其各階段都可以是aos函數，這使我們能夠更好的進行控制。 1. 以kernel記的為準。2.就是同個東西，kernel他就是一個負責排隊和分配資源的程式，hub他是在kernel的基礎上去額外做的功能，或者說他是kernel的一種。3.可以放在工作區啦。4.你的解讀比較好。5.報錯

頂層再問兩個邊緣狀況（使用者插話時 agent 正在等工具：排隊等這輪做完還是打斷；kernel 記的跟實際不符〔實例自己掛了、被 OOM 砍〕要不要定期對帳、kernel 重開後記錄要不要存硬碟），他回：

> prompt當queue這塊，等工具做完或打斷，這就隨意，沒必要訂死，因為大家都有不同需求，可能有些agent適合打斷，有些適合做完，這就是aos agent的靈活之處，你可以自己掌控設定。kernel這塊，寄售等實際遇到問題之後再來解決。

（「寄售」應是「就」的打字誤：意思是 kernel 這塊就等實際遇到問題之後再來解決。）

頂層再問兩題（①舊對話歸檔放工作區的哪裡：放 `$AOS_WS/.stack/` 底下不衝突 C-65，跟 `new/`、`out/` 並排就衝突 ②hub 的常駐 kernel 要不要照 C-47／N-42 建在 daemon 上、算不算第三種 kernel〔N-42 只列 LLM、通用兩種〕），他回：

> 1. 隨意，盡量不要與現有的衝突。2.好問題，我也不確定。我覺得沒差。

## 決定（10-28）

1. **名字仍叫 aos-hub**，不叫 aos-ccc：管的不只 claude code，也包括 codex、pi coding agent 之類。
2. **環境變數用 `AOS_HUB`**（取代筆記裡的 `AOS_CLAUDE_CODE_CLI_HUB`）；`AOS_HUB` 指的資料夾裡跑一個**常駐的 aos-kernel**，管所有實例。（10-30 改口：aos-eca-hub 建在 daemon 上，見 [eca](2026-10-30-eca.md)）
3. **kernel 掛了，依賴它的指令直接報錯**，不做自動接回或自動重開。（10-30 改口：aos-eca-hub 建在 daemon 上，見 [eca](2026-10-30-eca.md)）
4. **限制實例數量：實作時再說。**
5. **要有 pause 和 stop 兩種**（頂層的解讀，使用者 10-28「你的解讀比較好」，定案）：
   - **pause**＝10-27 的「收起」：關掉程式，對話 id 留著，之後叫得回來。
   - **stop**＝結束這個實例：舊對話歸檔，不再叫回。
6. **舊對話歸檔放在工作區的 stack 裡**（`$AOS_WS/.stack/` 底下，具體路徑實作時定；使用者「可以放在工作區啦」、「隨意，盡量不要與現有的衝突」）——改掉原本「放在 `AOS_HUB` 路徑下」；不跟 `new/`、`out/` 並排，所以不碰 C-65。
7. **Ctrl-]＝跳出畫面但不結束實例**——這是筆記本身的意思，跟 10-27 晚「退出鍵只留一個」那條候選一致。
8. **實例狀態以 kernel 記的為準**，不再像 10-27 那樣當場讀格裡的檔。（10-30 改口：aos-eca-hub 建在 daemon 上，見 [eca](2026-10-30-eca.md)）
9. **hub 是 kernel 的一種**：kernel＝負責排隊和分配資源的程式，hub 在它上面多做事（列實例、接畫面、pause／stop）。所以不算撞名，跟 CONCEPTS 的 kernel（C-12 排序與資源分配）是同一個概念。（10-30 改口：aos-eca-hub 建在 daemon 上，見 [eca](2026-10-30-eca.md)）
10. **`AOS_HUB` 沒設＝報錯**，不給預設路徑（取代 10-27 的 `~/.local/state/aos-hub/`）。
11. **筆記 pseudo code 裡的 prompt 參數＝stdin／stdout**，當成一條 queue：使用者的新話、模型的回覆都經它，迴圈裡 `queue.pop()`／`queue.push()`。
12. **現成 agent 程式（claude code 之類）跟 aos loop／fsm agent 的差別**：後者底層握在我們手上，每個階段都能是 aos 函數，所以控制得更細。
13. **插話時等這輪做完還是打斷：不訂死**，每個 aos agent 自己設定——這正是 aos agent 的靈活處。現成 agent 程式（claude code 之類）的 queue 不在我們手上，照它自己的。
14. **hub 的常駐 kernel 要不要照 C-47／N-42 建在 daemon 上、算不算第三種 kernel：實作時自由選**（照 daemon 做或不照都行），不列待辦——使用者「我也不確定。我覺得沒差」。

## 未決

- kernel 跟各指令怎麼溝通（IPC 用什麼）——使用者說是技術細節，先不考慮。
- aos-tools 長什麼樣（使用者還在規劃）；aos-mcp 怎麼包在它上面。
- ~~跟 aos-say／listen 怎麼結合~~：10-28 下午做成了——hub 實作 say／listen 的信箱協議，見 [hub-adapter](2026-10-28-hub-adapter.md)。
- 一輪跑起來沒開畫面時怎麼看：`_entry` 那邊處理，還是 aos-mcp 記（筆記兩個都可）；10-27 的 `aos-hub watch`（讀 `live.jsonl`）是現有的一條路。
- 限制實例數量（決定 4，實作時再說）。
- **kernel 記的跟實際不符**（實例自己掛了、被 OOM 砍）要不要定期對帳、kernel 重開後記錄要不要存硬碟：使用者說等實際遇到問題再解決，先不處理、不列待辦。
- **「hub 是 kernel 的一種」跟通用 kernel 那題相關**：plan 留給使用者的方向題「通用 kernel 未決」（[plan § 1.2 第 3 題](2026-10-21-plan.md#12-留給你討論的不代定鐵律-5)、WAIT_USER 也掛著）——aos-hub 的常駐 kernel 算不算第三種、要不要建在 daemon 上，使用者 10-28 說沒差（決定 14，實作時自由選）；通用 kernel 那題本身仍掛在 plan，這裡不代定。

## 跟原則的對照（10-28）

10-28 的回答解掉的：狀態以誰為準（決定 8）、名字撞 kernel（決定 9）、舊對話搬到全機一份的地方跟 C-67／N-13（狀態落在 stack、位置由叫的人給）打架（決定 6，放工作區就不搬出去了）、pause／stop 解讀（決定 5）、`AOS_HUB` 沒設（決定 10，跟 N-13「需要的環境變數沒設就退 1」同調）。

10-28 再問兩題後解掉的：

- **C-65 工作區只放交辦的東西與成果、執行時的東西落在 stack**：舊對話歸檔放 `$AOS_WS/.stack/` 底下（決定 6，使用者「盡量不要與現有的衝突」），不跟 `new/`、`out/` 並排，所以不衝突。
- **C-47／N-42**（kernel 以 inst／loop／daemon 為基礎；N-42 只列 LLM、通用兩種）：hub 的常駐 kernel 要不要照 daemon 做、算不算第三種——**使用者表示沒差**（決定 14），實作時自由選，不算衝突、不列待辦。

歸到「kernel 這塊遇到實際問題再解決」（使用者 10-28「kernel這塊，寄售等實際遇到問題之後再來解決」），先記著、不列待辦：

- **N-13／C-52**：狀態以 kernel 記的為準，但格裡的 `busy.txt`、`lock` 這些仍是 cli_session 自己在 stack 外顯的狀態（N-13）。兩邊不一致時以 kernel 為準是定了，kernel 怎麼得知格裡的變化而不去讀下一層的內部（C-52 只管自己這層，10-27 已記的老問題）還沒定。
- **C-67 位置由叫的人給**：`AOS_HUB` 由環境變數給，形式上合；但「全機所有實例共用一個 kernel」這種全機一份的東西，原則裡還沒有。

## 現有 aos-hub 跟新方向的差異（之後要改的）

10-27 的 aos-hub 是 demo（使用者 10-27「以後再完善」），以下照 10-28 的決定，實作時要改。**10-28 下午已照表改完**（使用者「hub也可以開始做」），做法與代定見 [hub-adapter](2026-10-28-hub-adapter.md#結論二aos-hub-照-10-28-決定改完)：

| 項目 | 現在（10-27） | 新方向（10-28） |
|---|---|---|
| 常駐程式 | 沒有；`aos-hub` 每次當場讀格裡的檔，自動收起靠 aos-loop 跑 `reap.json` | `AOS_HUB` 裡跑一個常駐 aos-kernel 管實例，狀態以它記的為準；kernel 沒在跑，指令直接報錯 |
| 位置 | `AOS_HUB` 沒設＝`~/.local/state/aos-hub/` | 一律 `AOS_HUB`；沒設＝報錯 |
| Ctrl-] | 跳出並叫 `aos-hub pick` 換一格 | 只跳出、不結束實例 |
| 停的方式 | 只有 `stop`（＝收起，叫得回來） | 分 `pause`（＝現在的收起）和 `stop`（結束、歸檔、不再叫回） |
| 舊對話 | 留在格裡，沒歸檔 | stop 時歸檔，放在工作區的 `.stack/` 底下（具體路徑實作時定） |
| 指令 | `ls`、`pick`、`attach`、`watch`、`stop`；cd 過去打 `aos-hub` 直接接 | 筆記的 `state`（這裡是不是納管的實例）、`open [資料夾]`（＝現在的 `aos-hub`／`attach`）、`ls`；`state` 現在沒有 |
| 管哪些 CLI | claude、codex（cli_session 用過的格） | 加 pi coding agent 之類 |
| 數量上限 | 沒有 | 實作時再說 |
