# 2026-10-28 aos-hub 下一步：常駐 aos-kernel 管所有 CLI 實例、pause 與 stop

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)｜前情：[10-27 aos-hub（demo）](2026-10-27-claude-switch.md)、[10-26 playground](2026-10-26-playground.md)（`_entry` 叫 claude、經 aos-mcp 接工具）｜使用者筆記：[user-advice/20261027](../user-advice/20261027.md)（使用者的資料夾，不改）｜程式（還沒改）：[extras/cli_hub](../extras/cli_hub/README.md)

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

## 決定（10-28）

1. **名字仍叫 aos-hub**，不叫 aos-ccc：管的不只 claude code，也包括 codex、pi coding agent 之類。
2. **環境變數用 `AOS_HUB`**（取代筆記裡的 `AOS_CLAUDE_CODE_CLI_HUB`）；`AOS_HUB` 指的資料夾裡跑一個**常駐的 aos-kernel**，管所有實例。
3. **kernel 掛了，依賴它的指令直接報錯**，不做自動接回或自動重開。
4. **限制實例數量：實作時再說。**
5. **要有 pause 和 stop 兩種。** 怎麼分是頂層的解讀（**代定、可翻案**）：
   - **pause**＝10-27 的「收起」：關掉程式，對話 id 留著，之後叫得回來。
   - **stop**＝結束這個實例：舊對話歸檔到 `AOS_HUB` 底下，不再叫回。
6. **舊的（舊對話歷史）放在 `AOS_HUB` 路徑下。**
7. **Ctrl-]＝跳出畫面但不結束實例**——這是筆記本身的意思，跟 10-27 晚「退出鍵只留一個」那條候選一致。

## 未決

- kernel 跟各指令怎麼溝通（IPC 用什麼）——使用者說是技術細節，先不考慮。
- aos-tools 長什麼樣（使用者還在規劃）；aos-mcp 怎麼包在它上面。
- 跟 aos-say／listen 怎麼結合（使用者自己也覺得「可能不太行」）。
- 一輪跑起來沒開畫面時怎麼看：`_entry` 那邊處理，還是 aos-mcp 記（筆記兩個都可）；10-27 的 `aos-hub watch`（讀 `live.jsonl`）是現有的一條路。
- 限制實例數量（決定 4，實作時再說）。

## 現有 aos-hub 跟新方向的差異（之後要改的）

10-27 的 aos-hub 是 demo（使用者 10-27「以後再完善」），以下照 10-28 的決定，實作時要改：

| 項目 | 現在（10-27） | 新方向（10-28） |
|---|---|---|
| 常駐程式 | 沒有；`aos-hub` 每次當場讀格裡的檔，自動收起靠 aos-loop 跑 `reap.json` | `AOS_HUB` 裡跑一個常駐 aos-kernel 管實例；kernel 沒在跑，指令直接報錯 |
| 位置 | `AOS_HUB` 沒設＝`~/.local/state/aos-hub/` | 一律 `AOS_HUB`（沒設時怎麼辦還沒定） |
| Ctrl-] | 跳出並叫 `aos-hub pick` 換一格 | 只跳出、不結束實例 |
| 停的方式 | 只有 `stop`（＝收起，叫得回來） | 分 `pause`（＝現在的收起）和 `stop`（結束、歸檔、不再叫回） |
| 舊對話 | 留在格裡，沒歸檔 | stop 時歸檔到 `AOS_HUB` 底下 |
| 指令 | `ls`、`pick`、`attach`、`watch`、`stop`；cd 過去打 `aos-hub` 直接接 | 筆記的 `state`（這裡是不是納管的實例）、`open [資料夾]`（＝現在的 `aos-hub`／`attach`）、`ls`；`state` 現在沒有 |
| 管哪些 CLI | claude、codex（cli_session 用過的格） | 加 pi coding agent 之類 |
| 數量上限 | 沒有 | 實作時再說 |
