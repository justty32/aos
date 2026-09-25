← [notes](../README.md)｜樣板：[examples/company](../../examples/company/README.md)｜規格：[company.md](../../spec/team/company.md)、[market.md](../../spec/team/market.md)｜比喻版：[playbook/company.md](../../playbook/company.md)

# 2026-09-25 組織設計：用 aos 團隊蓋一間公司（＋市場層）

董事的話：「就當做是開公司……我要的是**用我們現有的 aos 體系**去建立這個公司架構。」後來追加：公司要能開 N 家互相競爭，經理人照表現撥額度，花光倒閉、剩兩家合併；倒閉的剩餘額度與名額回總池。

## 1. 做了什麼

| 東西 | 在哪 | 一句話 |
|---|---|---|
| 公司樣板 | [examples/company/](../../examples/company/README.md) | `company.json`（八個部門、兼任、新創上限 10／20／5、擴張頂 100／200／20）、五個部門的真團隊資料夾（hq、mfg、qa、rd、lib 各一份 `team.json`＋門房）、公司層人格 |
| 公司程式 | [lib/aos_company.py](../../lib/aos_company.py)、[company.py](../../examples/company/company.py) | `new`（照樣板生一家、成員名加前綴）／`up`／`down`／`status`（正式 N/10、cpu N/20、llm cpu N/5）／`order`／`mail`／`answer`／`relay` |
| **總機** | 同上 `Switchboard` | 部門之間的往來：成員寄給 human 的信第一行寫 `〔給 mfg〕…` → 開總機單 → 照對方門房開單或寫信給窗口（寄件人 human）→ 回覆照 reply_to／任務單的 request 抄回下單的人。**不叫模型、不改任何團隊規格** |
| 市場層 | [lib/aos_market.py](../../lib/aos_market.py)、[market.py](../../examples/company/market.py) | `open`／`score`／`rank`／`grant`／`bankrupt`／`close`／`pool`／`slots`／`merge`；帳戶直接用財務部的 `aos_team_cost`（cost.md §6） |
| 規格 | [spec/team/company.md](../../spec/team/company.md)、[spec/team/market.md](../../spec/team/market.md) | 新檔，既有規格一個字沒改 |
| 測試 | `lib/test/test_company.py`（22 條）、`test_market.py`（14 條） | 樣板全過驗、開五家不撞名、上限計算、總機行為、假帳本跑排名／撥款／總池／倒閉／合併 |
| 比喻落地 | [playbook/company.md](../../playbook/company.md) | 每一列補「aos 裡是哪個團隊資料夾／哪個成員」 |
| 試玩 | [play/](play/README.md) | 新使用者只拿樣板 README：開一家、下一單（deepseek-chat，343 秒、126 次呼叫、451 萬 token，成功）、關機；市場層假資料走完 open→merge；五條標準 4／3／4／4／4 |
| 審查 | [review-astra.md](review-astra.md) | codex（gpt-6-astra，唯讀）審公司樣板＋市場層：必修 15 條（撥款／合併非交易、封存與回收無鎖、CPU 名額可虛增等）、建議 6 條、可不拍 2 條 |
| 市場真跑 | [market-run/](market-run/README.md) | 兩家（只差寫手 deepseek-chat／gpt-5.5）同時做「補人物 老木頭」：c1 DONE（401 秒、131 次、595 萬 token），c2 FAILED（審查 3 次沒過、45 次、90 萬 token）；走一輪 score→rank→bankrupt→grant：c1 58％、c2 42％；一家一個 daemon 真開機驗過；規則問題 7 條（品質分會顛倒、失敗照拿四成、沒打分也照發） |

### 設計的幾個決定（我代裁的，攤在這）

1. **跨團隊不開新通道**：現有規格一支團隊只認自己的 outbox，但「寄給 human」（落在 `team/human/`）與「human 寄出」（`outbox/human/`，能寄給任何成員、能開單）兩個口本來就有。總機只是在兩個口之間搬，所以郵差、牆、驗收一行都不用改；從對方部門看，總機交辦的事就是「公司（human）」交辦的。
2. **一家一個 kernel**：kernel 的池寫死叫 `default`／`llm`，一個 kernel 裡沒辦法按公司分池；一家一個 kernel（共用一個 daemon），池的大小就是這家的 cpu／llm cpu 上限，是**硬上限**（多的工作排隊）。成員名照樣加公司前綴，萬一共用 kernel 也不撞名。
3. **一律用內建模板＋公司人格**：門房落穿找的是 `template: lead` 的成員；arknights 樣板用自訂模板資料夾 `./templates/lead`，**落穿時找不到領隊**（`NoLead`）。所以公司的經理都用內建 `lead`，專案規矩用 `up` 時 `aos-agent persona append` 接上去（每個家只接一次）。
4. **正式／臨時看名冊的 `employment`（HR 部）**，`company.json` 的 `staff` 只記兼任角色；**上限只有一個來源** `company.json` 的 `limits`，`up` 寫進這家的 HR 政策 `K/hr/policy.json`，HR 的擋點與 `status` 同一組數；**cpu 不含 llm 池**（照 HR 的算法）。給 `aos-team` 的環境不帶 `AOS_DAEMON_HOME`，免得幾家共用 daemon 時 HR 把別家的 kernel 也數進來互相擋。
5. **總裁的 SOP**：補人物先派「只寫詞條」（不動索引、計數），製造 DONE 才派品管，品管 DONE 才回報董事；任一步 FAILED 直接報董事、不自己重派。
6. **開單類的單，負責人自己說的 DONE 不轉**：要等郵差驗收＋審查完寄的那封，總裁才不會在還沒驗過時就叫品管。
7. **commons 一家一份**（`<公司>/teams/commons/`，各部門團隊的上一層＝圖書館部的預設位置）：競爭的公司不共用經驗。

## 2. 新創編制（正式 7／10、cpu 12／20、llm cpu 5／5）

| 部門 | 團隊 | 正式員工（模型） | 兼任／機械 |
|---|---|---|---|
| 總裁辦 hq | `teams/hq` | hq-lead 總裁（gpt-5.5） | 兼業務（門房）、兼 HR 決策 |
| 製造 mfg | `teams/mfg` | mfg-lead 經理、mfg-writer1 寫手、mfg-reviewer 審查（都 gpt-5.5） | 經理可 spawn worker（臨時工，不用批） |
| 品管 qa | `teams/qa` | qa-inspector 檢驗員（deepseek-chat） | eval 的評審＝一次性 claude-opus-5（臨時工） |
| 研發 rd | `teams/rd` | rd-smith 工具匠（gpt-5.5） | — |
| 圖書館 lib | `teams/lib` | lib-librarian 館員（deepseek-chat） | commons 機械審 |
| 業務、HR | 併在 hq | — | 門房規則；`status` 數名額 |
| 財務 | 沒有團隊 | — | 帳本＋帳戶（`AOS_COST_HOME`） |

組織圖全表（掛什麼、收什麼單、交什麼貨、KPI、擴張到 100 長怎樣）在 [examples/company/README.md](../../examples/company/README.md)。

## 3. 真跑（2 次，共約 9 分鐘牆上時間）

環境：`~/tmp/company-run/c1/`（前綴 `c1-`），專案是 `~/tmp/arknights-try` 的 rsync 副本（不帶 `.git`；製造隊同時在 arknights-try 上跑、會 reset，不能共用），帳本 `~/tmp/company-run/cost`。模型全走 LiteLLM `localhost:4000`：gpt-5.5（總裁、製造三人）、deepseek-chat（檢驗員）；沒用到 claude。紀錄：`~/tmp/company-run/c1/runs/run1/`、`run2/`（各部門 score、任務、信、總機單、帳本分組、hops）。

| | 第 1 次：「補人物 老財」 | 第 2 次：「補人物 老木頭」 |
|---|---|---|
| 結果 | **FAILED**：製造部兩次審查都沒過（證據列「礦工與司機仍拉著他」原文只有司機），總裁照 SOP 回報董事失敗、沒派品管 | **DONE**：製造一次過（驗收＋審查），品管抽 3 列「結論：合格」，總裁回報董事 |
| 牆上 | 5 分 12 秒（11:55:41 → 12:00:53） | **3 分 26 秒**（12:02:23 → 12:05:49） |
| 模型 | 37 次、760,104 token（製造 33 次 740,520；總裁 4 次 19,584） | 34 次、890,254 token（製造 19 次 777,183；品管 8 次 74,163；總裁 7 次 38,908） |
| 跳數 | 董事→總裁→〔總機〕→製造（寫手 2 輪、審查 2 輪）→〔總機〕→總裁→董事；跨部門 4 封 | 董事→總裁→〔總機〕→製造→〔總機〕→總裁→〔總機〕→品管→〔總機〕→總裁→董事；跨部門 6 封 |
| 總機單 | o-0001（handoff，failed） | o-0002 製造（2 分 21 秒）、o-0003 品管（21 秒），都 done |

- 總機延遲：每跳 ≤ 5 秒（輪詢間隔）；hops 報告裡時間幾乎都在「等模型」。
- 第 2 次交件事後用品管的機械工具複查：證據 11／11 列原文對得上，機械 6／7（**詞條有兩處行尾空白，驗收與檢驗員都沒抓**）→ 市場層品質分（無評審）＝92.9。
- HR 部併進來後又開關機一次（沒下單、沒叫模型）：五個部門（含剛開張的圖書館）照常 init／start，HR 沒擋；`company.py status` 與 `aos-team hr cap` 都印「正式 7／10、cpu 12／20、llm cpu 5／5」；這家的 commons 建在 `teams/commons/`。
- **真跑抓到的 bug**（已修、已加測試）：郵差放進 `team/human/` 的信多一格 `header`，拿 `validate_letter` 驗會整封被當壞信略過——總機第一輪一封都沒處理。修法：驗之前拿掉 `header`。第 1 次跑的第一封是我手動補跑一輪總機才走下去的（o-0001 比信晚 1 分鐘開）。

## 4. 給董事的問題（一題一題）

1. **五家同跑，llm cpu 加總超過機器上限（5×5＝25 ＞ 20）怎麼辦？** 樣板做法：每家 4（`new --llm-cpu 4`，市場層開戶時會擋總數）。另兩個選項：按排名動態分（第一名 6、最後一名 2）；或允許超賣、大家排隊。**已裁決（董事 09-25 14:20）**：都不選，把機器上限從 20 提高到 25，五家各 5 剛好，不用再降。
2. **額度換算成每家多少？** 現在的參數：開辦費每家 1 美元＋2500 萬 token、每輪總額 2 美元＋5000 萬 token（原本 200 萬／400 萬，試玩後調高，見第 14 題）。gpt 走訂閱、帳本沒價錢（只記 token），建議 gpt／deepseek 用 token 管、claude 用美元管；總量 `total` 要填多少（claude ≤ 一週額度 10%、gpt 本週剩的、deepseek 約 5 美元）請給數字。
3. **每輪多長？** 選項：一次 `order`（一個詞條）一輪；固定一批（例如 5 個詞條）一輪；或按時間（每天一輪）。
4. **排名公式的權重？** 現在品質 0.6、快 0.25、省 0.15；品質門檻 `min_quality` 0（不設）。
5. **品質分要不要叫評審（claude-opus-5）？** 評審每人約 6 萬 token 的 claude 額度；不叫就只用機械＋證據（本次 92.9）。
6. **合併規則可以嗎？** 同部門的經理只留併入方的（被併方經理裁掉）；其餘人改名併進同部門，正式名額滿了改臨時工；筆記帶過去、對話紀錄留在封存。另一種：名額滿了直接裁掉，不留臨時工。
7. **公司之間要不要共用 commons（經驗庫）？** 現在一家一份、不互通（競爭）。
8. **新創期還剩 3 個正式名額給誰？** 候選：第二個寫手、業務專員（把董事的話翻成製造部句型）、HR 專員（跑 `hr trial` 試降級）。
9. **總裁遇到 FAILED 要不要自己重派一次？** 現在：直接報董事、不重派（第 1 次就是這樣停的）。
10. **董事的「補人物 X」預設要不要動索引與計數？** 現在總裁預設派「只寫詞條」（快、不和別的單搶索引）；要動索引得明說。
11. **跨部門要不要開「直接指定負責人與驗收條件」的開單路？** 現在只能走對方門房的規則（命中才開單，沒命中寫信給窗口），想多一種單就在對方門房加規則。
12. **倒閉的公司名額回總池後，經理人要自動撥給第一名，還是一律手動？** 現在手動（`market.py slots`）。
13. **「cpu ≤ 20」算不算 llm 的 5 顆？** HR 部的擋點不算（default 池 20＋llm 池 5，最多 25 顆），財務部的 cost 表把兩池加起來印（「開著 17 個、其中 llm 5」）。公司樣板照 HR 的算法（它是真正擋的那一個），`status` 印 `cpu 12/20、llm cpu 5/5`（`new` 原本印 17/20，已改成同一個算法）。請拍一個，兩邊統一。
14. **開辦費給多少 token？** 試玩真跑一張「補人物 老財」（deepseek-chat）＝126 次呼叫、451 萬 token；舊預設開辦費 200 萬＝一家公司一張單就倒閉。研發部先改成 **2500 萬（約 5 張單）**、每輪總額 5000 萬（約 10 張單）。選項：照 5 張單的平均花費（現在）；照 10 張；或按模型分（gpt-5.5 一張約 89 萬，deepseek 約 451 萬）。總量 `total` 也要跟著給。

## 5. 留下一輪

- **五家真的同跑**：兩家同跑做過一輪（[market-run](market-run/README.md)），五家還沒。要跑就照 [examples/company/README.md〈開幾家〉](../../examples/company/README.md#開幾家市場層)；每家要自己的專案副本。
- 驗收加行尾空白檢查（製造部的單、品管的驗貨單都漏了）；品管驗貨單改跑整套 `mech_check`。
- HR 部的擴編規則（積壓 ≥3、品管分 <80）接到總裁的 SOP；`status` 順便印 `aos-team hr cap` 的擴編理由；薪資表（worker 最低通過 deepseek-chat、lead 換 deepseek 不通過）拿來定各部門的模型——現在寫手還是 gpt-5.5，可以試降。
- `market.py slots` 只改 `company.json`，kernel 開著時不會自己 `aos-kernel cpu add`（下次 `up` 會對齊 K 的池，見 §7）。
- `quality_from_eval` 只認 arknights 評分器的格式。
- 帳本價格表沒有 gpt-5.5、deepseek-chat 的價（只記 token）：財務部的 `prices.json` 要補，美元配額才有意義。
- 總機只認第一行的〔給 …〕與 reply_to：寫錯格式的信留給董事（`company.py mail` 看得到）。
- 部門門房「落穿找 `template: lead`」這條，用自訂模板資料夾的領隊會找不到——建議核心改成「模板名或資料夾名是 lead」（要改 route.md，沒動，攤給董事／研發部）。

## 6. 沉澱

- 經驗 → [playbook/lessons.md](../../playbook/lessons.md) 24～27（總裁辦／研發部／HR）。
- 團隊架構 → [playbook/teams/company-startup.md](../../playbook/teams/company-startup.md)（新創公司：八部門、七個正式員工的編法）。
- 工作流 → [playbook/workflows/company-order.md](../../playbook/workflows/company-order.md)（董事一句話 → 總裁 → 製造 → 品管 → 回報）、[market-round.md](../../playbook/workflows/market-round.md)（一輪市場：打分 → 排名 → 撥款 → 倒閉 → 合併）。
- 可複用工具 → [playbook/README.md](../../playbook/README.md) 索引加 `company.py`、`market.py`。

## 7. astra 必修處理（研發部內核組）

[review-astra.md](review-astra.md) 必修 15 條、建議 6 條、可不拍 2 條，加上試玩員的三件事與董事 09-25「每公司一個 daemon 和 kernel」。每條都有一個「舊程式會紅、修好變綠」的測試（test_market `AstraMust`、`PlaytestFixes`，test_company `RelayAstra`、`KernelPoolSync` 等）；只改程式與規格，不真跑模型。

**必修**（照審查的順序）：

| # | 問題 | 狀態 |
|---|---|---|
| 1 | 撥款崩在逐家途中會重撥；合併崩在 A 加、B 扣之間憑空加款 | 修了：grant／merge 先把計畫記進 `market.json` 的 `pending` 再撥；帳戶的撥款帶操作 ID、同 ID 只記一次；合併改用 `account_transfer`（同一次讀寫兩邊一起記） |
| 2 | 搬進 archive 後才存狀態，崩了變「營業中但目錄不見」 | 修了：先標 `closing`／`merging`（記下目的地）再搬；重跑 `close`／`bankrupt`／`merge` 接著做，原目錄或 archive 都認 |
| 3 | 市場沒有鎖，並行撥款突破總池、並行合併共用名額 | 修了：改東西的子命令都拿 `.market.lock`；合併在鎖裡重算計畫（跟 dry-run 不同＝`Stale`），寫名冊拿 `roster_lock` |
| 4 | 回收取停機前的快照、停機失敗照樣封存放名額 | 修了：`company.py down` 沒停乾淨退 1；市場層 `StopFailed` 停在 `closing`（還占名額與錢）；停好後才讀餘額收回 |
| 5 | 開戶不擋路徑重疊／重用，帳重複算、污染舊帳戶 | 修了（市場層）：開戶擋跟任何帳戶或市場用過的資料夾重疊（含收掉公司的原路徑）、擋重用收掉的名字。財務部 `account_open` 本身沒擋（`account_of` 設計成取最長前綴），要擋全部入口得改 cost.md，留下一輪 |
| 6 | 配不到的 reply_to 仍套 fallback；非窗口能結 desk 單 | 修了：fallback 只給沒寫 reply_to 的；desk 單只有窗口本人的 DONE／FAILED 結案（別人的照抄、不結） |
| 7 | 總機單寫好、單號未記回就崩留孤兒；董事單派送前崩沒入口 | 修了：照來信找回同一張；每輪最後接續 `via` 還空著的單 |
| 8 | 門房工具先跑後存，重跑再執行一次 | 修了一半：先標 `running` 再跑，重跑看到就**不自動重跑**、標 failed 回報（回信已寄就照回信補記）。「工具接受操作 ID 自己去重」要改 aos-team 工具介面（核心），本輪不動 |
| 9 | grant 後沿用上一輪分數 | 修了：分數帶 `round`，rank 只認這一輪的 |
| 10 | 用下單時間篩、字串比時間 | 修了：看 `closed_at`（總機結案時記；舊單用最後一封回覆），解析成帶時區時間再比 |
| 11 | 先 grant 再 bankrupt，歸零公司被救活 | 修了：花光的不撥、覆寫也擋（`Broke`）；規格順序改成先 bankrupt 再 grant |
| 12 | slots 收負數，虛增總池 | 修了：只收 ≥ 0 |
| 13 | up 已有 K 時不同步池 | 修了：`up` 把 `K/info.json` 兩池顆數對到 `company.json`（`cpu add／rm`），對不上不開。池的 envs 不同步（cpu add 不改既有池的 envs），留下一輪 |
| 14 | 合併改名碰撞覆蓋原員工 | 修了：撞名加 `-2`、`-3`；apply 前再驗一次 |
| 15 | 美元四捨五入超發 | 修了：一律往下取到 0.0001，縮額後斷言合計 ≤ 總池 |

**建議**：1 分數與覆寫、開辦費驗有限值與範圍（做了；`market.json` 的 `params` 本身沒驗，留下一輪）｜2 宿主部門關了＝退信（做了）｜3 董事直接下單命中 tool 的結果 `mail` 看不到（留下一輪）｜4 合併保留 `spawn`／`commons` 覆寫、新名字接公司人格（留下一輪）｜5、6 補故障注入測試（做了：孤兒單、工具中斷、錯 reply_to、非窗口結案、縮額、跨輪、鎖、停機失敗、合併中斷、額度守恆；「真郵差消費寄件檔後的恢復」與真 kernel 的 slots→down→up 留下一輪）。
**可不拍**：關閉事件記 `freed`、〔給 …〕只認第一行，都順手做了。

**試玩員三件事**：①樣板 README 補換模型、`aos-team` 在哪、怎麼看結案、成本提醒、daemon 位置；②`new` 的 cpu 改成不含 llm（12/20）、`down` 後 `status` 印 `stopped`、`down` 印總機撤了沒與 daemon 停了沒；③`market.py` 每個子命令與參數都有 `--help`、覆寫負數擋、有結單沒花 token＝省 100、README 加假資料走完一輪的範例（在 scratchpad 照著跑過一次）。開辦費改 2500 萬 token（§4 第 14 題）。

**董事 09-25「每公司一個 daemon 和 kernel」**：做了。`company.json` 的 `daemon` 預設改 `D`（`<公司>/D/`，原本 `../D` 幾家共用）；daemon 在公司資料夾裡時給 aos-team 的環境照帶 `AOS_DAEMON_HOME`（HR 只數得到自家），寫回 `../D` 共用就照舊不帶；`down` 的 `aos down` 會把自家 daemon 一起關。真開機驗過（[market-run §4](market-run/README.md#4-一家一個-daemon真開機驗過)）：`<公司>/D/` 各自建起來、HR 只數自家、`down` 後行程乾淨。

**留給別的部門**：`playbook/workflows/market-round.md` 的步驟順序已改成先 bankrupt 再 grant（market-run 那一輪順手改）。

測試：test_market 14 → 34 條、test_company 24 → 35 條；全套 101 檔 2822 → 2853 條全綠。

## 8. 市場公式修正

研發部流程組，接 [market-run §5](market-run/README.md#5-發現的問題只記本輪沒改程式) 的 7 條。每條先寫會紅的測試再改（test_market `FormulaFix`，test_company 三條）；測試資料是那一輪的原始紀錄（董事的單、總裁的信、總機單、品質結果檔、c1 證據檔），唯讀複製進 `lib/test/fixtures/market_run/`。沒真跑模型。

| # | 問題 | 怎麼修 |
|---|---|---|
| 1 | 做壞的單照樣拿滿分品質 | 這輪沒有**成功結案**的公司，品質、快、省、總分全 0，撥 0。成功＝總裁寄了結案信（DONE）、信裡有品管的「結論：合格」、中間有結案的品管總機單；`score` 自己數，`--done N` 可覆寫 |
| 2 | 沒打分也照發、同分照名字排 | 這輪一家都沒 `score`，`grant`（含 `--dry-run`）退 1、印「本輪無分數」、什麼都不發；同分同名次，那幾個名次的份額平均分 |
| 3 | 「快」量的是部門間跳的平均 | 改成董事從下單到收到結案信的秒數（c1：182 → 401 秒） |
| 4 | 失敗的也進「省」的比較 | 只在成功的之間比；只剩一家成功就滿分，`rank` 那列註明「省、快：無對照（這輪只有它成功）」 |
| 5 | 證據檔用「A L30」代號，品質從 93.75 掉到 50 | `score --eval` 遇到「無檔名」先把代號展開成檔名（暫存副本）、用同一支 evidence_check 重跑；展開不了才算 0，輸出寫原因。c1 自動算出 93.75（證據 7/8），跟人手展開的一樣 |
| 6 | 草稿不在，單子還寫「讀草稿」，總裁說「依草稿寫成」 | 門房規則加 `if_missing`：`aos-drafts/X/` 不在或是空的，單子改寫「無草稿、從原文起」；總裁人格加一句「單子寫無草稿就不要說照草稿」 |
| 7 | `aos-team hr cap` 要 `AOS_KERNEL_HOME`，README 沒寫 | README 補上；`status` 最後一行印出要帶的兩個值；新增 `company.py hr cap` 自動帶 |

**用那一輪的紀錄重算**（兩家開戶 2500 萬、各自花的 token 照帳本；`score` 都用 `--eval`，不手動覆寫）：

| | 修之前（經理人手動覆寫 c1 品質後） | 修之後（全自動） |
|---|---|---|
| c1 | 第 1 名，排名分 96.25，撥 58％（1.1666 美元、2917 萬 token） | 第 1 名，排名分 **96.25**（品質 93.75 自動、快 100、省 100，註明無對照），撥 **100％（2 美元、5000 萬 token）** |
| c2 | 第 2 名，排名分 60，撥 42％（0.8333 美元、2083 萬 token） | 第 2 名，排名分 **0**（原品質 100，但這輪沒成功結案），撥 **0** |
| 撥完再 `grant` | 第 2 輪照樣整份發出去 | 退 1：「本輪無分數（第 2 輪還沒有任何一家 score）」 |

現在經理人可以照公式發額度：打分只要 `score 名 --eval 結果.json`，看一眼「說明」與 `rank` 右邊的註記，`grant --dry-run` 再 `grant`。還沒做的：成功只認「補人物」這種有品管的單（沒經過品管的結案一律算失敗）；「省」只剩一家成功時沒比出東西，要多跑幾家同條件的單才有意義。

測試：test_market 34 → 43 條、test_company 35 → 38 條；全套 101 檔 2853 → 2865 條全綠。

簡報 brief/2026-09-25.md §1 的「公式還不能真發額度」在本輪修完後應改為：「排名公式真跑後修好了：做壞的單拿 0、沒打分不准撥、快改看董事等多久，經理人可以照公式發額度（打分後看一眼說明與註記再撥）」。
