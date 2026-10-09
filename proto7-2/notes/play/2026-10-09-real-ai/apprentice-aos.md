# 2026-10-09 真 AI 學徒寫 aos 工具包與模組包（A5 隊）

← [真 AI 第一圈](README.md)｜程式：[author 包](../../../packs/author/README.md)（`aos7_author_aos.py`）｜三關：[checkers](../../../packs/author/checkers/README.md)｜證據：[evidence/apprentice/](evidence/apprentice/)

使用者目標 3「讓 AI 熟悉 aos、自己做模組／工具」的第一次真跑。學徒是真模型，寫一個新工具包或新模組，過三關（靜態、沙箱測試＋獨立答案、審查）才發布到 `apprentice/` 分支；合不合由隊長（頂層代理）決定。

## 一句話結果

**兩題都有過三關的發布，兩題都已審合進 `loop8/A5`**（`packs/usage/`、`modules/llmdiag/`）。學徒共 15 次出題呼叫、審查 7 次、寫踩坑 1 次，合計 23 次真 AI 呼叫（gate ≤150）、236 091 token。**看不出自我改進**：題 2 帶踩坑比不帶少重問 1 次，但兩邊失敗的原因都不是踩坑能防的（見下）。

## 怎麼跑的

- 學徒 node：`../aos-wt/apprentice-node`，先 `aos7-wfnode init` 裝好 wf；同 node 開 budget（grant 1 億、gateway `llm.litellm`）。
- 每題一圈：`aos7-author propose <需求.json> --llm 學徒 --review-llm chatgpt-gpt-6-astra-high --budget budget/llm --context …` →（不過）把上一份候選與檢查結果交回學徒重問，最多 2 次 → 過了 `publish … --reviewer file:<審查回覆> --ref main`。腳本：[evidence/apprentice/drive.py](evidence/apprentice/drive.py)。
- 提示給 BRIEF、工具卡、三關規則與幾份參考檔；**不給答案檢查器**（測試鎖住）；不設 max_tokens。
- 題 1 做完後跑 `aos7-author learn`，由學徒自己（sol-high）把這題踩過的坑寫進它 node 的 `wf/workflows/common/gotchas.md`（[寫完的樣子](evidence/apprentice/gotchas-final.txt)）；題 2 用 `--gotchas` 帶進提示。
- 第 3 關審查人是 astra-high 經 llmcall（有帳），回覆以 `--reviewer file:` 交檢查器；送審前先過 rules。

## 結果

| 題 | 學徒 | 輪數 | 每輪結果 | 學徒 token | 審查 token | 秒 | 發布 |
|---|---|---|---|---|---|---|---|
| 1 usage（需求第一版） | sol-high | 3 | ②答案 → ②答案 → ①非 JSON | 42 562 | 0 | 245 | 無（3 輪都沒過） |
| 1 usage（需求補寫後） | sol-high | 3 | ①非 JSON → ③審查退 → 過 | 35 717 | 15 377 | 328 | `apprentice/usage1_b8891b81` **已合** |
| 1 usage（比較） | astra-high | 1 | 過 | 11 041 | 9 258 | 178 | `apprentice/usage1_05263eae` 未合 |
| 2 llmdiag（帶踩坑） | sol-high | 2 | ①非 JSON → 過 | 20 494 | 6 729 | 243 | `apprentice/diag1_e8800ec9` **已合** |
| 2 llmdiag（不帶踩坑，對照） | sol-high | 3 | ①非 JSON → ①空回覆 → 過 | 24 228 | 6 356 | 203 | `apprentice/diag1_af24a314` 未合 |
| 2 llmdiag（比較） | astra-high | 3 | ③審查退 → ①超大小 → 過 | 42 250 | 15 965 | 400 | `apprentice/diag1_c029ed61` 未合 |

（「秒」是各輪 propose 牆鐘相加，含三關沙箱與審查；publish 每次約 1～2 秒。）

**人工修正**：合進來後只修 1 次（一個 commit）：兩個索引列被三關附加在檔尾、落在表格外，搬回表格並把 `day|hour` 改成不會切斷表格的寫法。程式本身零修改。

**人工備援**（gpt-6.1-sol 代寫）：沒用到——每個題目變體最後都由學徒自己過關。

## 壞候選被擋：次數與原因

16 份學徒候選，10 份被擋、6 份過。

| 關 | 規則 | 次數 | 原因 |
|---|---|---|---|
| ① | json | 5 | 4 次只回一句「我會先查看原型、檢查器…再跑三關」，1 次空字串（見下方發現 1） |
| ① | size | 1 | astra 為了補審查意見把測試寫超過 8 KiB |
| ② | answer | 2 | 需求第一版沒寫清楚 budgets 的形狀與「哪些回條算合法」（發現 2） |
| ③ | review | 2 | astra-high 審查退件：回條缺欄位被當成 null＝0；`1e400` 解析成無窮大後輸出崩潰 |

三關都各自擋到真東西；沒有壞候選漏過去（兩份合進來的都另由隊長讀過碼）。

## 題 2 比題 1 有沒有進步

| 比較 | 重問次數 | 學徒 token |
|---|---|---|
| 題 1（sol-high，需求補寫後） | 2 | 35 717 |
| 題 2 帶踩坑（sol-high） | 1 | 20 494 |
| 題 2 不帶踩坑（sol-high，對照） | 2 | 24 228 |

數字往下，但**不能算自我改進的證據**：
- 題 2 兩個變體的失敗全是「只回一句開場白」或空回覆，這是代理那一層的問題（發現 1）；踩坑檔裡雖有一條「先確認 JSON 可解析」，但同樣的開場白在帶踩坑那一組照樣出現。
- 學徒寫的四條踩坑有三條專屬題 1（budgets 形狀、合法回條、缺欄位≠null），對題 2 用不上。
- 每組只跑一次，重問差 1 次在雜訊範圍內。

結論：這套「學徒寫踩坑 → 下一題帶上」的管線能跑通，但這一輪**沒有可歸因的進步**。要量得出來，下一輪需要同類型的多題，並先解決發現 1。

## 四指標（`aos7-metrics job apprentice-node --overhead 1644`）

| 指標 | 值 | 說明 |
|---|---|---|
| 每單 token | 118 045（2 單合計 236 091） | prompt 153 223（代理前置 37 812＋自己 115 411）、completion 82 868（推理 24 848）、cached 4 224 |
| 並行呼叫數 | 最多 3 | 題 2 三個變體同時跑，代理撐住 |
| 收單→結案秒數 | 量不到（2 單都「未結案」） | aos 路徑沒有 author 回條的 closed 標記；上表用每輪牆鐘代替 |
| 重試次數 | 21 | metrics 以 logical 分單，學徒、審查、learn 和各變體都記在 `author/<rid>` 名下，所以「呼叫數−1」被灌大；學徒真正的重問是 8 次（見上表） |

相較 R1 的 CSV 題（每單約 2 562 token、一次就過），寫一個 aos 包每次呼叫約 1 萬 token（候選是好幾個完整檔案），審查每次約 7 千。

## 發現（邊緣狀況）

**1. sol-high 經 LiteLLM 會只交出開場白**：sol-high 當學徒的 11 次呼叫中有 4 次 content 只有一句「我會先…再跑三關」，completion 卻記了 5～6 千 token（推理 2～2.6 千）——答案的本體沒有回到 `message.content`。另有 1 次空字串。astra-high 4 次 0 例。看起來是代理把多段輸出只回傳第一段（`raw.json` 的 `response.choices[0].message` 只有那句）。llmcall 照實交付、三關照實擋下，所以沒有壞東西流出去，但每次浪費約 1 萬 token。

**2. 答案藏起來時，需求單必須寫死輸出形狀**：usage 需求第一版只寫「budgets 的 receipts_used 是…」，沒說 budgets 是陣列還是以名稱為鍵的物件、也沒說壞 JSON 那幾筆的回條算不算「合法回條」。學徒只看得到自己的錯誤輸出、看不到正確答案，三輪都沒過。補兩句話後兩個模型都過了（`27bf06ef`）。

**3. 三關把索引列附加在檔尾**：`INDEX.md`、`modules/README.md` 的檔尾是條列，不是表格，所以新的那一列在畫面上會落在表格外。每次合併都要人搬一次。

**4. 審查人只看一份、不比較**：同一個 `1e400` 輸入，astra 版因為 `allow_nan=False` 會崩潰而被退件；合進來的 sol 版不崩潰，但會印出非嚴格 JSON 的 `Infinity`，審查沒挑出來。審查抓得到「會壞」，抓不到「兩份之間誰更嚴」。這條在已合的 llmdiag 裡仍存在（極端輸入才會遇到），列為已知限制。

**5. 合併後才發現新慣例**：同一天 main 新增了 README 開頭三行的模板（`modules/README-head.md`），學徒寫的 llmdiag README 還是舊的契約卡格式（工具卡規定的也是舊格式）。

## 合了什麼

- `apprentice/usage1_b8891b81` → `156bdfb7`（`packs/usage/`：入口、程式、README、測試 `test_usage_aggregation.py`）。選 sol 版的原因：README 短、指令從 repo 根照抄就能跑；astra 版的 README 把評分用的 `check_answer.py` 寫進給使用者的說明。
- `apprentice/diag1_e8800ec9` → `4f3ddd5d`（`modules/llmdiag/`）。選帶踩坑的 sol 版：三份裡最短，契約卡四段齊全。
- 人工修 `14692f6e`（索引列搬進表格）。
- 沒合的三個 `apprentice/` 分支留著給人比對；要清掉的話 `git branch -D` 由人決定。

## 代定事項（頂層代使用者定，翻案改這裡）

1. usage 需求單（A4 範例）由 A5 補寫兩句輸出形狀，算「修需求」不算「放水」：答案檢查器一個字沒改。
2. aos 路徑的 `--reviewer` 只收 `rules` 或 `file:PATH`；模型審查一律走 `--review-llm`（經 llmcall 記帳），不再直接呼叫 codex。送審前必過 rules，publish 用 `file:` 時也重跑 rules。
3. 兩題各選一份合併（sol 版）；astra 版與不帶踩坑版只當對照、不合。
4. 學徒的 llmcall 帳開在學徒自己的 node（`apprentice-node/budget/llm`），審查與 learn 也記同一本帳。
5. 下一輪建議（只列不做）：查發現 1、索引列插進表格、工具卡改新 README 模板、審查與 learn 分開 logical、aos 路徑補結案標記。
