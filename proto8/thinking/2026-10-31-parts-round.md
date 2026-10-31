# 2026-10-31 parts 組合化與 round 重切：收斂（fable 規劃）

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)｜出發點：[10-31 aos-var § 使用者後補](2026-10-31-aos-var.md#使用者後補10-31-傍晚逐字收回-aos-var改問-parts-能否組出來)（parts 能否用 aos-exec＋`$ref`／`$env` 組出來）、[§ round 重切草圖](2026-10-31-aos-var.md#round-重切草圖10-31-傍晚唯讀-session-推的設計素材待議非行動)（判準四項；使用者「暫時沒啥問題，後續隨需求增加可能再變，先這樣。」）｜使用者原文（不重抄，點過去看）：[parts 的定位（10-31 早）](2026-10-28-agent-round/09-實作時代定.md#10-31-使用者原文parts-的定位)、[先單體按需析出、何時該拆＝檔案系統公民（10-31）](2026-10-30-aos-round/08-10-31-使用者想法-控制流不拉-seq／if.md#10-31-使用者想法控制流不拉-seqif-拼整合成單檔tasksseqif-之後順便做先記之後處理)、[固定名字可以但限縮範圍（10-31，C-51 加註）](2026-10-30-eca/10-10-31-使用者原文-turn-的定義檔只認固.md#10-31-使用者原則固定名字可以但限縮範圍判準)、[round 化作薄殼（10-30）](2026-10-30-eca/11-10-31-使用者想法-turn-改名-把-tu.md#翻案round-化作-aos-round-薄殼10-30使用者澄清)、[turn 批次代定「都按照預設」（10-31）](2026-10-30-eca/13-實作時代定.md#決定10-31)、[格全部走註冊檔（決定 16，10-28）](2026-10-28-agent-ops/02-決定.md#決定10-28)｜條文：[C-48、C-51、C-52、C-56、C-72、C-74](../docs/CONCEPTS/01-設計理念.md)、[C-61](../docs/CONCEPTS/05-agent.md)、[N-36～N-39](../docs/NORMS/07-基礎設施-組合子.md)、[N-45](../docs/NORMS/06-基礎設施-命令列與指示詞.md)、[N-58、N-59、N-61、N-62](../docs/NORMS/10-基礎設施-定義與工作區.md)｜程式：[impls/aos-exec](../impls/aos-exec/README.md)、`bin/aos-parts`、`bin/aos-round`、`lib/agent/round/`、`bin/aos-eca-turn`、`lib/agent/queue/`、[impls/aos-post](../impls/aos-post/README.md)；code map [12-agent-round](../../wf/workflows/common/code-map/proto8/12-agent-round.md)、[06-周邊工具](../../wf/workflows/common/code-map/proto8/06-周邊工具.md)

規矩見 [thinking/README](README.md)。**這份整份是 fable 照原則代定的設計結論、可翻案**；使用者定的在上面各原文。**程式沒動、條文沒動**（CONCEPTS／NORMS 不改）；契約核對是對著 C++ aos-exec 實跑過的（10 個小案，見分檔 01）。要使用者看的只有兩節：[衝突](2026-10-31-parts-round/04-匯流與衝突.md#衝突)（3 條）與 [方向性問題](2026-10-31-parts-round/05-方向題與實作計畫.md#方向性問題)（2 題）。

**狀態：已收斂、待使用者裁衝突 3 條與方向題 2 題；實作計畫寫好、未動工。**

## 決定

本輪沒有新決定（使用者在外）。待使用者：衝突 1～3、方向題 1～2。

## 一句話結論

- **題 A（parts 能否組出來）**：能。parts 現在做的「名字→路徑＋每槽 env＋`$env`／`$ref`」，aos-exec 本來就會（C-72／N-61：JSON 物件當資料夾、`.env` key 放指示詞、字串轉向、`檔#/指標`）——`parts.json` 其實是一份沒長成 aos-exec 格式的 object-as-folder。真的只有程式才做得到的，只剩「註冊檔→固定名字」的查找順序與「沒掛」判定。**結論：格式退成 aos-exec 的格式（約定），`aos-parts` 縮成 `which`／`run` 薄殼**；層級要改口（衝突 1）。
- **題 B（round 重切草圖）**：照四項判準重判，五格不是「四項全弱」——(c) 一格一叫被 ask_round、aos-listen、P-20 從 `state.txt` 接著做、38 案測試吃著；queue 格是外部介面（ask_round 的 push／pop）不該收進單體；兩個佐證一個半成立、一個不足；而且重切會推翻 10-30 使用者「薄殼、迴圈用 loop／fsm」的決定。**結論：不重切、維持現狀**，吸收草圖站得住的一點（`AOS_ROUND_ON_EMPTY` 改 argv `--on-empty`，與 aos-eca-turn 對稱），另訂日後重切的門檻（方向題 2）。
- **匯流**：草圖「round 不用五格 → parts 需求少一大半 → parts 退成約定」這條因果不成立（五格本來就不經 parts；經 parts 的是器官，草圖裡器官照留）；但「parts 退成約定」靠 aos-exec 契約自己就站得住，不必等 round 重切。兩題可分開裁。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../wf/STRUCTURE.md) 按 `##` 標題拆開；本檔留前言、決定、一句話結論與表，各段在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-契約核對](2026-10-31-parts-round/01-契約核對.md) | 契約核對結果（aos-exec 已定的契約、實跑 10 案、aos-parts／round／aos-eca-turn／queue 現況） |
| [02-題A-parts](2026-10-31-parts-round/02-題A-parts.md) | 題 A 結論（逐項對照、新格式範例、代定改口五條） |
| [03-題B-round](2026-10-31-parts-round/03-題B-round.md) | 題 B 結論（四項判準逐塊重判、兩個佐證、代價、結論） |
| [04-匯流與衝突](2026-10-31-parts-round/04-匯流與衝突.md) | 匯流、衝突（3 條：哪條原則、撞在哪、兩邊後果、建議） |
| [05-方向題與實作計畫](2026-10-31-parts-round/05-方向題與實作計畫.md) | 方向性問題（2 題，附背景、例子、建議與門檻）、實作計畫（分步、檔、測試） |

<a id="契約核對結果"></a>
<a id="題-a-結論"></a>
<a id="題-b-結論"></a>
<a id="匯流"></a>
<a id="衝突"></a>
<a id="方向性問題"></a>
<a id="實作計畫"></a>
