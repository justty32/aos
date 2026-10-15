# 2026-10-15 kernel 截流：agent 只管叫、貴的呼叫先排隊

← [討論紀錄](README.md)｜概念：[CONCEPTS kernel](../CONCEPTS/04-kernel.md)、[agent](../CONCEPTS/05-agent.md)｜前情：[10-13 kernel／agent](2026-10-13-kernel-agent.md)、[`_metainfo`](2026-10-13-json-path/02-metainfo.md)｜程式：[lib agent.md](../lib/agent.md)、`aos_agent_call.py`（agent 當函數叫 agent，未進 git）

## 原文（10-15，照記）

「然後可以開 fable 去思考這塊：像這種 agent 函數呼叫 agent 函數的情況，會發現到他們都需要吃很多資源，比如 LLM 呼叫之類，所以這時候就是該 kernel 出場的時候了。agent 呼叫的時候可以不管那個 tool 的成本（當然，也可以在 tool 的 description 中稍微說一下，但不要說太多，小 LLM 模型的判斷力不足，會被這個搶走注意力），就是只管呼叫。然後 LLM 呼叫，乃至特定工具／agent 的呼叫，因為都是走 inst，所以可以套一層包裝，由 kernel 截流，讓 kernel 決定說要先處理哪個。套的包裝，可以是送給某 daemon 作為呼叫請求，或是隨意」

補充（看過 AI 的卡死分析後）：「卡死就卡死，就像我先前說的，S表達式中，一棵樹的可預期性等特性，可以參照其子葉的特性，不管是總和或其他都可以。kernel就是看這個來排程。這塊，所以說inst json格式中可以有_metainfo來表述」

定義與規範（10-15）：「kernel這塊，概念上就是指能夠管理哪些東西被執行或被使用的...一個東西，這個很寬泛，算是原生定義，而為了實作，我這邊補充追加：在當前的aos計劃下，kernel就是以inst/loop/daemon為基礎，能夠管理某一inst是否被執行的，一個正在執行，或是被執行的inst。那，規範這塊，我們就先做兩種kernel，一個用於管理LLM呼叫，一個則是通用的管理(以agent作為判斷)，然後都基於daemon。具體機制再來規劃。」

同日稍早：agent＝函數＋binding（bob/ 定義不變；frame 像 stack 累積 history，可與 cwd 不同）；tools＝傳進 call 的函數，裡面可以有別的 agent。環境：146 不准用，本機 LM Studio 一次只載一顆模型、顯卡跟使用者共用。

## 決定（使用者 10-15 定）

- **巢狀等待卡死不另做防護**：卡死就卡死，精神同 N-20（不保證、使用者的事）。
- **kernel 排程看的是呼叫樹的特性**：一棵樹（agent、工具、子 agent 串起來的 S 表示式）的可預期性等特性，由子葉的特性彙總（總和或別的彙總法都行）。出處＝C-22／2.16（agent 當 S 表示式拆，節點有的知道有的不知道，[河堤 2.16](2026-10-11-restart/02-河堤後段.md)）、C-13（九軸是每個任務自己的屬性）、C-22b（節點＝函式＋環境）。這也回答了 10-13 §3.2 留著的「包別人的 inst，`_metainfo` 自報還是由內層推」：由子葉彙總上去。
- **特性寫在 inst.json 的 `_metainfo`**（10-13 已定的「給 kernel 參考的抽屜」）；裡面的欄位與彙總規則之後再定。
- **kernel 定義兩層**＝[C-47](../CONCEPTS/04-kernel.md)（原生：管什麼被執行或使用；aos：以 inst／loop／daemon 為基礎管某 inst 是否執行）。**先做兩種 kernel**＝[N-42](../NORMS/09-kernel.md)（管 LLM 呼叫的；通用管理、以 agent 判斷的），都基於 daemon。
- **具體機制再規劃**：下面的閘門／信箱草案與六題未決**仍開著**，沒被這次定案取代。

## 結論（AI 整理，待使用者確認）

**對上既有概念**：這題就是 C-20。腦＝有限資源（C-09、C-10，本機一顆＝1 格）；排序 C-11；收件程式也是任務 C-12；腦是外部 PU（C-29）；kernel 只排程 C-38；kernel 基於 daemon（10-13 已定）。不用新概念。

**包裝的形狀（主線：送給 daemon）**：一支閘門 inst（暫叫 `aos-gate`），設定裡寫「真正要跑的 inst TARGET」。它不自己跑，把三樣東西寫成一封信丟進 kernel 的信箱（N-16 Maildir）：那份 inst、stdin 的內容、回信放哪；然後等回信，到了就把回信原樣吐到 stdout。呼叫端一個字不改：還是 N-12 的呼叫、還是拿到 N-30 那份結果，只是多等一會。agent.json 只改一行——`brain` 指到閘門；工具、子 agent 要排隊也一樣包。kernel 端＝daemon（N-28）底下一個收件 loop：每拍挑一封、認領（new→cur）、起 aos-inst 真跑、寫回信、刪信；一格一次一封。這也剛好是 N-41 說的「非同步 think」——把「丟請求、下一拍再看」做成通用的一支程式，同步格不用改就能排隊。

**「或是隨意」的其他形**：鎖窗（N-15）、代幣桶檔／號誌（N-14）最輕，先到先搶，kernel 看不到全局；信箱版 kernel 才有決定權。

**誰決定順序、kernel 看什麼**：順序由 kernel 排序格決定（C-15），初版先來先跑。閘門把被叫 inst 的 `_metainfo` 抄進信裡給 kernel 看；整棵彙總可作者自報，或 kernel 從子葉加總上去（差在誰算）。沒寫＝當便宜的，直接跑不排隊。

**agent 為什麼不管成本**：小模型注意力有限；成本是環境的事（C-22b），description 最多一句「會慢」。

**巢狀卡死**：已接受不防護。只有「包會再叫別人的工具」佔格才會卡；只包葉子（腦、單一貴工具）一格也夠。當慣例寫在閘門說明，不做機制。

**延遲與餓死**：排隊的時間會算進呼叫者的 `timeout_ms`（fsm 格、ask 工具 120000）；排太久＝整格 `timed_out`→`CellFailed`，呼叫端分不出「還在排」跟「壞了」。建議閘門自己有 `wait_ms`，超過就回 N-29 的錯 `QueueTimeout` 並撤信。純先到先跑下，長鏈（三顆腦串著）排在一堆短請求後面可能一直輪不到；排序格可用「等了幾拍」加分（C-38 時間參照）或樹的彙總深度，深的先。

**誰死了怎麼辦**：kernel 死＝信堆著沒人收，閘門等到逾時；重起讀 new/ 接著做（Maildir 天然可接回），cur/ 那封是半途的，N-20 不保證冪等→回錯給閘門比重跑穩。呼叫者先死＝閘門收 SIGTERM 時撤信（還在 new/ 的刪掉；已在跑的讓它跑完、結果沒人收）。腦本身壞（LM Studio 沒開）＝回信是錯，閘門照吐，agent 走既有 `BrainFailed`、連錯 `max_fails` 停。

## 未決（要使用者拍板；括號＝建議預設）

1. 包到哪：只包腦，還是工具、子 agent 也包？（先只包腦；工具有寫 `_metainfo` 才包）
2. 排隊用哪種窗：信箱 vs 鎖／號誌？（信箱，kernel 初版純先到先跑）
3. `_metainfo` 初版欄位：先只用一個 `resource`（例 `"llm"`），九軸等通用寫法照舊晚點再說？（是，先當閘門私約、不進規範）
4. 彙總規則與誰算：作者自報整棵 vs kernel 從子葉算（加總／取最大）？（先自報，寫了就用；沒寫的 kernel 把子葉加總）
5. 排隊久了算誰的：含在呼叫者 `timeout_ms` vs 閘門另算？（另設 `wait_ms`、錯碼 `QueueTimeout`）
6. kernel 重起時 cur/ 那封：重跑 vs 回錯？（回錯，N-20）

## 最輕的原型路線

- `aos_gate.py`：設定 `{"target": 腦的 TARGET, "queue": "q/", "wait_ms"}`；stdin 原樣＋target＋target 的 `_metainfo`＋回信路徑寫成一封信丟 `q/new/`，等回信檔出現就吐出；SIGTERM 撤信。
- `aos_gate_kernel.py`：一個 loop 的身體（或 daemon 子 loop）：每拍 new/ 最舊一封→cur/→aos-inst 真跑→回信→刪；一格＝一次一封。
- demo：三個 agent 共用假腦（`fake.py` 加 sleep 2 秒），`brain` 全指閘門；看 kernel 的 stdout 順序、各 agent 拍數與 `timed_out`。
- 再接 clerk 巢狀例子（甲問乙、乙叫腦）跑一圈，確認只包腦時一格就夠。
- 全本機、不碰 146；LM Studio 一顆模型剛好＝1 格，假腦跑順再換真腦。
