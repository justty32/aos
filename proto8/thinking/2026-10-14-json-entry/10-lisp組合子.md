# 2026-10-14 Lisp／組合子視角

← [JSON 入口](../2026-10-14-json-entry.md)｜上一份：[09-daemon套fsm](09-daemon套fsm.md)

## 22. 使用者原話

> 然後，我又回到了lisp的感覺，想想看，就類似說：(loop inst), (loop (fsm idle (fsm ask wait) (tool tool-result)))

> 對，只有fsm不太夠...但，一樣，有需求再來做，反正這些都是小程式。

> 不造語法，但以後可以做lisp程式庫，輔助我們來快速建立相關東西。但這是很以後的事情了

## 23. 研究結論

- aos 像**只有特殊形式（fexpr）的 Lisp**：引數是 quote 住的 TARGET，何時求值由運算子決定。form 頭＝argv[0] 程式、引數＝JSON（map）、巢狀＝某格的值是另一個 TARGET。
- 最準類比是 **tagbody／go**：fsm＝tagbody、格＝標籤、`next`＝go、state 窗＝存檔的 continuation、巢狀 `end`＝return-from；巢狀 fsm 沒吐 next＝yield。loop／daemon 比較像求值器（trampoline／排程器）。
- 破的地方：值是 stdout 串流不是單值；每拍重生，沒落檔的全丟；轉移圖在 stdout 的 `next`，不在 form 裡，看式子看不出控制流。
- 使用者式子的正規形：`(loop (fsm idle (idle) (thinking (fsm ask wait)) (tool (fsm tool tool-result))))`。

## 24. 拍板

- **語法**：不造語法；以後可做 Lisp 程式庫輔助建立（很以後）。
- **表上靜態 next**（推薦）：格可寫 `{"target": …, "next": "b"}`；stdout 有 `next` 蓋過表上的；兩邊都沒有才留原狀態。06／08 的「沒吐＝留原狀態」已改。
- **子式名字**：在 `states` 表明寫（推薦）。
- **源碼寫法**：一份 JSON 樹為主（推薦）——一份 `agent.json` 用 `#/` 指格、子 fsm 設定內嵌在格裡（N-04）；資料夾是 state／work 落地處，需要時小工具攤平成資料夾。10-14 夜使用者補：寫 agent.json 或建資料夾**都可以**，inst TARGET 本來就兩種都收（[12](12-七題回覆.md)）。
- **一拍一步**（推薦）：fsm 一拍只跑一格。
- **巢狀出口的原子縫**：內層歸位與外層前進是兩次 rename，中間當掉會重發 LLM 請求。**接受重跑**（非推薦）——各格冪等性不保證、不在規範範圍內（N-20，10-14 夜）；要顧的格自己先看 `work/N` 有沒有舊結果。
- **格裡放 aos-loop／daemon**：不禁止、不鼓勵（推薦），靠 inst `timeout_ms` 守；文件寫明會阻塞一拍。

## 25. 其他組合子（按需再做，每個都是小程式）

| 組合子 | 補什麼 |
|---|---|
| seq | 一拍內先 A 再 B |
| par | 一拍內同時跑多片葉子並 join |
| race | 先完成者勝 |
| retry | 失敗重跑 N 次 |
| wait／until | 等某檔出現（非同步 think 的 wait 格就是它） |
| foreach | 對資料夾每個檔套同一張 inst |
| while | 依身體回傳停（可能只是 loop 多一個 key） |

→ 下一份：[11-下班前待辦](11-下班前待辦.md)、[12-七題回覆](12-七題回覆.md)
