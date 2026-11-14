結論：全景的「部門」不是獨立型別，而是有孩子的組織節點；可無限嵌套，但組織歸屬不等於 kernel 請求路由。董事長指令已有 `expand`／`hire`／`power` 三種送信入口；`power` 已留 `priority`、`quota` 欄位，尚不是額度分配機制。以下只列查得的事實，不做設計判斷。

已讀必讀：aos `_description.json`（最先）及其目錄 index、`AGENTS.md`、`common/user.md`、`dispatch/aos-teams.md`、aos-teams 的 06／07；另讀知識庫 `kernel.json`。

## 一、部門模型

### 定義與 agent 的對應

- 部門＝樹上任何有孩子的節點，不另設一種「部門」型別；主管就是該節點自己。主管本人狀態放 `self`，整個部門狀況放 `rollup`。來源：`proto8/thinking/2026-11/14/view-1114/02b-fable稿-部門與空間.md:53`、`proto8/thinking/2026-11/14/view-1114/02b-fable稿-部門與空間.md:123`。
- 現有對應是：使用者＝董事長；`repo-aos`＝董事長秘書，也是一個部門節點；各線 opus eca＝主管；sol／astra＝員工；小助手＝部門秘書。來源：`proto8/thinking/2026-11/14/view-1114/02b-fable稿-部門與空間.md:30`。
- 按性質分類用選填 `tags`，只上色、篩選，不改父子關係、不另算彙總。第 6 題「照樹自己長」已獲採用。來源：`proto8/thinking/2026-11/14/view-1114/02b-fable稿-部門與空間.md:57`、`proto8/thinking/2026-11/14/view-1114/03-計劃.md:244`。

### 資料長相：須區分設計稿與已上線格式

- 第二輪設計稿是平的節點表，不是巢狀 JSON：外層包含 `schema:"view-tree/2"`、`rev`、`generated_at`、`tree_down_since`、`root`、`nodes:{id:node}`。來源：`proto8/thinking/2026-11/14/view-1114/02b-fable稿-部門與空間.md:172`、`proto8/thinking/2026-11/14/view-1114/02b-fable稿-部門與空間.md:182`。
- 節點欄位包含 `id`、`kind`、`body`、`name`、`parent`、`parent_by`、`slot`、`tags`、`self`、`rollup`、`children`、`aide`、`marks`、`seen_at`。`kind` 可為 `agent/proc/daemon/external/group`；`body` 可為 `eca/fsm/exec/daemon/http/virtual`。來源：`proto8/thinking/2026-11/14/view-1114/02b-fable稿-部門與空間.md:75`、`proto8/thinking/2026-11/14/view-1114/02b-fable稿-部門與空間.md:113`。
- `self` 記本人燈號、原因、程序狀態、一句話及其來源；`rollup` 記自己與所有後代的燈號、節點數、在跑數、待決數等，由固定程序計算、不經模型。來源：`proto8/thinking/2026-11/14/view-1114/02b-fable稿-部門與空間.md:117`、`proto8/thinking/2026-11/14/view-1114/02b-fable稿-部門與空間.md:127`。
- Argon 採納後有兩項重要修正：`self.light` 只看主管本人，部門問題算在 `rollup`；小助手只放 `aide`，不進 `children`、不佔座位、不計入「底下還在跑」。來源：`proto8/thinking/2026-11/14/view-1114/05b-採納表-第二輪.md:10`、`proto8/thinking/2026-11/14/view-1114/05b-採納表-第二輪.md:11`。
- 第 0 期實際上線記錄仍是 `view-tree/0`，每層有同一套 `light why rollup{worst,nodes,path} tags`；文件說 `view-tree/2` 是它的超集、之後再長過去。不能把完整第二輪 schema 當成已上線契約。來源：`proto8/thinking/2026-11/14/view-1114/03-計劃.md:256`。

### 與 kernel 樹的關係、嵌套

- 備料明確分開三種關係：請求路由＝`AOS_KERNEL`／gate `next`；subagent 所有權＝父的 subagents 名冊；daemon 管轄＝daemon 的 proc 表。沒有一處列出全樹。來源：`proto8/thinking/2026-11/14/view-1114/01b-備料-部門與空間介面.md:74`、`proto8/thinking/2026-11/14/view-1114/01b-備料-部門與空間介面.md:78`。
- 第二輪設計以「歸屬」為骨幹：宣告 → subagent 紀錄 → 名字前綴；daemon 管轄兜底；請求路由只作標記／虛線，不作組織骨幹。來源：`proto8/thinking/2026-11/14/view-1114/02b-fable稿-部門與空間.md:150`。
- 備料當時已發現路由樹與所有權樹不一致：ok-view、ok-pilot 沒有 `AOS_KERNEL`，其 sol 沒經頂層 gate。這是當時蒐集記錄，不是本次重查活樹的結果。來源：`proto8/thinking/2026-11/14/view-1114/01b-備料-部門與空間介面.md:79`。
- 實際上線的父子判定順序為 `config.parents` → subagent 紀錄 → 名字前綴 → `parent_rules`；遇環剪斷。`children` 可無限層。來源：`proto8/thinking/2026-11/14/view-1114/03-計劃.md:256`。
- 可把任意節點指定為 `parent`，因此部門裡能再有部門；`report.facts.members[]` 只列直屬孩子。來源：`proto8/thinking/2026-11/14/view-1114/02b-fable稿-部門與空間.md:61`、`proto8/thinking/2026-11/14/view-1114/02b-fable稿-部門與空間.md:184`。

## 二、董事長指令入口與標記

### 計劃中的入口

計劃原文：

> 三件都走同一個形狀：**頁面只送一張「董事長指令」，接單的是一個部門（agent），頁面不自己動手**。這樣頁面永遠只有「送話、送信、答題」三種寫入，授權照舊（不開 stop／rm／push）；真正動樹的事由接單的部門走 gate。

來源：`proto8/thinking/2026-11/14/view-1114/03-計劃.md:268`。

流程為 `POST /api/order {kind,target,what,...}` → 一封 `REQUEST` 信，body 加 `order`、回覆到中轉信箱 → 接單者處理 → 回信出現在「往來」與部門卡。來源：`proto8/thinking/2026-11/14/view-1114/03-計劃.md:271`。

| kind | 接單者 | 計劃欄位 | 來源 |
|---|---|---|---|
| `expand` | 該部門主管／target 本人 | `target`、`what`、`budget?` | `proto8/thinking/2026-11/14/view-1114/03-計劃.md:278` |
| `hire` | HR；未設時 `repo-aos` | `target`、`role`、`model`、`count`、`why` | `proto8/thinking/2026-11/14/view-1114/03-計劃.md:279` |
| `power` | llm kernel 上層；未設時 `repo-aos` | `target`、`priority`、`quota?`、`why` | `proto8/thinking/2026-11/14/view-1114/03-計劃.md:280` |

`power` 那一列原文：

> | `power`（電力：llm 額度） | 電力部門（之後的 llm kernel 上層；沒設就寄給 repo-aos） | `target`、`priority`、`quota?`、`why` | 機房區的「電力」卡：各部門用量（有正式介面才顯示，否則 `not recorded`）＋調整申請 |

來源：`proto8/thinking/2026-11/14/view-1114/03-計劃.md:280`。

### 補查開發副本：實際格式

因指定的計劃檔沒有具體標記字串，我另唯讀查看它列出的開發副本，未讀活樹程式。

- `GET /api/orders` 回傳三種 kind、接單者、額外欄位；`POST /api/order` 共用 `kind`、`target`、`what`，額外欄位為 expand 的 `budget`、hire 的 `role/model/count`、power 的 `priority/quota`。來源：`/home/lorkhan/code/view-1114/aos-view/API.md:51`、`/home/lorkhan/code/view-1114/aos-view/API.md:52`。
- `why` 沒有獨立寫入實作的 `order` 物件；理由與需求放共用 `what`，前端提示為「要什麼、為什麼」。來源：`/home/lorkhan/code/view-1114/aos-view/aos-view:1591`、`/home/lorkhan/code/view-1114/aos-view/ui/v1/app.js:637`。
- 額外欄位實作為非空時轉字串、截到 200 字；`priority` 前端只是文字輸入，提示「優先級（高／中／低）」，不是已定義的排程 enum。來源：`/home/lorkhan/code/view-1114/aos-view/aos-view:1592`、`/home/lorkhan/code/view-1114/aos-view/ui/v1/app.js:630`。
- 信件帶 `from:"user"`、`status:"REQUEST"`、`via:"aos-view"`、`order`，透過 `aos-post send --reply-to <中轉信箱>` 寄出。來源：`/home/lorkhan/code/view-1114/aos-view/aos-view:1542`、`/home/lorkhan/code/view-1114/aos-view/aos-view:1552`。

### 所有 `[董事長指令:xxx]` 標記

程式只有一個共用標題模板，原句：

```python
"title": "[董事長指令:%s] %s：%s" % (kind, target, short(what, 80)),
```

來源：`/home/lorkhan/code/view-1114/aos-view/aos-view:1598`。

依程式允許的三個 kind，會生成以下三種標記；這是模板展開，不是假稱找到三封實際指令：

- `[董事長指令:expand]`
- `[董事長指令:hire]`
- `[董事長指令:power]`

kind 清單來源：`/home/lorkhan/code/view-1114/aos-view/aos-view:1567`。

repo 搜尋到具體 `[董事長指令:power]` 的地方，是線層任務書；原句：

> - 全景的部門模型與「董事長指令」入口：`proto8/thinking/2026-11/14/view-1114/03-計劃.md`（裡面留了 `[董事長指令:power]`）；全景正在做新 UI（ok-view），要接得上。

來源：`wf/temp/ok-llmk2/任務書.md:38`。

狀態上，§11.3 標題仍寫「先留口，不施工」，但後面的進度表已記 `/api/order` 三種單與前端表單於 0.5 期上線；這只證明送單入口，不表示 HR／額度分配部門已完成。來源：`proto8/thinking/2026-11/14/view-1114/03-計劃.md:266`、`proto8/thinking/2026-11/14/view-1114/03-計劃.md:289`。

## 三、全景新 UI 在做什麼

- v1 已獨立凍結為 `view-v1 1.0.0`，8767 繼續使用、只修 bug；新 UI 與 v1 共用後端及 `view-api/0`。來源：`wf/temp/ok-view/任務書.md:114`。
- 新一輪重點是前端使用者體驗：董事長一眼看全局、一層層往下看、下指令與說話、操作順手。後端只補缺 API、不重寫；新 UI 另開 port 或路徑與 v1 並存。來源：`wf/temp/ok-view/任務書.md:115`、`wf/temp/ok-view/任務書.md:120`。
- 必須納入部門／董事長視角、2D 縮放、嵌套、bot 狀態、普通 proc、擴充／HR／電力三種指令、說話／寄信，以及排隊／已讀／已回狀態；另含布告欄、送出後收起、已送出清單、寄更正。來源：`wf/temp/ok-view/任務書.md:121`。
- 任務書仍要求新 UI 規劃完後提方向題與點頭事項，施工另等使用者批准；本次沒有據任務書推斷新 UI 已施工。來源：`wf/temp/ok-view/任務書.md:123`。

## 四、11-14 使用者原話

在指定的 `wf/` 與當日 thinking 目錄，檔名含 advice 的搜尋沒有命中；經 `user-advice` 文字引用找到正本 `proto8/user-advice/20261114.md`。以下逐段照錄。

### 全景管線、部門與嵌套

來源：`proto8/user-advice/20261114.md:5`

> 對了，再派一條線去幫我規劃，關於如何讓我掌握全景。就是說，現在雖然我可以cd到各ws和子ws，利用say/listen跟他們溝通。但這麼多，其實有點麻煩。我想了一個餿主意，就是每個工作團隊(有隊長的，或是自己本身就兼任隊長的)，都跟他們說，請他們盡量聘請一個小助手，可以用sonnet,haiku,terra,luna這種便宜的，根據隊伍工作複雜性而定，讓小助手定期搜集隊伍進度和狀況，包括需要使用者決策的(不要讓便宜模型寫對於使用者的決策請求單，要讓隊伍先準備好，便宜模型就負責傳遞)，統一丟到一個信箱，不是直接丟到使用者信箱，而是一個中轉信箱，然後一個固定程序負責從中轉信箱收取這些，拿去present到網頁上，這樣使用者就看網頁和操作網頁就好。

來源：`proto8/user-advice/20261114.md:7`

> 讓我掌握全景這塊，我這邊還有個餿主意：就像是管理公司一樣，要讓我這個董事長掌握狀況，所以就是分部門這樣

來源：`proto8/user-advice/20261114.md:9`

> 就是說，我們人類使用者，比較擅長3d/2d空間的縮放移動，我可以拉高視角看到各部門，也可以點進去看到各部門內部各員工的狀況(這個比較麻煩，未必一定要做)。

來源：`proto8/user-advice/20261114.md:11`

> 然後這可以嵌套

來源：`proto8/user-advice/20261114.md:13`

> 啊，要看員工狀況，就是用bot模型，他現在處在啥狀態，他過去幹了啥，說了啥。

來源：`proto8/user-advice/20261114.md:15`

> 對，就是這個意思。普通的proc，或許...也可以看到狀況？

### llm kernel 上一層、電力、優先級、需求、額度

來源：`proto8/user-advice/20261114.md:19`

> 好，等好了我就加上這個自己重啓。然後等這邊差不多了，就該來開始規劃基於llm kernel之上的下一個層級的llm kernel了，我先說想法，先別開始做：同樣用公司部門這塊來切入，llm呼叫是一種資源，每個部門有其優先級，也會有需求和額度分配，所以這個下個層級的llm kernel搞不好...或許算是電力部門，畢竟LLM算是agent公司的基礎設施了

### 擴充部門、HR 增派人員

來源：`proto8/user-advice/20261114.md:25`

> 好，全景這塊希望能儘快，我真的覺得現在太低效了...而且我還有好多想法，比如我可以指定要擴充啥部門，還有要增派人員時候的HR部門等。

### 全景先可用、說話寄信、前後端分離

來源：`proto8/user-advice/20261114.md:29`

> 都按照推薦。好，就先做小的，可行的，總之先讓我有一個能脫離一堆cd的東西。然後先不用手機。

來源：`proto8/user-advice/20261114.md:31`

> 全景真的得快點上線了，不然整個都很低效...

來源：`proto8/user-advice/20261114.md:33`

> 最好還要有對隊伍說話的功能

來源：`proto8/user-advice/20261114.md:35`

> 全景這塊，我希望我能說話和寄信。網頁的技術棧可以隨意，順手就好。考慮到這個網頁以後還會承擔一大堆東西，有需要的話可以切成後端前端

### 公司部門新 UI

來源：`proto8/user-advice/20261114.md:39`

> 然後目前的全景已經很好用了。希望能把版本獨立成一套。然後接下來的公司部門那個概念，可以的話需要重新規劃一整套UI，後端邏輯倒是應該還好。

來源：`proto8/user-advice/20261114.md:41`

> 對，就是前端的使用者體驗這塊

### 後續允許開始規劃，但電力只是比喻

來源：`proto8/user-advice/20261114.md:51`

> 好，開始。啊不要被限縮於"電力"這個概念，這只是一個比喻，一個可以參考的，一個我這個使用者主觀認定的，規劃途中可以改進乃至推翻。然後沙箱這塊可以走這條。我睡前關機前使用這條，可以放在桌面提醒我

### 工作線的優先順序

這是「開發工作的優先順序」，不是部門 llm 排程數值。

來源：`proto8/user-advice/20261114.md:55`

> 然後我們的權限體系感覺快要好了，感覺可以開始來規劃借用linux uid, 存取權限等方式，來讓整個aos體系更安全了。這是個大工程，可以慢慢來，並且不要擋到ok-release線。

來源：`proto8/user-advice/20261114.md:57`

> ok-release線要先好，這樣我才能開始微調。

來源：`proto8/user-advice/20261114.md:59`

> llm kernel的優先級稍微低一些

## 五、aos-brainstorm 的相關點子

README 是入口摘要；它沒有直接定義部門額度制度，並明記這輪「只發想、不規劃」，實驗尚未跑。來源：`proto8/thinking/2026-11/14/aos-brainstorm/README.md:1`、`proto8/thinking/2026-11/14/aos-brainstorm/README.md:12`。沿它的連結查得：

- 資源定義隨實際使用浮現，各 kernel 可以不同；`_metainfo` 是宣告，各 agent 有私有看法。README 摘要來源：`proto8/thinking/2026-11/14/aos-brainstorm/README.md:7`、`proto8/thinking/2026-11/14/aos-brainstorm/README.md:11`。
- 「人＝慢端點包」點子借用 llm kernel 的 `slots/priority/budget/保留格`，限制每隻 agent 每天問人的題數；另有按既往可理解性扣問人額度的點子。這是人類注意力配額，不是已採納的 llm 部門額度規則。來源：`proto8/thinking/2026-11/14/aos-brainstorm/05-匯總.md:22`。
- fable「人15」提出題目競標：agent 拿自身額度出價，衡量不答會卡多久、代定錯誤的重做成本；同時指出 agent 出價與人認為的重要性可能不同。來源：`proto8/thinking/2026-11/14/aos-brainstorm/03-fable發想.md:32`。
- 人既是被管的資源，也是最上層 kernel，人的一句話可蓋掉排序。來源：`proto8/thinking/2026-11/14/aos-brainstorm/05-匯總.md:30`。
- 資源解讀不必統一：各 kernel 只在自己那一站作判斷，可選擇擋或只記；Argon 也提出各讀者挑自己認識的資源欄位或自行轉換。來源：`proto8/thinking/2026-11/14/aos-brainstorm/03-fable發想.md:153`、`proto8/thinking/2026-11/14/aos-brainstorm/04-Argon點子.md:62`。

與資源觀直接相關的使用者原話：

來源：`proto8/thinking/2026-11/14/aos-brainstorm/00-原話.md:15`

> 新的資源類型這塊...就是說，metainfo和資源確實有着相關聯，確實可以放那邊，作爲一個宣告，然後每個agent都會有自己私有的看法。對，因爲我們的資源定義很自由，大家都可以有自己的看法。lisp/lua這塊也不急，至少等kernel穩定了。

## 六、沒找到／不確定

- 指定的 `03-計劃.md` 沒有逐字 `[董事長指令:power]`；有 `power` 接口表。具體標記出現在線層任務書，真正的產生方式在開發副本共用標題模板。來源：`proto8/thinking/2026-11/14/view-1114/03-計劃.md:280`、`wf/temp/ok-llmk2/任務書.md:38`、`/home/lorkhan/code/view-1114/aos-view/aos-view:1598`。
- 沒找到已送出的真實 `power` 指令原信；因此沒有可照錄的實際 target、priority、quota 值。本次只確認格式，不讀活樹信箱。
- 所讀部門 schema 沒有正式的 `priority/demand/quota` 欄位制度；目前相關資訊只見於使用者構想與送單入口。`quota` 的單位、週期、上下層加總規則未在這些材料定義。來源：`proto8/thinking/2026-11/14/view-1114/02b-fable稿-部門與空間.md:75`、`proto8/thinking/2026-11/14/view-1114/03-計劃.md:280`。
- 部門 llm 用量的正式讀取介面，在計劃查證時尚不存在；使用者選只走正式介面，所以頁面看不到時應寫 `not recorded`，不能把備料提到 stack 內有帳視為可直接讀取。來源：`proto8/thinking/2026-11/14/view-1114/03-計劃.md:190`、`proto8/thinking/2026-11/14/view-1114/03-計劃.md:244`、`proto8/thinking/2026-11/14/view-1114/03-計劃.md:280`。
- 02b 曾假設 llm-gpt 是另一個 daemon，後續實測已更正：它是主樹上的 proc，放機房區；單次 `llm_*` 工作者合併計數。本次未另外驗證當前活樹。來源：`proto8/thinking/2026-11/14/view-1114/03-計劃.md:191`、`proto8/thinking/2026-11/14/view-1114/05b-採納表-第二輪.md:12`。