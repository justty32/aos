# 2026-10-24 fsm 格的 exec：能不能寫「相對於這格」

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)

起因：看 agent-dan 的 `fsm.json`（[2026-10-23 腦的工具呼叫](2026-10-23-tool-calls.md)），think、act 兩格的 `exec` 寫死成 `"fsm.json#/states/think/body"`。

## 使用者原文（整理版，10-24）

- 「fsm.json中，states.think.exec的內容，爲何不能用指示詞：AOS_CO/exec呢？」
- 看完下面三條路之後：「先改成不寫死檔名的寫法。然後這三條路...感覺除了1我勉強可接受外，其他都不太好」

## 結論（跟 AI 討論後）

**為什麼現在不能寫 `AOS_CO` 再接 `/exec`**：

- `AOS_CO` 是 aos-exec **每跳都重設**的「入口在那份 JSON 裡的位置」（N-57）。loop 跑 `fsm.json` 時，aos-exec 挑的是 `fsm.json` 的 `_entry`，所以 aos-fsm 拿到的 `AOS_CO` 是 `/_entry`，不是 think 那格（實測：`printenv AOS_CO` 印 `/_entry`）。fsm 解格的 `exec` 時，這個值跟正在解的那格無關。
- `AOS_CO` 只是指標、不帶檔名；單靠它拼不出 aos-exec 認得的 `檔#/指標`。
- 指示詞不做字串內插：一個 `$env` 只換一個變數，`$path` 是照字面接上去的字串（N-45），沒辦法把 `AOS_CF` 和 `AOS_CO` 兩個變數拼在一起。

**現在就能用、不寫死檔名的寫法**：`{"$env": "AOS_CF", "$path": "#/states/think/body"}`。aos-fsm 10-23 晚起會解格的 `exec`（[table.cpp](../impls/aos-fsm/src/table/table.cpp)、N-45），`AOS_CF` 在 fsm 那一跳就是 `fsm.json` 的絕對路徑，`$path` 以 `#` 開頭直接接上。檔名不寫死，但格的位置（`#/states/think/body`）還是寫死的。

**三條「相對於這格」的路**（都還沒做）：

1. **fsm 解格之前，把 `AOS_CO` 設成那格的位置**（例 `/states/think`），格裡就能寫 `$env: AOS_CO` 加 `$path`。卡點：`AOS_CO` 不帶檔名，還是得另外接 `AOS_CF`，而指示詞拼不了兩個變數；`AOS_CO` 是 aos-exec 定義的（N-57），讓 fsm 在解指示詞時改它的意思，撞 N-57 與 N-45；`states` 若用 `$ref` 拆到別的檔，那格真正所在的檔不是 `AOS_CF`，要擴 `resolve_shallow` 記下每格出自哪份檔。
2. **`exec` 收相對寫法**，例 `"#body"` 表示「這格的 `body`」。卡點：N-36（fsm 只看名字跑格，不管格裡的事）、C-56（多一種只在這裡成立的寫法）。
3. **`exec` 直接放內嵌單子**（物件）。卡點：翻 10-21 計畫 F2 的代定（`exec` 只收字串，[2026-10-21-plan](2026-10-21-plan.md)）；撞 N-36（fsm 不碰格的內容）、N-28（loop／daemon 的 `exec` 同義、只收 aos-exec 的目標）、N-25（單子只由 aos-exec 跑）。**〔10-24 稍晚採用，見下「exec 直接放單子」；這三個卡點隨使用者的決定解掉：10-21 那句是轉述多推了一步，條文照改〕**

## 決定

- 先把 agent-dan 的 think、act 改成 `{"$env": "AOS_CF", "$path": "#/states/<名>/body"}`（10-24 做了，[demo/README § agent-dan](../demo/README.md)）。
- 路 1 使用者「勉強可接受」，**未定、不動工**；路 2、3 使用者覺得不太好。

## 未決

- 要不要走路 1（掛在 [NORMS 待定](../NORMS/08-待定.md)「相對於這格的 exec」）。〔10-24 稍晚：路 3 採用後，「相對於這格」的需要沒了，待定那行改成已解；路 1 使用者沒明說撤回，頂層代定為不做，可翻案〕
- 其他 demo（agent-bob、cathy、agent-ann、daemon、tick）也寫死檔名，要不要一起改成 `$env: AOS_CF` 寫法，使用者還沒說。〔10-24 稍晚：全部改成內嵌，見下〕

<a id="10-24-exec-直接放單子"></a>
## 10-24 稍晚：exec 直接放單子（路 3 採用）

### 使用者原文（整理版）

- 頂層說明 10-21 定了 loop／fsm 的 exec「只收 aos-exec 的目標，不再支援內嵌單子；要內嵌就寫 loop.json#/body」、fsm 是頂層比照代定的之後：「不過exec本來就應該要可以直接放內嵌單子吧」
- 「啊？loop的exec只收aos-exec能跑的目標...不是啊，內嵌單子aos-exec本來就能跑吧」
- 頂層查到 [10-21 計畫 § 2.2](2026-10-21-plan.md) 那句標著「頂層轉述」，判斷是轉述多推了一步（把內嵌單子排除），提議恢復；使用者：「好，就這樣做」

### 決定

- **loop、fsm、daemon 的 `exec` 都可以直接放單子物件**（指示詞先換一層，換完是物件就是單子）。拿到物件時**在自己行程內**呼叫 aos-exec 跑單子用的同一套（impls aos-exec 的 `run_inst`，底下是 inst 的 C lib）：`timeout_ms`、`grace_ms`、訊號轉給整群、結束碼都跟 aos-exec 跑單子一樣（10-21 前 loop 就是這樣）。字串、字串陣列照舊交給 aos-exec。
- demo 全部改成內嵌，不再繞一圈指自己的 `body`：agent-dan／bob／cathy／ann 的 fsm.json、ann 的 loop.json、daemon.json、tick 的 loop.json。
- 條文照改並記使用者原話；10-21 計畫 § 2.2 那句加註「轉述有誤」。`檔#/body` 這種寫法照樣能用（就是普通的 aos-exec 目標）。

### 實作時頂層代定的（可翻案；照 N-57 推）

1. **環境變數**：跑單子的那段時間，`AOS_CF`＝寫著它的設定檔（解開捷徑的實際路徑）、`AOS_CD`＝那份檔的資料夾、`AOS_CO`＝它在檔裡的 JSON 指標（loop／daemon＝`/exec`，fsm＝`/states/<名>/exec`；設定檔寫成 `檔#/指標` 時接在那個指標後面；名字照 JSON 指標跳脫）——就是 aos-exec 跑 `loop.json#/exec` 時會設的那三個。跑完還原成原本的（loop 之後讀 ctl 的指示詞、下一次跑字串目標時看到的還是自己的）。`AOS_WS`、`AOS_STACK` 照呼叫者現有的。翻案＝改設別的值（例如不動這三個）。
2. **相對路徑的基準＝`AOS_CD`**（設定檔的資料夾，同 aos-exec cd 進設定檔所在的資料夾）；字串目標仍照 cwd 算（L4 不變）。慣例下兩者一樣。單子裡相對的 `$ref` 從 `exec` 那格來自的那份檔的資料夾算。
3. **單子裡的指示詞跑的時候才解**（每次都解，那時三個 `AOS_*` 已設好），loop／fsm／daemon 讀設定時只把 `exec` 換一層、不往單子裡面走（10-23 晚「`exec` 整個解」改成這樣，只對物件）。
4. **單子壞＝那支程式自己的錯**：一行「程式名: 代號 原因」、退 1（`EntryBad`＝形狀不對、`DirectiveBad`＝指示詞解不開、`LaunchFailed`＝起不來；原因開頭「單子跑不起來：」，同 aos-exec）。形狀只在跑的時候驗（同 aos-exec），fsm 開跑時查整張表不查單子裡面。fsm 遇到單子壞不寫 trace、state 不動。
5. **daemon 的子項**：子 loop 讀的是小格裡的 `loop.json`，所以子項單子的 `AOS_CF`＝小格的 `loop.json`、`AOS_CO`＝`/exec`。為了「相對路徑從 daemon 的 cwd 算」（N-28）照舊成立，daemon 寫小格時：單子沒寫 `cwd`＝補上 daemon 的 cwd，`cwd` 是相對的字串＝接在 daemon 的 cwd 後面（`cwd` 是指示詞就不動）；單子裡相對的 `$ref` 檔名照它來自的那份檔轉成絕對（不解）。ctl 半路加的子項（`loops`／`loops_added`）同一套。
6. 訊息裡的「誰」：單子寫成「檔名#指標」，例「aos-loop: 第 1 次 loop.json#/exec 失敗，結束碼 7」。

### 挖出的邊緣狀況（照 N-57 推、還沒問使用者）

- `exec` 本身是 `$ref` 指到別份檔的單子：`AOS_CF`／`AOS_CO` 仍指設定檔裡寫 `exec` 的那格（不是 `$ref` 指到的那份檔）；裡面的 `$ref` 從那份檔的資料夾算。`states` 或格用 `$ref` 拆到別份檔時同理，`AOS_CO` 照原文寫的位置算、不穿過 `$ref`（同 N-62「指標走原文」），拿 `AOS_CF#AOS_CO` 回頭讀原文可能指不到。
- 單子被 `timeout_ms` 收掉：行程內跑看得到是訊號停的，fsm 的 trace 寫 `code` 143、`signal` 15；同一張單子寫成 `檔#/body` 經 aos-exec 跑時，是 aos-exec 以 143 正常結束，`signal` 是 null。
- 直接叫 `aos-loop`（不經 aos-exec）而且沒設 `AOS_WS`／`AOS_STACK`：單子看到的就是沒設（不像 aos-exec 會補上工作區與預設 stack）。
- 不讀 `.env`：loop 不「走進」哪裡，設定檔資料夾的 `.env` 在 loop 被 aos-exec 起來時已經套過；單子物件裡寫 `.env` key 不作用（只有沒 `argv` 的物件當資料夾時 aos-exec 才看，這裡沒 `argv`＝單子壞）。
- 沒 `argv` 的物件：aos-exec 把它當資料夾再取 `_entry`；`exec` 裡＝單子壞（`EntryBad`）。要那種寫法就照舊寫字串目標 `loop.json#/…`。
- daemon 子項單子的 `cwd` 若是指示詞、解出來是相對路徑，會從小格算；裡面的 `$env AOS_CF` 拿到的是小格的 `loop.json`。
- 行程內跑單子的期間 loop 自己被擋在那裡（同字串目標，阻塞到它結束）；daemon 自己的 `exec` 是單子時，那段時間不巡子項（同 10-21 前、同字串目標）。
