# 2026-11-05 夜 知識庫的增刪改與多庫（knowledge-write，K7，fable 規劃；W1～W4 已實作）

← [thinking README](../../../README.md)｜日 [2026-11-05](../README.md)｜前情：[agent-knowledge](../agent-knowledge/README.md)（memory 工具、`knowledge/aos`、五題裁定、[01 鎖協議草稿](../agent-knowledge/01-層級式記憶工具.md#預留給增刪改這輪不做另派-fable)、[03 K7](../agent-knowledge/03-接進agent與工具說明.md)）、[arch-refactor](../arch-refactor/README.md)（搬夾後的新路徑，本夾一律用新路徑寫）、[no-pid](../no-pid/README.md)（除 daemon 外不靠 pid）｜原則：[C-52、C-56、C-64、C-66、C-68](../../../../docs/CONCEPTS/01-設計理念.md)、[N-05](../../../../docs/NORMS/01-總則/01-N-05.md)、[N-15](../../../../docs/NORMS/05-基礎設施-窗/04-N-15.md)、[lib 契約](../../../../lib/docs/01-分層等.md)、[wf/STRUCTURE 四級成長](../../../../../wf/STRUCTURE.md#一個工作流的成長軌跡四級)

狀態：**W1～W4 已於 11-07 實作（`f95cffb2f`，含 `memory_write`）；同日 `fbf75b026` 補修 JSON 葉與資料夾並發寫入，W5～W6 待做。**本檔照 [user/03](../../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)：原文（逐字）、已定、代定（可翻案）、留給他的題。

## 使用者原文（逐字；11-05 下午～夜）

> 現在是查詢需求，等需求有了後，後續我們還可以再讓fable去規劃增刪查改，也就是相關工具用來增加記憶、刪除...等等。並且這套知識庫還可以給多個agent共享！

裁題 2（併發）：

> 自行承擔風險。但可以弄個協議，也就是要修改的話就放鎖，也不一定要整個庫一個鎖，搞不好也可以只鎖子庫。也可以善用linux權限

> 嚴格來說，沒有庫、子庫之分，資料夾、子資料夾、檔案，本來就是一種資料庫、記憶庫。上鎖，就是跟大家說，這個資料夾我正在修改。檔案的話就rename原子修改(?)

裁題 3（多庫）：

> 不會只有一個知識庫。agent也可以接好幾個知識庫。但是我們現在就先規劃說，一個agent他所使用的memory工具，就是只指定一個知識庫。這樣最方便。後續可以修改這個memory工具，讓他可以接多個庫，只是假裝頂層還是一個庫。

裁題 4（JSON 後端）：「等大了再做 (Recommended)」。11-05 晚：「K7 也派 fable 規劃」。

## 一句話結論

**寫入＝另一支工具 `memory_write`（`add`／`edit`／`rm`），底下就是寫暫存再 rename／mkdir／rm，每次寫前對「要改的那個資料夾」放 aos-lock、寫完就放；能不能寫＝①有沒有配這支工具 ②Linux 權限。多庫＝一個資料夾放幾條捷徑各指一庫，memory 原樣當一庫看（只補 `find` 跟捷徑），不加設定格式。** 四題與一條衝突留給使用者。

## 已定（使用者說的）

- 增刪改要做、有「相關工具」；多隻共享（11-05 下午）。
- 自擔風險；協議＝改哪個資料夾就鎖那個資料夾（任一層）；檔案不鎖、rename 原子蓋過去；Linux 權限當第二層（裁題 2＋補）。
- 一支 memory＝一個庫維持；多庫＝「假裝頂層還是一個庫」（裁題 3）。JSON 後端等大了（裁題 4）。

## 代定（fable 照原則定、可翻案；細節在分檔）

1. 寫入另立工具 **`memory_write`**，`memory` 保持純查詢（agent-knowledge 代定 14 的延伸；C-52：工具清單＝能力清單）。三個 op `add {path, text}`／`edit {path, text}`／`rm {path, recursive?}`；不做 `mv`（[02](02-寫入設計.md)）。
2. 寫法照 N-05：同一個真資料夾裡 `mkstemp` 暫存（不帶節點名）、`edit` 用 `os.replace`、`add` 用 `os.link`（目標已在就 `NodeExists`，不蓋）、留原權限；葉長出子節點時升級 `a.md → a/README.md`（四級成長；先建好 `.new.*` 再 rename 再刪舊葉，沒有空窗）；刪資料夾節點先 rename 成 `.rm.*` 再刪。細節與實測 [02](02-寫入設計.md)、[04](04-邊緣狀況.md)。
3. 鎖＝每次呼叫自動 `aos-lock acquire --wait-ms 3000 --lease-ms 10000 <要改的資料夾>/`、寫完 release；鎖在 `<資料夾>/.lock/`（memory 看不見）。拿不到＝`LockFailed`。沒有 `lock`／`unlock` op（題 2）。租約 10 秒＝no-pid 之後不看 pid 死鎖也能收。
4. 文的驗證只兩條：第一行 `# 標題`、≤ 8000 bytes（`TextBad`）；`.json` 葉要是合法 JSON。根 `/` 不給改不給刪（`PathBad`；根每次進所有 agent 的 system prompt）。
5. 多庫走捷徑資料夾（[03](03-多庫設計.md)）：只改 memory／memory_export 的 `find` 與定址兩處讓它們跟捷徑；`_memory.json` 的 `base` 仍是一個字串、`AOS_MEMORY` 仍是一個路徑。要在設定裡命名多根（方案 B）是可選步驟。
6. 三支工具共用的「找根、定址、列子節點」收成同層模組 `lib/agent/memory_fs.py`（規則 9 同層模組照 `agent_tool.py` 先例；memory_export 已抄一份、第三份就該收）；JSON 後端之後只換這個模組。
7. 不做 metadata、不做版本：要歷史就把庫放 git（依託現成）。
8. 出廠的 `knowledge/aos` 由人寫；agent 寫自己的庫（題 3）。

## 使用者裁定（11-05 夜，逐字）

> 知識庫這塊都按照推薦

四題＋衝突 1 全照推薦：1 多庫＝一個資料夾放幾條捷徑、各指一個庫，memory 不加設定；2 鎖＝每次寫入自動鎖那一個資料夾、寫完就放（不做 lock op）；3 寫＝另一支工具 `memory_write`、出廠 `knowledge/aos` 不配給 agent 寫、agent 寫自己的庫並用捷徑把兩庫掛成一個；4 不記誰改的、何時（不記 `_meta`，要歷史就 `git init`）；衝突 1＝lib 契約規則 4 照 `agents` 先例加例外「`memory_write` 的沙盒＝知識庫根」、knowledge/aos 的 rules 第 7 條加半句。實作排在大重構之後。

## 要使用者裁的（白話；推薦放第一）

（11-05 夜已裁：全照推薦，見上「使用者裁定」。）

1. **多庫怎麼接？**
   - **一個資料夾放幾條捷徑，各指一個庫；memory 不加設定 (Recommended)**：零格式、`ln -s`／`cp -a` 就是掛卸；只要修 `find` 跟捷徑。代價：根的 README 人寫一句目錄、捷徑是 Linux 限定（已裁）。
   - `_memory.json` 的 `base` 收 `{"名": "路徑", …}`、根的目錄由工具合成：定義裡能寫死、不靠捷徑；多一種格式、多 60 行。
   - 兩個都做：先捷徑，有人要再加 B（[05 W7](05-實作步驟草稿.md)）。
2. **鎖怎麼放？**
   - **每次寫入自動鎖那一個資料夾、寫完就放，agent 不知道有鎖 (Recommended)**：單次寫入不互踩；兩回合之間別人改了＝後寫的贏（你裁的自擔）。
   - 多給 `lock`／`unlock` 兩個 op 讓 agent 宣告「這個資料夾我要改一陣子」（租約 60 秒）：貼你「上鎖＝跟大家說」的原話，但小模型容易忘了放。
   - 不鎖、只靠 rename：同名 add 會互蓋。
3. **誰能寫、寫到哪？**
   - **寫是另一支工具 `memory_write`；出廠 `knowledge/aos` 不配給 agent 寫（人改）；agent 寫自己的庫，用題 1 的捷徑把兩庫掛成一個 (Recommended)**：能不能寫一眼看工具清單；aos 知識不會被一隻 agent 改歪而污染所有人的 system prompt。
   - memory 一支加寫的 op、靠 Linux 權限擋：少一支工具，但唯讀的 agent 會看到寫法去試、撞 `WriteFailed`。
   - 連 `knowledge/aos` 也讓 agent 補：知識長得快，但要有人審。
4. **要不要記「誰改的、何時」？** **不記，庫想留歷史就 `git init` (Recommended)**；或每個節點旁放 `_meta.json`（多一套格式、每次寫兩個檔）。

**衝突 1（lib 契約規則 4 ↔ 寫知識庫）**：規則 4 說工具只在 `$AOS_WS` 裡寫；`memory_write` 寫的是知識庫根（工作區外、由 `_memory.json`／`AOS_MEMORY` 指）。**推薦**：照 `agents` 先例在規則 4 加例外「`memory_write` 的沙盒＝知識庫根，根是定義／人配的、腦不能挑（C-66 指標精神）」；`knowledge/aos` 的 `rules` 第 7 條加半句「透過 `memory_write` 改你的知識庫除外」。不改＝知識庫只能放進工作區，多隻共享就做不到。

## 分檔目錄

| 分檔 | 涵蓋 |
|---|---|
| [01-現況](01-現況.md) | 有什麼積木、搬夾後路徑、現有程式對寫入與多庫的阻礙 |
| [02-寫入設計](02-寫入設計.md)、[02-續](02-寫入設計-續.md) | 三個 op、`text` 規矩、原子寫法、鎖協議；續：權限兩層、同像性（JSON 後端接口）、錯誤代號、description |
| [03-多庫設計](03-多庫設計.md) | 捷徑資料夾當掛載表（A）、設定命名多根（B）、根與路徑、find／export 跨庫、寫入落在哪 |
| [04-邊緣狀況](04-邊緣狀況.md)、[04-續](04-邊緣狀況-續.md) | 併發、捷徑與檔案系統；續：設定與搬夾、小模型行為、11-05 夜實測證據 |
| [05-實作步驟草稿](05-實作步驟草稿.md) | W1～W10，每步獨立、有 Done when；哪些等裁題 |
