# 2026-11-05 下午 給 agent 的 aos 體系知識＋層級式記憶工具 `memory`（fable 規劃，工具與知識庫已做、沒改既有程式）

← [thinking README](../../../README.md)｜日 [2026-11-05](../README.md)｜前情：[feat-proto](../feat-proto/README.md)（self_tools、agents、endpoint 包、排程、份額）、[kernel-daemon](../kernel-daemon/README.md)（daemon＝最基礎 kernel）、[portable-flow](../portable-flow/README.md)（image 模型、相對管我的 daemon）｜原則：[wf/STRUCTURE 分層](../../../../../wf/STRUCTURE.md#分層原則)、[C-42、C-46、C-61](../../../../docs/CONCEPTS/05-agent.md)、[C-52、C-56、C-64、C-68](../../../../docs/CONCEPTS/01-設計理念.md)、[N-63](../../../../docs/NORMS/10-基礎設施-定義與工作區.md)、[lib 工具契約](../../../../lib/docs/01-分層等.md)｜程式：[lib/agent/memory](../../../../lib/agent/memory/_entry)（新）、[knowledge/aos](../../../../knowledge/aos/README.md)（新）

狀態：**工具 `memory` 與第一個知識庫 `knowledge/aos` 已做並實測（Haiku 9／9、luna 9／9）；接進三種 agent 與改寫各工具 description 等新功能隊收工後再排（[03 步驟 K1～K8](03-接進agent與工具說明.md)）**；沒動 `lib/agent/self_tools`、`agents`、`extras/agent`、demo 任何既有檔。本檔只記使用者原文（逐字）、已定、代定（可翻案）、留給他的題（[user/03](../../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。

## 使用者原文（11-05 下午，逐字，依先後）

> 齁齁，進度不錯。不過agent要碰這些，需要或多或少的aos體系知識，可能要讓fable去規劃這套。目標是haiku或codex-luna能懂。可以用英文，畢竟AI比較擅長這個，但是要有一份繁體中文的說明給我看。各種工具的說明都可以基於這套aos體系知識，再去額外說明

> hmmm，底層技術細節應該不用贅述，或者說，應該是分層的。想想看我們wf/中的structure.md。頂層可以是簡介、index目錄之類，並且盡量講簡單(ELI5風格？)，然後agent有需要的話，再去透過工具，或是一些其他東西去抽取更深一層的知識(或者是當初在規劃該agent用途的時候，就考慮到它需要這個，然後在定義那邊就給他配上)。喔天啊，看來這就是我們aos體系下，第一個好東西了：層級式記憶工具？現在是查詢需求，等需求有了後，後續我們還可以再讓fable去規劃增刪查改，也就是相關工具用來增加記憶、刪除...等等。並且這套知識庫還可以給多個agent共享！

> fable他可以再開fable去規劃細項！

> 現有的資料夾、檔案系統，本身就是一個很好用的東西，盡量依託於這塊。/usr/bin的ls/grep之類也很好用，我知道我們通常會把shell工具停掉，但這些基本指令也可以包成aos函數&工具來用，可以做為記憶工具的基石。不用重複發明太多東西。json本身與檔案系統也有同像性，可以是檔案系統以外的另一種效能/體積權衡選擇，aos-json可以做為基石。

> markdown, json, yaml之類的格式都可以。"人類可讀性"可以是次要考慮選項，因為人類想看的話，要麼直接問agent，要麼agent弄一份輕鬆轉為markdown/html的工具，把json轉過去也可以。

## 已定（使用者說的）

- 知識分層，照 wf/STRUCTURE 的分層樹：頂層＝簡介＋目錄、盡量簡單（ELI5）、不贅述底層細節；agent 需要時用工具往下抽，或規劃該 agent 用途時就在**定義**裡配好。
- 這就是 aos 的第一個通用元件：**層級式記憶工具**。這輪只做查詢；增刪改另派 fable 規劃，格式與介面要預留。
- 知識庫**多隻 agent 共享**（一個資料夾、多隻指它）。
- 依託檔案系統、包 ls／cat／grep 當基石、JSON 與檔案系統同像（aos-json 當另一種後端）、少重複發明。
- 節點格式 md／json／yaml 都可以；agent 好讀優先、人類可讀性次要（人看＝問 agent，或之後做轉 markdown／html 的工具）。
- 知識英文、給使用者的說明繁中（[05](05-給使用者的說明.md)）；工具說明建立在這套知識上、只寫增量。
- fable 可以再派 fable 規劃細項（這輪派了 opus 寫工具、自己寫知識與設計；沒再派 fable——細項規模還不需要）。

## 代定（fable 照原則定、可翻案；細節在各分檔）

1. 工具叫 `memory`、放 `lib/agent/memory/`；三個 op `read`／`ls`／`find`；知識庫根由 `AOS_MEMORY` 指（相對＝相對 `$AOS_DAEMON`，同 `AOS_LLM_KERNEL`）；腦不能自己挑知識庫（[01](01-層級式記憶工具.md)）。
2. 節點＝資料夾（文在 `README.md`）或葉 `.md`／`.json`；路徑 `a/b`、段名 `[a-z0-9_-]`（跟 aos-json `#/a/b` 同形）；md 第一行標題、下一個非空行＝摘要；一節 ≤ 2 KB；`.`／`_` 開頭不算節點（[01](01-層級式記憶工具.md)）。
3. 第一個知識庫 `proto8/knowledge/aos/`：根（八個詞＋五條規則）＋九節（[02](02-aos知識庫.md)）；`proto8/knowledge/` 是放知識庫的新頂層資料夾（跟 demo、lib 並列）。
4. 根每次都進 system prompt（給 `memory read` 的輸出、含目錄）、其餘按需；三種 agent 的接法與 description 五條規則（[03](03-接進agent與工具說明.md)）。
5. `agents` 工具沒有 `priority` 參數（子 agent 的急件由它自己寄信時寫）——Haiku 實測指出來的，先維持；要加是 feat-proto 件 4 的事。
6. 實測時 `gpt-6-luna` 在公司 WSL 不可用，改 `gpt-5.6-luna`（aos-teams 名單是家機測的；沒改那份文件，等使用者確認是帳號差異還是名單過期）。

## 留給使用者的題（推薦放第一）

1. **知識庫放哪、誰共用**：推薦 repo 的 `proto8/knowledge/` 放「出廠」知識庫，部署時 daemon 定義的 `.env` 寫 `AOS_MEMORY`（絕對路徑或相對 daemon stack）、整台共用；另一條是複製一份進 `ws/`（搬家跟著走，但多份會漂）。
2. **將來可寫時的併發**：推薦整個知識庫一把 aos-lock＋「先寫 `.名字` 再改名」，簡單、夠用；另一條是每節點一把鎖（多隻同時寫不同節不互等，但鎖多）。這輪不實作。
3. **多個知識庫**：推薦 `AOS_MEMORY` 只指一個、要合就在根下開子資料夾（`aos/`、`project/`…）；另一條是 `AOS_MEMORY` 接 `:` 分隔多個根（像 PATH）。
4. **JSON 後端什麼時候做**：推薦等有「一棵很大、很零碎」的知識庫再做（現在十個檔，資料夾夠用）；另一條是現在就讓 `AOS_MEMORY` 認 `.json`。
5. **根要不要固定進 CONVENTION**（「agent 的 system prompt 以 memory 根開頭」）：推薦先當 demo 範本的做法、跑過 K2～K4 再定條文。

## 分檔目錄

| 分檔 | 涵蓋 |
|---|---|
| [01-層級式記憶工具](01-層級式記憶工具.md) | 四條設計原則、`AOS_MEMORY`、節點與定址、`read`／`ls`／`find`、錯誤代號、預留給增刪改 |
| [02-aos知識庫](02-aos知識庫.md) | 根＋九節各教什麼、為什麼這樣寫、用詞表 |
| [03-接進agent與工具說明](03-接進agent與工具說明.md) | 根進 system prompt、三種 agent 怎麼拿、description 五條規則＋範例、步驟 K1～K8（等新功能隊收工） |
| [04-實測](04-實測.md) | 九題、Haiku／luna 結果、改前改後三處 |
| [05-給使用者的說明](05-給使用者的說明.md) | ELI5 繁中說明 |
