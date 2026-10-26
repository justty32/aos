# 2026-10-15 kernel 截流：agent 只管叫、貴的呼叫先排隊

← [討論紀錄](README.md)｜概念：[CONCEPTS kernel](../docs/CONCEPTS/04-kernel.md)、[agent](../docs/CONCEPTS/05-agent.md)｜前情：[10-13 kernel／agent](2026-10-13-kernel-agent.md)、[`_metainfo`](2026-10-13-json-path/02-metainfo.md)｜續：[LLM kernel 優先級](2026-10-15-llm-kernel.md)

## 原文（10-15，照記）

「然後可以開 fable 去思考這塊：像這種 agent 函數呼叫 agent 函數的情況，會發現到他們都需要吃很多資源，比如 LLM 呼叫之類，所以這時候就是該 kernel 出場的時候了。agent 呼叫的時候可以不管那個 tool 的成本（當然，也可以在 tool 的 description 中稍微說一下，但不要說太多，小 LLM 模型的判斷力不足，會被這個搶走注意力），就是只管呼叫。然後 LLM 呼叫，乃至特定工具／agent 的呼叫，因為都是走 inst，所以可以套一層包裝，由 kernel 截流，讓 kernel 決定說要先處理哪個。套的包裝，可以是送給某 daemon 作為呼叫請求，或是隨意」

補充（看過 AI 的卡死分析後）：「卡死就卡死，就像我先前說的，S表達式中，一棵樹的可預期性等特性，可以參照其子葉的特性，不管是總和或其他都可以。kernel就是看這個來排程。這塊，所以說inst json格式中可以有_metainfo來表述」

定義與規範（10-15）：「kernel這塊，概念上就是指能夠管理哪些東西被執行或被使用的...一個東西，這個很寬泛，算是原生定義，而為了實作，我這邊補充追加：在當前的aos計劃下，kernel就是以inst/loop/daemon為基礎，能夠管理某一inst是否被執行的，一個正在執行，或是被執行的inst。那，規範這塊，我們就先做兩種kernel，一個用於管理LLM呼叫，一個則是通用的管理(以agent作為判斷)，然後都基於daemon。具體機制再來規劃。」

同日稍早：agent＝函數＋binding（bob/ 定義不變；frame 像 stack 累積 history，可與 cwd 不同）；tools＝傳進 call 的函數，裡面可以有別的 agent。環境：146 不准用，本機 LM Studio 一次只載一顆模型、顯卡跟使用者共用。

## 決定（使用者 10-15 定）

- **巢狀等待卡死不另做防護**：卡死就卡死，精神同 N-20（不保證、使用者的事）。
- **kernel 排程看的是呼叫樹的特性**：一棵樹（agent、工具、子 agent 串起來的 S 表示式）的可預期性等特性，由子葉的特性彙總（總和或別的彙總法都行）。出處＝C-22／2.16（agent 當 S 表示式拆，節點有的知道有的不知道，[河堤 2.16](2026-10-11-restart/02-河堤後段.md)）、C-13（九軸是每個任務自己的屬性）、C-22b（節點＝函式＋環境）。10-13 §3.2 的「包別人的 inst，`_metainfo` 自報還是由內層推」：由子葉彙總上去。
- **特性寫在 inst.json 的 `_metainfo`**（給 kernel 參考的抽屜）；裡面的欄位與彙總規則之後再定。
- **kernel 定義兩層**＝[C-47](../docs/CONCEPTS/04-kernel.md)（原生：管什麼被執行或使用；aos：以 inst／loop／daemon 為基礎管某 inst 是否執行）。**先做兩種 kernel**＝[N-42](../docs/NORMS/09-kernel.md)（管 LLM 呼叫的；通用管理、以 agent 判斷的），都基於 daemon。
- **具體機制**：照下面的閘門／信箱與六題建議預設定案。

## 結論（照推薦定案）

- **對上既有概念**：這題就是 C-20（腦＝有限資源 C-09／C-10，本機一顆＝1 格；排序 C-11；kernel 只排程 C-38；基於 daemon）。不用新概念。
- **包裝（主線：送給 daemon）**：一支閘門 inst（`aos-gate`），設定寫真正要跑的 inst；它把那份 inst、stdin 內容、回信放哪寫成一封信丟進 kernel 的信箱（N-16 Maildir），等回信、原樣吐到 stdout。呼叫端照舊 N-12 呼叫、拿 N-30 結果；agent.json 只改 `brain` 指到閘門，工具、子 agent 要排隊也一樣包。kernel 端＝daemon（N-28）底下一個收件 loop：每拍挑一封、認領（new→cur）、起 inst 真跑、寫回信、刪信；一格一次一封（＝N-41 的「非同步 think」做成通用一支程式）。
- **順序與 `_metainfo`**：順序由 kernel 排序格決定（C-15），初版先來先跑；閘門把被叫 inst 的 `_metainfo` 抄進信裡給 kernel 看。
- **巢狀卡死**：只有「包會再叫別人的工具」佔格才會卡；只包葉子（腦、單一貴工具）一格就夠。當慣例寫在閘門說明，不做機制。
- **誰死了**：kernel 死＝信堆著，重起讀 new/ 接著做；呼叫者先死＝閘門收 SIGTERM 撤信（還在 new/ 的刪掉，已在跑的讓它跑完）；腦壞＝回信是錯，閘門照吐，agent 走既有 `BrainFailed`。

## 六題（照建議預設定案；題目後是採用的做法）

1. 包到哪：只包腦，還是工具、子 agent 也包？→ 先只包腦；工具有寫 `_metainfo` 才包。
2. 排隊用哪種窗：信箱 vs 鎖／號誌？→ 信箱，kernel 初版純先到先跑。
3. `_metainfo` 初版欄位：先只用一個 `resource`（例 `"llm"`），九軸等通用寫法照舊晚點再說？→ 是，先當閘門私約、不進規範。
4. 彙總規則與誰算：作者自報整棵 vs kernel 從子葉算（加總／取最大）？→ 先自報，寫了就用；沒寫的 kernel 把子葉加總。
5. 排隊久了算誰的：含在呼叫者 `timeout_ms` vs 閘門另算？→ 含在呼叫者的 `timeout_ms` 裡，閘門不另設等待上限（KISS 1.8，使用者「其他都按照推薦」）。
6. kernel 重起時 cur/ 那封：重跑 vs 回錯？→ 回錯，N-20。

細節見 [LLM kernel § 動工自定點](2026-10-15-llm-kernel.md#動工自定點)、[KISS 彙整](2026-10-15-kiss/README.md)。
