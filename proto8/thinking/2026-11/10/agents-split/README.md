# agents-split（11-10 晚）：把 `agents` 工具拆成三塊

← [11-10](../README.md)

舊的 `agents` 一支包了六個動作、20 個參數、混了四支指令。使用者要它拆開。這夾只留原話、決定、結論。

## 使用者原話（逐字）

- 今晚的通則（self_tools）：「我原本想說，這支工具就是aos-agent tools的包裝，只是目標改自己」；路徑限制「A，拿掉限制」；不認得的鍵「那就報錯」。
- 頂層攤 agents 現況（六個 op：add／new／say／ask／rm／ls；自加規則：只能管自己生的、配額預設 4、new 只能寫在工作區、記血統）並問六點（不是包裝而是四支指令混合、20 個參數；少了 stop／start／sleep／wake／pause／resume／state；生完不能再調；限制要不要拿掉；rm 一律 purge；new 還要不要）。使用者：
  1. 「首先是我希望拆成幾大塊：掌管子agent的管理與生滅，掌管agent定義的創造修改，掌管與其他agent的交流」
  2. （頂層就三塊各問細節）「第一塊：這又可以拆成兩項，一個是具生殺大權的子agent，另一個是普通的aos-agent ctl add(能不能成要看自身權限)，起來後不管。具備生殺大權的才能在出生後調整子agent的東西。第二塊：同樣拆兩塊，一個創造或修改定義，一個改自身。啥定義都可改，只要有權限，包括改自身定義。粗細的話，先做粗的，細的之後慢慢添加，也可以分開做。血統記錄...可以先不做。 第三塊這邊先不要動，我下一篇來講」
     （「粗的」＝頂層描述：這塊只做「複製範本成新定義」與「檢查定義合不合格」，改內容用一般的 write／edit／json_edit 工具；「細的」＝設 system prompt、設腦、加減工具這類專門動作。）
  3. 頂層確認三點：① 2b「改自身」＝今晚在做的 self_* 一家（self_tools、self_llm、self_history、self_hook：改正在跑的這一隻自己那份、不動定義）；② 1a 的「大權」＝工具自己記帳（用 1a 生的記帳、歸我管、算配額；用 1b 掛的不記帳、不算配額、之後碰不了）；③ 1a 出生後用什麼調子 agent 的東西（頂層提：底層指令 `aos-agent tools／llm -t 名字` 本來就收目標，1a 多開「目標是我的子 agent」的入口）。使用者：「1.對 2.對 3.讓規劃者提案」
  4. 第三塊：「就是說，aos-say/listen目前是接近於直接存取history，這對於agent來說是底層工具，並且我希望這是偏向於獨屬於使用者的。如果要讓agent使用的話，我會希望只讓他能夠對子agent做。至於真正的agent間交流，我打算去看看a2a協議，或是用aos-post實現wf/inbox協議」
  5. 「然後這幾塊功能，可能要拆成幾個tool，命名好後讓我看看」（A2A／inbox 的功課：「不用，我自己看」）
  6. （看過拆法與命名提案）「拆分的名字，建議用agents_* 當前綴」
  7. （接著補）「agent_def」
  8. （頂層問：A 三支都 `agent_`／B 只有定義那支叫 `agent_def`、另兩支維持 `agents_`）「B」
  9. eca 驗收：「要驗收的話可以用eca，不用怕燒額度，haiku隨便用。我發現額度掉太快會說。」
  10. （看到 1b 的名字）「agents_add...沒有rm？」；頂層攤兩案（A 維持只管掛；B 改成普通的 ctl 包裝、對象是表上任何一隻、不記帳、名字也換，代價是能移除別人生的 agent）：「B」；接著補：「有權限就能做」
- 配額（11-05）：「工具自己有紀錄，會看到說超過四個，直接回error」。

## 決定

- 三大塊：① 子 agent 的管理與生滅；② 定義的創造修改；③ 跟其他 agent 交流。
- ① 再分兩項：1a 有生殺大權的（工具自己記帳、算配額、出生後能調子的東西）；1b 普通的 `aos-agent ctl add`（成不成看權限、起來後不管、不記帳）。
- ② 再分兩項：2a 創造或修改定義（哪份都能改、含自己的定義，看權限；先做粗的：複製範本成新定義、檢查合不合格；細的之後加）；2b 改自身＝self_* 一家（別隊在做）。
- 1b 改成 `aos-agent ctl` 的完整純包裝（第 10 句）：ctl 有的動作都給、對象是表上任何一隻、成不成看權限、不記帳不算配額。跟 1a 的差別＝1a 記帳與配額、只對自己生的、能 say／listen／ask、能調子的工具／腦／歷史／hook。
- 血統先不做。
- ③ 不動、不設計；say／listen 是底層、偏使用者專屬，agent 要用只能對自己的子 agent。
- 工具名字用 `agents_` 當前綴：1a `agents_children`、1b `agents_ctl`（名字是頂層舉例、使用者沒另指定，可翻案）、2a `agent_def`（使用者第 6～8、10 句）。拆法、動作、入口、代定清單使用者沒提異議。

## 檔

| 檔 | 內容 |
|---|---|
| [01-拆法與命名](01-拆法與命名.md) | 拆成哪幾支、每支動作一覽、1a 調子 agent 的入口、代定清單（名字已照使用者改成 `agents_*`） |
| [02-施工單](02-施工單.md) | 三支的介面細節、要刪要換的清單、驗收 |
| [03-驗收結果](03-驗收結果.md) | 假腦九個情境、gemma-4-e4b、eca（haiku）實跑結果、怪處清單、試驗場刷新要注意的 |
| [04-知識庫節點](04-知識庫節點.md)＋[04-agents.json](04-agents.json) | 交 json-memory 隊：`knowledge/aos/agents.json` 整份換成的新內容（agents_children、agents_ctl、agent_def、thought）、根表與其他節點要改的句子、tooldef 的 Details 指標建議 |

## 結論（11-10 晚施工完）

- 三支在 `proto8/lib/agent/`：`agents_children`（1a）、`agents_ctl`（1b）、`agent_def`（2a）；舊 `agents` 已刪，範本改登記三支，配額設定檔改名 `children.json`。
- 1a 調子 agent：`agents_children` 的 `tools`／`llm`／`history`／`hook` 四個動作，`args` 就是 self_* 收的東西；做法是用子的 `$AOS_STACK` 跑旁邊的 self_*，self_* 沒改。
- 驗收：單元測試全綠、假腦九情境全過、haiku 全過。gemma-4-e4b 寫不出 `$` 開頭的鍵（`{"$env": …}`），所以 `agent_def new` 加了 `template`（內建範本的名字，例 `"agent-fsm"`），加完 gemma 三題都寫對。

## 代定清單（可翻案）

1. 1b 的名字 `agents_ctl`（頂層舉例，使用者沒另指定）。
2. 2a 另開 `agent_def`、不改原本只讀的 `lib/aos/defs`（check 轉叫它）。
3. `agents_children` 的 rm 預設留 stack、`purge: true` 才刪（跟 `ctl rm` 一致）。
4. add 不再順手收 `llm`／`tools`／`tools_rm`，出生後用轉手動作調。
5. `ask` 留著（say＋listen），另有 `listen`；什麼期限都沒給＝等 600 秒。
6. `agents_children` 的 ls 只列我生的；要看整張表用 `agents_ctl` ls。
7. 配額設定檔 `agents.json` → `children.json`，預設 4 不變。
8. 血統：寫的那半隨舊工具拿掉；`lib/aos/defs` ls 遇到既有的 `lineage` 照印。
9. 公開子帳（ask／listen／rm 時抄子的觀測帳）留著。
10. 三支都登記進 `agent-fsm`、`eca-claude` 範本。
11. `agent_def new` 照 `cp -r`：`tests/` 一起抄（只略過 `__pycache__`）；從 agent-fsm 抄出來 200 KB、其中 tests 76 KB。
12. `agent_def new` 的 `template`（範本短名）——給寫不出 `$` 鍵的小模型一條路。
13. 子還在排隊時叫轉手動作＝新代號 `ChildQueued`。
14. 下層句子裡教 CLI 的寫法（`aos-agent ctl start --target …`、`--purge`、`--replace`、撞名的 `--name`）在給腦的結果裡換成工具參數的寫法。
15. add 的 `ws` 給了又不在＝先建（舊行為）。

## 留給使用者

- 4096 context 裝不下範本全部工具的說明（現在 15 支約 7600 tokens；三支新工具加 wall_clock 約 2400）。小模型要嘛少登記幾支、要嘛說明再瘦——方向沒定。
- self_tools、self_hook 的 `path_json` 也是 `$` 鍵，gemma 一樣寫不出（別隊的工具，沒動）。
- `agents_ctl` 能 rm 別人帳上的子（使用者選 B 時已知的代價）；被 rm 的那隻，原主下次對帳自己忘掉。
- `eca-claude` 範本 check 不過（缺 `README.md` 與 `_metainfo.json`）；`lib/aos/defs` 對單一定義三個怪處（路徑一律顯示 `.`、資料夾自己的名字不查、空資料夾算過）——沒動。
- 條文沒改的：C-42 續（第 5、13 行還在講舊 `agents` 的 new／add 與 `ws`）、C-52 例外 ⑧「`agents` 成功時轉印 warning」可能已不適用——改了會動到條文意思。

## 之後可加

「細的」定義動作（設 system prompt、設腦、加減工具寫進定義）；`agents_children` 對 rm 後留下的 stack 直接清掉的動作；血統。

