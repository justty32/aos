規劃夾入口：把四個專案的組織寫法總結成 aos 的 org 範本，並評估 `proto8/templates/` 要不要分成 agents／kernels／orgs（11-23，fable 子 agent 替 eca-aos 做的規劃；只讀、沒改任何現有檔、沒碰活樹）。

# org 範本與 templates 分層（11-23 規劃）

← [2026-11-23](../README.md)｜這個 repo 的 org：[wf/org](../../../../../wf/org/README.md)

## 使用者原話（11-23，逐字；出處 [eca-aos 筆記](../../../../../wf/ws/eca-aos/notes.md)「2026-11-23 16:10」）

> 對了，wf/org這塊，去看看/mnt/c/code/mine/arena_cheater, mine/paper_readings, mine/mecha_srpg，去總結一下，弄進template。template這邊你看看，是不是考慮把它分成templates/agents, templates/kernels, templates/orgs

eca-aos 的讀法：前半句是「去做」（總結成範本），後半句是請我們評估、由他拍板。我照這個讀法做，沒有覺得讀錯。補一點：`mecha_srpg` 實際的夾叫 `mecha-srpg`，它沒有 `wf/org`、也沒用 aos。

## 結論

1. **四個樣本，真正有 org 的是三個，骨架是同一副**：一份入口（成員表、標準流程、東西放哪）、一張張四段的角色卡（職責、讀寫範圍、交接、模型）、一套寫信的規矩（五種狀態、開工信寫什麼、回信要短）、一個只跟使用者說話的協調者、「定義只指向角色卡」。`mecha-srpg` 是上一代的寫法，有這些零件的原型。
2. **三個不一樣的地方是九個各自獨立的選擇**（協調者的身體、常駐還是按需、照什麼切、誰 commit、怎麼審查…），不是「小型工作室」「多部門」兩種套餐。
3. **所以 org 範本建議長這樣**：一副骨架（入口、東西放哪、信、負責人的卡、空白卡）加一份九題的選擇題，加幾樣選用件；不附現成的 agent 定義，只附一段指向角色卡的系統文字；內容英文。初稿 13 個檔在 [draft/orgs/](draft/orgs/README.md)。
4. **templates 分層，推薦只新增 `templates/orgs/`、其餘不動**。`kernels` 那一類已經有了（叫 `templates/kernel/`）；`agents` 那一類搬的是執行期的位址：這棵樹四隻 agent 的定義、arena_cheater 七份定義都指著 `templates/eca-claude`、`templates/agent-fsm`，搬了要每棵活樹停下來改，而且沒有過渡期。三類也只收得下現有 14 夾裡的 7 夾。
5. **以上都是推薦**。要使用者拍板的五題在 [04](04-要問使用者的題目.md)；他答之前不施工。

## 導覽

| 檔 | 內容 |
|---|---|
| [01-四個樣本的總結](01-四個樣本的總結.md) | 對照表；都有的、只有大的有的、互相矛盾的 |
| [01a](01a-樣本-arena_cheater.md)、[01b](01b-樣本-paper_readings.md)、[01c](01c-樣本-mecha-srpg.md)、[01d](01d-樣本-aos.md) | 四個專案各一份：規模、身體、怎麼切、角色卡、信、定義、地盤、資產、踩的坑，每條附出處 |
| [02-org範本的設計](02-org範本的設計.md) | 檔案樹、哪些是骨架哪些選用、為什麼不附定義、跟 kits／起手範本／daemon-sub 的關係、抄過去要改哪幾處、語言 |
| [draft/orgs/](draft/orgs/README.md) | 範本初稿全文（英文）：類別的 README、骨架 `basic/` 六個檔、選用件 `extras/` 六個檔 |
| [03-templates分層](03-templates分層.md) | 現有每一夾歸哪一類、三個選項、推薦 |
| [03a-搬動代價的盤點](03a-搬動代價的盤點.md) | grep 的數字：程式寫死的、範本互相引用的、測試、知識庫、wf、活樹與別的專案 |
| [04-要問使用者的題目](04-要問使用者的題目.md) | 五題，每題有選項、後果、推薦 |
| [05-施工清單](05-施工清單.md) | 依答案分支：誰做、先後、怎麼驗 |
| [06-switch](06-switch/README.md) | 明早切換要用的補丁、腳本與預演紀錄 |

## 沒讀到、沒驗到的

- **別棵樹的表沒查**（`~/aos-home` 的根、`mine_arena`、`eca_main`、家機那棵）：任務規定不讀別棵樹的 stack。03 裡「別棵樹多半也記著 `templates/eca-claude`」是照範本 README 教的掛法推的，不是看到的。
- **這棵樹只看了最上層那張表裡的定義路徑**（`~/repo/aos/.stack/procs_state.json`，只取含 `templates` 的路徑、跳過環境變數的欄）；子層的表沒看。
- 三個專案只讀了文件與定義檔，沒讀任何 stack、信箱、history。arena_cheater 的 `org-retro-1/dev.md`、`qa.md`、`org-retro-2/dev.md`、`qa.md` 四份回顧原文沒讀，只讀了兩輪的 README 摘要與 `org-retro-2/review.md`；`multi-agent-roles.md` 只讀了前三分之一。
- paper_readings 的試行還在進行（我讀的時候查核報告還沒出現），它最後學到什麼沒辦法寫進來。
- 範本初稿的英文沒有第二個人看過，也沒有拿真的專案試抄一次；測試還沒寫（05 第 2、4 步）。
- 乙選項「kernel 範本搬了活樹不會斷」是照「樹裡的是抄本」推的，沒在任何一棵樹上驗。
- `templates/tests`、`py/tests` 一支都沒跑（只讀；規劃不改東西）。
