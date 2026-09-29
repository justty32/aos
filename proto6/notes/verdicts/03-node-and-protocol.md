# 2026-09-29 使用者裁定（三）：node 與協議篇

← [裁定索引](README.md)｜[筆記索引](../README.md)

本份收：第六～十二批，含「軟性標準：一步一步走完整套 agent 循環」。全部裁定後批優先，見[裁定索引](README.md)。

## 第六批：規劃四題＋root helper（同日）

- 逐條規劃的 Q1～Q4、root helper 題：**都照建議**（Q1 收件 commit 後才刪原件；Q2 先 commit 請求檔再送出；Q3 設定編輯不被還原；Q4 清理先只承諾移出日常檔案）。
- **別濫用 git**：實作時避免幾天就上萬個 commit（沒變動不 commit、定期合併等）；可用 **git submodule** 把高頻變動與不太動的部分分開管。
- **改設定**：重要設定——操作手冊寫「先暫停該 agent 的 tick，再手改」；普通設定（增刪工具等）——提供工具，使用者先把檔案寫在別處（每個 agent／kernel 資料夾提供一個 ignore 的工作資料夾），再用工具加進去。（修正 Q3 的做法）
- **root helper 本質上是 daemon 的一部分**，切出來是為了安全：緊急時可以快速 kill 掉它。
- **沒有 root helper 也要能跑**：設一個通用 user 身分；新 agent／kernel 沒規定身分就繼承上層 kernel 的身分，最頂層 kernel 的身分就是這個通用 user。
- **身分不該靠資料夾位置判定**，應在 inst 加欄位宣告（「資料夾必須在有 helper 權限的 kernel 底下」太麻煩）。授權檢查方式待定，見 [kernel 樹](../2026-09-29-kernel-tree.md)。
- **通用 user 預設是開 daemon 的那個 user**，可另外設定。身分額度做法 OK；inst 格式變動草案見 [kernel 樹](../2026-09-29-kernel-tree.md)五之一節（待使用者看過）。
- inst：**不管 proto5 舊版，加了 `user` 的格式就是 proto6 inst 第 1 版**；其餘草案（型別、不吃指示詞、先授權、切身分後才解其他欄位、資源框不寫在 inst）都 OK。

## 第七批：kernel 與 agent 合併成 node（同日）

- kernel 與 agent 大部分相同，只差 tick 註冊表的內容 → **合併成一種東西，叫 node**（中性名字）。
- **kernel 是一個概念**：代表這個 node 管理了一些資源分配與任務排程（由註冊表裝的任務決定），不是用「有沒有成員」來判定。
- **agent 是一個概念**：代表會自主行動的東西，基本上牽涉 LLM（同樣由註冊表裝的任務決定）。
- 一個 node 可以同時是 kernel 與 agent，也可以都不是（例如只跑收信這種自訂任務）。

## 第八批：重寫後兩題（同日）

- **沒有 root helper 時 LLM key 不受保護**：代發服務與 agent 同一個帳號，檔案權限擋不住；接受，文件寫清楚。要保護 key 就要有 helper（或另一個帳號跑代發）。
- **inst 最外層整份 `$ref` 可能藏住 `user`**：沒關係，不另加禁止；維持「展開後不得改變已授權身分」。
- 另請 agent 調查「不用 root helper，改以 daemon 是否用 sudo 啟動決定特權」的可行變形（使用者自評危險，仍想看看）。
- **使用者選定變形：一支指令、看啟動方式決定模式**〔使用者方向 2026-09-29〕：用 sudo（root）開 daemon 時，daemon 自己 fork 出 helper，主程式立刻降權成通用 user；不用 sudo 開就是沒 helper 模式。啟動時印出 helper 的 PID，讓使用者緊急時可以直接 kill 它收回特權。daemon 死掉時 helper 必須跟著死（不能留下沒人管的 root 程序）。細節待 root 調查回來再補。

## 第九批：剩餘待定（同日）

- **下層 kernel 帳號、下層池代發帳號**：合併成 node 後自然解決——kernel node 用自己 inst 的 `user`，它的代發服務用該 kernel node 的帳號。架構筆記待定 1、4 關閉。
- **跨隊傳訊**：有權限就直投對方收件區，不經上層轉送。
- **sudo 模式三細節**照建議：通用 user 不能是 root（預設取 `SUDO_UID`）；kill helper 只切斷新的特權操作、不自動重啟；helper 自己核對身分與路徑。
- **工程數字**（間隔、重試次數、寬限、批次上限）全部先照建議，實作量過再調，不逐條拍板。
- **系統任務用哪個帳號**：一格 tick 裡所有任務都用 node 自己 inst 的 `user`，不另設服務帳號；要 root 的交 helper，管成員的事由上層 kernel 在自己的 tick 做。「控制側」是舊架構用詞，刪除。
- **兩條請求路線**〔使用者方向 2026-09-29〕：要 helper 做事＝node 透過 **IPC 找 daemon**，daemon 核對後轉 helper；要上層 kernel 做事＝**JSON-RPC**。〔建議預設，未拍板〕上層 kernel 不常駐，所以這個 JSON-RPC 以檔案承載：請求檔（id／method／params）投進上層收件區、必要時叫醒上層，回應檔（同 id 的 result 或 error）投回成員收件區；物件形狀可直接沿用 JSON-RPC 2.0。細節在協議篇定。

## 第十批：協議篇開工時（同日）

- **一次性工作**：IPC 註冊可標 `once`（跑一格自動解除）；工作不必是資料夾，單一 inst 檔就行。
- **inst 目標慣例**（沿 proto5 `aos-exec xxx`）：`xxx` 是檔案＝它就是 inst JSON；是資料夾＝找 `xxx/.aos/inst.json`，沒有再找 `xxx/inst.json`；首版**不提供**改路徑的環境變數或旗標→ [協議篇 P-010](../../spec/protocol/README.md)。
- **暫停 tick**：由 daemon IPC 暫停／恢復，只停開新格、不殺正在跑的。

## 第十一批：協議篇整合後兩題（同日）

- **once**：資源一律算發起 node（daemon 以可信 parent_id 記下，不讓工具自選額度）；runner 根本沒啟動時 daemon 在 inst 檔旁寫 inst 檔名加 `.err` 的旁檔（例如 `job.json.err`，見本檔末）。
- **網路**：首版只記用量，不做硬限速；要求限速的部署明確報不支援。

## 軟性標準：一步一步走完整套 agent 循環（同日）

〔使用者方向 2026-09-29，軟性標準〕以一整套 agent 循環為目標：從零開始（寫 daemon 設定、開 daemon、建頂層 node、設 LLM 池、建 agent node、登記、傳訊、看它 tick、看回覆、處理待辦、清理、停機），每一步都要能讓人用指令推進、看得到結果。CLI 規格以這條走查檢驗：走不下去的地方就是缺指令或缺協議。
- **CLI 結構**〔使用者方向 2026-09-29〕：`aos <用途> <動作> ...`，第一層依用途分（daemon／kernel／agent／node 等），子命令後還能再接子命令；不怕多、不怕深，常用的用 alias 縮短。中間層也可以是用途，例如 `aos agent tools add ...`（agent 用途下的 tools 用途）。
- **停 daemon**：首版就用前景 Ctrl-C（SIGINT／SIGTERM 照停機流程），不做跨終端 `aos daemon stop`。
- **下一輪**：定 agent 與 kernel 的最小預設任務程式與 `aos node new` 範本，補走查缺口；CLI 改大白話、加入工具改成 `aos agent tools add/rm/ls`。
- **LLM 請求送去哪＝agent 設定裡的一個位址**〔使用者方向 2026-09-29，取代「一律交給自己的 kernel」〕：請求／結果格式只有一種，agent 照設定的位址送（node id），不管對面是誰。路線由開 agent 的 kernel 在建立時決定，牽涉權限與資源管理路徑：
  - **kernel 全部都管**：位址設成自己；kernel 裝「LLM 轉交」module，收請求、扣額度、排隊，再交給自己的池、上層 kernel 或別的 kernel。
  - **kernel 不管**：開 agent 時給它權限，直接往管池的 kernel（LLM kernel）收件區丟；kernel 改裝「用量收集」module，定期讀 agent 自己記的用量。
- **kernel 別每格都重新註冊**〔使用者方向 2026-09-29，要考慮負擔〕：重新註冊成員只在需要時做（daemon 重開後、成員清單變動時），不要每格都全部重送。
- **agent 日常對話沿用 proto5**〔使用者方向 2026-09-29〕：`aos agent say`（投一句話）／`aos agent listen`（看回話，含 `--last`／`--wait`／`--follow`），承襲 proto5 aos-agent 的 say／listen。
- **收件分兩格，名字沿 proto5**〔使用者方向 2026-09-29〕：`inbox/` 拆成 `requests/`（別人問我）與 `responses/`（我問別人、別人回我）。回應仍**投回發問者家**的 `responses/<id>.json`（不像 proto5 留在回答者家等人來拿、也不用 ack）：node 不常駐，tick 只看自己家就好。兩格都在 `.gitignore`；`reply_to` 指發問者 node，回應落在它的 `responses/`。
- **啟動失敗旁檔改名**〔使用者方向 2026-09-29〕：inst 檔名後面直接加 `.err`，例如 `job.json` → `job.json.err`；取代 `.launch-error.json`。
- **node id 唯一性不另防**〔使用者方向 2026-09-29〕：同一資料夾經 symlink 有兩個路徑、同一路徑先後給不同 node、跨機器重名，這三種都不在考慮範圍內，風險由使用者自行承擔；spec 不加展開 symlink、世代號或跨機檢查。
- **`inbox` 這個名字保留**〔使用者方向 2026-09-29〕：之後要拿去做工具，node 布局不用 `inbox/` 當資料夾名；收件就是根下的 `requests/`、`responses/`。
- **daemon 的待處理事項盡量走 IPC**〔使用者方向 2026-09-29〕：平常靠 IPC 查；磁碟上的資料夾只為 daemon 關掉重開後接續用。

## 第十二批：協議細節再整理（同日）

- **method 名對上現有指令**〔使用者方向 2026-09-29〕：有對應 CLI 的，method 就用那條指令去掉 `aos` 前綴；params 可以是 inst 格式，但裡面的 argv 不能省 `aos`。改名：`agent.send`→agent say、`llm.complete`→llm chat、`kernel.recheck`→kernel schedule recheck。
- **工具也有兩條路線**（比照 LLM）：kernel 要管就全部轉交 kernel；不管就讓 agent 自己在底下登記 once 工作、自己記用量。
- **tick 代為投出與清理**：任務只把要送的檔放進待送位置，tick 在 commit 後才投出、才刪收件原件；每個 module 一項任務即可，取代「收件／準備／派送／清理」四段拆法。
- **daemon 盡量無狀態、可以隨意停開**：正常退出時把狀態存成 json，下次開起來接續；意外退出沒存到，也要有辦法接回來。**daemon 開起來就自動開始 tick 頂層 node**（取代前一條「不先跑頂層」）。
- **pause 存到磁碟**（細節見下批）。
- **work/**：只放任務的暫存工作進度，拿掉「設定草稿」用途。**public/**：可供其他 node 存取的共用空間。kernel 替成員跑工具、打 LLM 這類系統服務，另找地方放，不和一般任務共用 work/（命名待定）。
- **tasks.json 改成 inst 的變形**：每項是一份 inst（不准 `user`）加上 `id`、`kind`、`group`、`needs`；最外層用 `_metainfo`。拿掉 `AOS_TASK_ID`。
- **method 理解確認**〔使用者方向 2026-09-29〕：method＝指令去掉 `aos`、以 `.` 連接（`agent.say`＝`aos agent say`）；params 是一份 inst，意思是「請在你那邊跑這條指令」，argv 必須和 method 是同一條指令且是收件 node 開放的指令，否則回 -32601；回應是這條指令的結果（結束碼、stdout 等，與工作結果同格式）。
- **pause 存檔要批次**〔使用者方向 2026-09-29〕：考量一萬個 agent、極限每秒上千次 pause，不每次寫檔，改成有變動時每 X 秒存一次（X 為工程數字，先照建議）；正常退出時完整存 `state.json`。意外退出最多丟掉最後 X 秒內的 pause 變動。
- **系統區統一放 `.aos/`**：`.aos/inst.json`、`.aos/tasks.json`（追蹤），`.aos/jobs/<id>/`（替成員跑工具、打 LLM 的 once 工作，ignore）、`.aos/summary/`（給上層讀的摘要）。
- **拿掉 `AOS_CONFIG_COMMIT`**：「tick 裡的任務不改 `config/`」是**軟性原則**〔使用者方向 2026-09-29〕，不遵守也可以，但同一格裡設定新舊混用的風險自己承擔；改設定一律在 tick 外用指令（如 `aos-config-add`、`aos agent tools add`），持同一把鎖。任務直接開檔讀設定。
- **其餘照現狀**〔使用者方向 2026-09-29〕：頂層 node 只寫在 daemon 設定、改了要重開 daemon——可以；叫醒權與投件權分開（跨隊投件者叫不醒對方，靠對方 kernel 通知或低頻補看）——維持。
- **回覆也用 `agent.say`**〔使用者方向 2026-09-29〕：拿掉 `agent.reply.receive`；agent 回覆傳訊者就是對它說一句話，payload 多帶 `in_reply_to`（回的是哪一句）。收方一律照 agent.say 收進 history；`aos agent listen` 靠 `in_reply_to` 分出回覆。
- **跨 node 請求的 inst 不另設防**〔使用者方向 2026-09-29〕：params 的 inst 可帶 envs、指示詞、任意 stdin 路徑等，基礎框架不管借權讀檔或換程式的風險，由 agent 與使用者自行承擔；日後需要再擴充。
- **待處理事項分兩處**〔使用者方向 2026-09-29〕：daemon 只保管它自己的事項（啟動失敗、自動停格等），走 IPC 查，`state_dir` 只為重開接續；node 自己的事項放在它的 `.aos/attention/`；`aos attend ls` 沿登記樹整理成一張清單。拿掉讓 node 把事項交給 daemon 的 `daemon.attention.put`。
- **回應的 stdout 照現狀**〔使用者方向 2026-09-29〕：結果只給路徑、發件者未必讀得到，不另做內嵌或搬運機制。
- **node 的事就放 node 那邊**〔使用者方向 2026-09-29，細化上一條〕：runner 沒能開始、tick 壞掉（自動停格）、程序清不乾淨這類都是 node 自己的問題，由 daemon 寫進該 node 的 `.aos/attention/`（ignore，不隨 group 還原）；once 單檔工作沿用 `.err` 旁檔。daemon 只保管它自己的事（helper 不見、state 存不下等），走 IPC 查、`state_dir` 只為重開接續。〔建議預設〕daemon 須對各 node 的 `.aos/attention/` 有寫權；多帳號部署由建 node 時開權限，〔使用者方向 2026-09-29〕寫不進去就不管，daemon 在 **stdout** 印一行警告。
- **daemon 的 stdout／stderr 分工**〔使用者方向 2026-09-29〕：stderr 只印 daemon 自己的原因造成的錯誤；stdout 印啟動那行 `helper_pid=...`，以及 node 那邊的問題（例如事項寫不進 node 的 `.aos/attention/`）的警告。
- **helper PID 也存檔**〔使用者方向 2026-09-29，怕 stdout 被刷掉〕：啟動時除了印 `helper_pid=...`，也寫進 `state_dir/helper.pid`（一行，沒 helper 寫 `none`）；〔建議預設〕同處寫 `daemon.pid`，正常退出時兩檔都刪；開機看到舊檔只當提示，不拿來殺程序。
- **daemon 記憶體裡的事項定期存檔後清空**〔使用者方向 2026-09-29〕：事項（daemon 自己的、要寫進 node `.aos/attention/` 的）先暫放記憶體，每 X 秒批次寫出，寫完就從記憶體清掉，減輕 daemon 負擔；重開後**不**把存好的事項讀回記憶體。〔建議預設〕`daemon.attention.ls/show` 查詢時直接讀 `state_dir/attention/` 的檔案（加上還沒寫出的那幾筆）；`resolve` 就是把那份檔搬到 `done/`。
- **`resolve` 改名 `done`**〔使用者方向 2026-09-29〕：`resolve` 聽起來像下了指令就自動修好；改成 `done`＝「人已處理完，標成完成」。`daemon.attention.done`、`aos daemon attention done ID`；node 事項那邊（`aos attend ...`）有同義動作也一併叫 `done`。
- **結果不明的工作就放著**〔使用者方向 2026-09-29〕：unknown 不另做處置流程，沒人處理就隨 tick 的定期清理清掉。
- **git 歷史回收先不管**〔使用者方向 2026-09-29〕。
- **attention 就是待辦清單**〔使用者確認 2026-09-29〕：aos 裡出了事、aos 自己不該或不能自動處理，交給人或 agent 手動處理（清理或修好）的清單。
- **`aos attend` 縮成三條**〔使用者方向 2026-09-29〕：`ls`（沿登記樹彙整 node 與 daemon 的待辦）、`show N ID`（出了什麼事＋白話的建議處理，必要時附建議指令的文字）、`done N ID`（處理完標完成）。實際修理由人或 agent 自己下指令。
- **`aos attend try-solve` 留到以後**〔使用者方向 2026-09-29〕：原 `run`（照處理表試著處理）改名 `try-solve`，處理成功就自動 done；這支程式以後再做，本輪 spec 只留名字與一句用途，處理表、自動執行、y/n 確認、動作紀錄都先拿掉。
- **不做自訂清理接口**〔使用者方向 2026-09-29〕：`aos-clean` 只清自己認得的資料（預設 agent／kernel 任務產生的），不認得的不碰、也不回報；自訂任務的資料自己清。
- **`aos-clean` 由 tick 定期呼叫**〔使用者方向 2026-09-29〕：它是 node 任務表裡的一項。〔建議預設〕任務表沒有間隔欄位，由 aos-clean 自己記上次清理時間，沒到期就直接回 0（間隔寫在它的設定，預設一天）。
