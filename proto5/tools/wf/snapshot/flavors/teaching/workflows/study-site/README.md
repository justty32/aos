# study-site — 把知識做成可操作的互動網頁課程（工作流入口）

[WORKFLOWS](../../WORKFLOWS.md)｜[INDEX](../../INDEX.md)

把一個明確的知識面向，做成**可操作、會即時回饋、可循序完成**的互動學習網站。不是把 Markdown 換皮，也不是行銷頁：第一個畫面就要是可用的學習工作台。

**何時用**：使用者說「把這個主題做成互動網頁課程」「弄一個可以操作的教學網站」，而且讀者需要**動手做**才學得會。
**何時不用**：讀者只要讀懂、不需要操作 → [plain-explain](../plain-explain.md)（純文字講解）。網站已存在、只是文字太薄 → [enrich-existing](enrich-existing.md)。內容還沒讀懂 → 先讀懂再回來。

## Done when

- `PROJECT-BRIEF.md` 與 `BUILD-SPEC.md` 存在，且 BUILD-SPEC 的每個互動元件都填滿 `id / type / 範圍 / 預設 / 計算式 / 判準 / 數值實例`（骨架見 [TEMPLATE.build-spec.md](TEMPLATE.build-spec.md)）。
- [quality-gates](quality-gates.md) 的驗收指令片段全數通過（缺 id 0、外部資源 0、相對連結全存在）。
- `驗收紀錄.md` 存在，且每個關卡欄位是「通過／失敗／待人工」其中之一，沒有空欄。

## 必要輸入

1. **主題邊界**：一次只做一個說得清楚的面向，不要一口氣做一整個學科。
2. **讀者基線**：已會什麼、最容易卡在哪裡——格式與填法見 [plain-explain](../plain-explain.md) 的「讀者基線」表。
3. **本地來源包**：權威筆記、名詞對照、必要的相鄰課程。缺什麼先列缺口，別邊做邊查。
4. **可觀察成果**：讀者完成後能做出的判斷、計算、診斷或設計。

四項都要寫進 `PROJECT-BRIEF.md`，**不可只存在對話紀錄裡**。

## 流程

<!-- wf-nav -->
1. **立案**：寫 `PROJECT-BRIEF.md`（骨架見 [TEMPLATE.project-brief.md](TEMPLATE.project-brief.md)），鎖定範圍、完成準則、輸出位置與**不做事項**。同時定下預算（見下）。
2. **內容切片**：把來源拆成「學習目標 → 核心概念 → 常見誤解 → 可操作任務」。每個切片記來源檔與章節；網站不得出現無法追溯的關鍵數值或結論。讀者已是強項的部分只留必要銜接。
3. **互動建模**：每個目標選一種機制（狀態機、參數實驗、排序、故障診斷、取捨比較、階段閘門），並定義「使用者操作 → 狀態變化 → 即時回饋 → 正確性判準」四件事。**沒有判準的動畫、純翻卡、只換頁都不算互動。**
4. **建置契約**：把前兩步整合成 `BUILD-SPEC.md`：資訊架構、DOM 契約、公式、預設值、檔案所有權、驗收方式。**每個 widget 的參數要鎖死到照抄即可實作**——規格留白，下游就會各自發明。
5. **分批派工**：照 [build-with-agents](build-with-agents.md) 分層執行；每個檔案只有一個作者，同一輪的寫入範圍必須互斥。
6. **驗證交付**：照 [quality-gates](quality-gates.md) 逐關驗，結果寫進 `驗收紀錄.md`；要對外發布再走 [publish](publish.md)。

零基礎讀者（看不懂術語、沒有前置模型、回饋「先考後教」）→ 流程 2–3 之間插入 [foundations-first](foundations-first.md) 剖面。

## 產物與落點

產物**放回知識來源所屬的目錄**（例：`{{來源主題目錄}}/互動課程/`），不堆在工作流資料夾裡；工作流檔只放方法。

| 產物 | 內容 | 誰寫 |
|------|------|------|
| `PROJECT-BRIEF.md` | 讀者基線、目標能力、來源、教學邊界、不做事項 | 立案者 |
| `BUILD-SPEC.md` | 靜態結構、教學頁契約、每個互動的完整參數、驗收方式 | 立案者 |
| `派工計畫.md` | 任務編號、角色、唯一寫入範圍、狀態 | 派工者 |
| `建置進度.md` | 建置期間的檢查點（已完成檔、通過的關卡、待修缺陷）；**交付後刪除**，不進版控 | 派工者 |
| `驗收紀錄.md` | 日期、環境、通過項、失敗項、已知限制、是否允許交付 | 獨立驗收者 |

## 預算（先講好，不是做到一半才問）

- **外部查詢預設 0**：先把本地來源讀完。確有缺口就先列缺口清單，再由**單一**執行者串行查證，一批最多開少量一手來源。
- **不下載依賴**：預設原生 HTML／CSS／JavaScript，不用外部字型、圖片、CDN、遠端 API 與第三方執行期依賴；課程要能**離線開啟**。
- 真的需要新增依賴 → 先報名稱、用途、估計下載量與替代方案，取得使用者同意（守鐵律 2：授權來源）。

## 內容

| 檔案 | 內容 |
|------|------|
| [foundations-first.md](foundations-first.md) | 零基礎剖面：多頁結構、先教後操作、自由實驗、拆頁條件、可延續性 |
| [quality-gates.md](quality-gates.md) | 品質關卡 checklist ＋可複製的驗收指令 |
| [build-with-agents.md](build-with-agents.md) | 分層派工產線：token 階梯、單一作者、獨立驗收 |
| [enrich-existing.md](enrich-existing.md) | 只加厚既有課的文字，不動互動與版面 |
| [publish.md](publish.md) | 發布契約：只發成品、單一入口、驗 HTTP 200 |
| [TEMPLATE.project-brief.md](TEMPLATE.project-brief.md)／[TEMPLATE.build-spec.md](TEMPLATE.build-spec.md) | 兩份產物的骨架，複製到產物目錄改寫 |
| `gotchas.md`（長出來才建）| 本工作流專屬踩坑（共通的在 `common/gotchas.md`）|

> 〔導入判斷〕課程是純閱讀型（只有文字與導覽，不做互動元件）→ 流程第 3 步只需定義「每章的自我檢核問題」，`BUILD-SPEC.md` 的互動段寫「不適用」。同步：`workflows/study-site/quality-gates.md` 的「學習有效性」段、`workflows/study-site/TEMPLATE.build-spec.md` 的互動段。

## 交接

- 內容還沒講得零基礎讀得懂 → 先走 [plain-explain](../plain-explain.md)，它的名詞表與概念表直接餵進流程第 2 步。
- 建好之後文字仍太薄 → [enrich-existing](enrich-existing.md)；要對外發布 → [publish](publish.md)。
- 卡在使用者（實機瀏覽器驗收、發布授權、要不要加依賴）→ [WAIT_USER](../../WAIT_USER.md) 一行；跨 session 的建置進度 → [SESSION-LOG](../../SESSION-LOG.md) 一行；為什麼這樣簡化模型 → [decisions](../decisions.md)。
