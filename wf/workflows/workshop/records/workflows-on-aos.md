# 用 aos 實現 workflows
← [workshop](../README.md)｜前情：[核心行程與子行程](core-process-and-subprocess.md)／[四個懸而未決的選擇](four-open-choices-tradeoffs.md)／[agent loop](agent-loop-architecture.md)／[回頭審視](step-back-review.md)／[隨意發想](free-ideation.md)

| | |
|---|---|
| **主題** | 如何用 aos 實現 workflows 那樣的功能 |
| **開場** | 2026-08-25 |
| **已跑輪數** | 一輪 |
| **狀態** | 進行中 |
| **參與身份** | 資深工程師 / 資深架構師 / 資深研究人員（作業系統／體系結構） / 要接這個工具的開發者 |
| **缺哪個角度** | 沒有「普通用戶」——使用者先前拿掉了那個身份。所以**沒有「這東西人看不看得懂」的視角** |
| **reasoning effort** | `xhigh` |
| **參與者** | **與〈四個懸而未決的設計選擇〉〈agent loop〉〈回頭審視〉〈隨意發想〉是同一批人**（同一批 codex session 續下來） |

## 先讀這段（500 字懶人包）

這輪第一次知道 aos 的目的：改善純 markdown 的 workflows。**四位共同方向是：markdown 繼續保存
「怎麼想、為什麼」；aos 只接手「現在輪到誰、卡在哪、何時再醒、下一步投去哪」。**候選動作是
`wf start／wait／resume／done／status`；inbox 仍是信，只有 `accept` 後才變成工作。

但這還不能直接開做。四位都只是**推論**出兩種痛：open-only／歸檔靠記憶，以及模板安裝、升級
靠手工合併；使用者尚未說真正哪裡不好用。另一個 4／4 未決問題是活狀態要不要隨 Git 跨機：
若要，通常不版控的 `.aos` 不能當唯一真源。

最先該問的是：最近一次具體卡在哪？只能消掉一步，會選安裝升級、找路由、維護狀態、記得 tick，
還是 agent 不照流程？

---

使用者在這輪第一次揭露 aos 的起點：

> 其實 **aos 在最初，只是我覺得 `C:/code/mine/workflows` 不是很好用，才想出來的規劃**。
> 開啟下一輪吧，大家一起想想看，**如何用 aos 實現 workflows 那樣的功能**。

這改變了整個專案的座標。前面幾輪的 CPU 類比、行程、lane、kernel、agent loop 都是可能的
**手段**；這輪第一次看見它們原本想服務的**目的**。

`workflows` 本身沒有 executor：`WORKFLOWS.md` 用自然語言派發意圖，各工作流 README 解釋理由、
判準與步驟；`SESSION-LOG.md`、`WAIT_USER.md`、`inbox/` 靠人或 agent 手動維護。它的分層原則是
「每層只指向下一層」，也有一套非侵入式匯入方法。這個 repo 的 `wf/` 同時是它用了幾個月的
活實例，已經長出 workshop、ideas、tick 等 template 原先沒有的東西。

但是使用者只說「不是很好用」，**沒有說痛在哪裡**。所以下面凡是談目前痛點，都標成四位從
template 與活實例推出的假說，不寫成使用者已確認的事實。

## `workflows` 現在可能會痛在哪

> **本節全部是推論，不是使用者已確認的痛點。**

### 活狀態的「open-only」靠記憶維持

**四位獨立地都指出同一個現象**：活實例的 `SESSION-LOG.md` 已從「只列一行 open」長出完成歷史，
`WAIT_USER.md` 即使寫「目前無」仍保留已解事項，inbox 也留著模板說明。四位的推論是：新增、移動、
完成即移除、歸檔等規則全靠當下 agent 記得，所以使用久了會漂移。

這裡只能確認「文件現況偏離 open-only」，不能確認這就是使用者說的不好用。也可能使用者其實
故意要保留歷史；這正是後面要問他的問題。

### 安裝與升級沒有可追的上游基準

**四位獨立地都推論這可能是第二個痛點**：初次導入要複製 template、貼 flavor 表、填 placeholder、
修連結；活實例之後新增 workshop、ideas、定期工作流等客製內容，再想帶入新版 template 時，沒有
「當初從哪一版來」的紀錄，只能手工判斷每一處差異。

四位不是說客製化本身錯了。問題假說是：**沒有 source version／base hash，升級分不出「上游新
版本」「本地故意改的」「從未填完的 placeholder」。**

### inbox 的信件生命週期也靠人記得

資深工程師、資深架構師**兩位獨立地直接指出**，寄信要人工避開撞名，收件、忽略、完成、搬 done
也沒有機械狀態；研究人員與開發者則從 tick／歸檔角度看到同一類手工維護。這可能會痛，但 inbox
原本就容許不回、寄失敗也無妨，不能因為能機械化就把它誤改成可靠 instruction queue。

### 派發與遵守流程是不是痛點，材料本身看不出來

四位都把「找不到該走哪條流程／派錯工作流／agent 不照做」列進要問使用者的候選，但沒有人能從
檔案證明它真的常發生。`WORKFLOWS.md` 的自然語言路由也可能正是系統最好用的部分。這一項不能
先以 parser 或狀態機解掉。

### tick 與 schedule 可能只是在等人記得喚醒

工程師、研究人員、開發者提到 ready／到期項仍需 tick 或 cron 喚醒；開發者把 schedule 縮成只存
`next_at`。這是從現有定期工作流推出的疑點，不是使用者已說「我常忘記 tick」。是否值得先做，
仍要看實際頻率。

## 該變成 `.aos` 的

四位共同的邊界比具體路徑更穩定：**aos 不判斷這個需求該走哪條 workflow；它在 workflow 已選定
之後，原子地保存活狀態、移交 owner、到期時投遞下一步。**

### 共同長出的動作

| 動作（候選） | 做什麼 | 誰提的 | 原本手工做什麼 |
|---|---|---|---|
| `aos wf start FLOW` | 建立一筆 open task，記 workflow、step／resume、owner 與目前 phase；需要時投遞第一步 | 工程師、架構師、開發者三位明確給命令；研究人員用建立 open-item 表達同一動作 | 在 SESSION-LOG 加一行、另記入口與下一步，兩邊容易漏一邊 |
| `aos wf wait ID --question FILE` | 把 owner 改成人，保存問題／resume 資訊，從 ready 移到 wait-user | 工程師、架構師、開發者三位明確提出；研究人員用 owner=user 的 open-item | 手動把 agent 進度搬到 WAIT_USER，再確保原處刪掉 |
| `aos wf resume ID` | 保存人的答覆，把 task 移回 ready，原子投遞續步 | **四位都提出** | 手改兩份清單、找回中斷前脈絡，再記得喚醒 agent |
| `aos wf done ID`／`resolve ID` | 關閉 open item；不再讓完成史留在 open view | 架構師、研究人員明確給命令；其餘兩位要求完成即移除／搬動 | 手動刪 open、決定是否另歸檔，容易留下已完成項 |
| `aos wf status --format md` | 從唯一活狀態渲染 SESSION-LOG／WAIT_USER 兩種 view | 工程師、架構師、開發者三位明確給 CLI；研究人員也主張兩份 log 是依 owner 產生的 view | 人同時維護資料與展示，容易雙寫漂移 |
| `aos wf accept MAIL` | 明示把一封可忽略的信升成 task／ready，必要時再 Deliver instruction | 工程師、開發者兩位明確給命令；架構師、研究人員都主張信箱與 instruction queue 分開 | 收信者憑記憶決定它算知會、待辦還是立即執行 |
| `tick`／schedule wake | 讀 ready／`next_at`，成功 Deliver 到 `inst.tempd` 後才更新 cursor／下次時間 | 工程師、研究人員、開發者提出；架構師的 task phase 可容納相同喚醒 | 人／cron 要掃文件、判到期、投遞，並避免投遞失敗卻先前進狀態 |

這些命令共同依賴 temp＋rename，但不等於每個 workflow 都要變成 lane。資深工程師說 workshop 先只是
跨回合 work item；架構師說只有獨立等待、喚醒與收件才升 lane；研究人員把 feature-dev 看成 job、
workshop 才「可能」是 lane；開發者也只讓跨回合工作升 world。**四位都沒有主張把每條 markdown
流程編譯成一顆常駐行程。**

### 磁碟版面有兩個尚未合併的版本

三位與研究人員在「活狀態放哪裡」分成兩種：

| 版本 | 版面 | 得到什麼 | 代價／疑問 | 誰提出 |
|---|---|---|---|---|
| **`.aos` 是活狀態真源** | `.aos/wf/tasks/<id>/state.json`，或 `.aos/wf/{ready,wait-user,schedule}/<id>.json`；位置／phase 表示狀態 | 原子 move 容易；status 可產生 markdown view；文件不再同時兼任資料庫 | 若 `.aos` 通常不進 Git，跨機／協作時 open 狀態不會跟著走；JSON 是否允許人直接改也要定 | 工程師、架構師、開發者三位獨立提出 |
| **`wf/open` 是活狀態真源，`.aos` 只執行 next** | `wf/open/{agent,user,peer}/<id>.md`，front matter 記 workflow、since、resume；`.aos` 只放本次投遞／`.runi` | open item 可讀、可 Git diff、可隨 repo 跨機；仍能按 owner 產生 view | move markdown 與 Deliver next 要如何形成一個可恢復動作，還沒具體化 | 研究人員提出 |

資深工程師、架構師、研究人員、開發者**四位都各自標記自己沒把握同一件事**：open 狀態是否要
隨 Git 跨機。這個答案會直接決定上述兩個版面哪個在對的層，不能靠偏好選。

### 一個候選的動作順序

把三位的 `.aos` 版面與四位共同語意疊起來，候選流程是：

```text
模型讀 WORKFLOWS.md，選到 workflow
        │
        ▼
aos wf start FLOW ───────────────► ready
                                      │
                    tick／立即 Deliver 到 inst.tempd
                                      │
                     ┌────────────────┴───────────────┐
                     ▼                                ▼
             aos wf wait ID                    aos wf done ID
                     │
                  wait-user
                     │ 人回答
                     ▼
             aos wf resume ID ─────────────────► ready

inbox/MAIL ── aos wf accept MAIL ──────────────► ready
```

這張圖只描述四位提過的狀態轉換，不決定真源是 `.aos/*.json` 還是 `wf/open/*.md`。`tick` 必須先
確認 Deliver 成功，再更新 task／cursor；否則下一次會以為已喚醒，實際 queue 裡卻沒有 instruction。

### 安裝與升級也可以機械化，但不應覆蓋客製

**四位獨立地都提出 source version／base hash＋三方 diff。**命令名稱有三種：
`aos wf install dev`、`aos init --with workflows:dev`、`aos module add workflows --flavor dev --layout wf`。
共同形狀是：安裝非侵入式文件骨架，記下來源版本／base hash；升級比較「舊基底／新基底／本地修改」。

資深工程師另外提出 `doctor`，掃 placeholder、壞連結、孤兒路由；其餘三位沒有獨立提出這支命令。
開發者則把 upgrade 收緊為只自動替換未修改檔，客製檔只顯示差異。**四位都沒有主張拿新版 template
直接覆蓋活實例。**

## 該永遠留在 markdown 的

**四位獨立地都畫出相同邊界**：

- `WORKFLOWS.md` 的意圖派發；模型要理解「使用者現在想做什麼」，不是比對有限 enum。
- README 裡的理由、判準、例子、Done when、例外與 gotchas。
- 鐵律、慣例、durable 知識、研討議題與完整紀錄。
- 非侵入式匯入的說明，以及人要審閱、Git diff 的政策文字。

資深架構師與開發者允許給文件加很薄的 `id`／`entry` front matter，讓 `wf start` 找得到入口；但
**aos 不解析正文來取代路由判斷**。研究人員的一句話是：「讓 aos 執行下一步，不要取代 workflows
用來思考的文字。」

把這些內容編成 JSON／狀態機的代價，不只是難讀。四位都指出，workflow 政策仍在生長；機械 schema
會把尚未成形的理由與例外提早凍死，之後 markdown 與 JSON 又變兩份真相。

這一輪最整齊的分工，可以原樣保留兩位的句子：

> **讓 Markdown 保存「怎麼想」，讓 `.aos` 保存「現在走到哪裡」。** ——資深架構師

> **Markdown 保存怎麼想，aos 只接手輪到誰、卡在哪、下一步投去哪。** ——資深工程師

## 三軸分別長成什麼

四位都沒有把 `SESSION-LOG`、`WAIT_USER`、`inbox` 混成一個 queue。他們共同抽出的是 open-item，
三軸仍靠 **owner 與語意** 分開：

| 現在的軸 | 機器狀態的候選形狀 | 什麼動作進來／出去 | 不能失去的原意 |
|---|---|---|---|
| **SESSION-LOG：我手上的 open in-flight** | owner=`agent`、phase=`ready|running`，帶 workflow、step、resume | `start` 建立；`resume` 回到這裡；`wait` 移出；`done` 關閉 | 只列 open，不變成完成史；它是「現在做到哪」，不是工作流全文 |
| **WAIT_USER：卡在人** | owner=`user`、phase=`wait-user`，保存 question 與 resume | `wait --question` 進入；收到答覆後 `resume` 回 ready | 等的是人親自做／驗證；不能只用 paused 混掉「誰欠下一步」 |
| **inbox：agent 之間的信** | owner=`peer` 或獨立 mail envelope；可以未讀、忽略、歸檔 | 寄信只進 inbox；只有 `accept` 才轉 task／ready，必要時再 Deliver | **信不是 instruction。**寄失敗／不回原本就容許，不能直接塞 `inst.tempd` 變成必須 claim 的工作 |

研究人員把 SESSION／WAIT 看成依 owner 產生的兩個 view；架構師也用 task 的 owner／phase 表示；
工程師與開發者則偏好 ready、wait-user、mail 三個目錄，讓位置本身就是狀態。語意已接近，尚未定的
是「狀態存在欄位裡」還是「狀態存在路徑裡」。

schedule／tick 是三軸之外的喚醒條件：開發者只存 `next_at`，人或 cron 到點喚醒；工程師要求
Deliver 成功才改 cursor。它不必把 sleeping task 改成一條常駐 loop。

## 還在生長的想法

### 活狀態要可 Git、可跨機，還是純本機執行狀態

這是最關鍵也最沒有答案的一條。三位的 `.aos/wf/*.json` 很適合 rename 與 generated status；研究
人員的 `wf/open/*.md` 很適合 Git、跨機與人直接改。四位都明說：若 open 狀態要進 Git，`.aos`
不能是唯一真源。也可能反過來決定 open 只屬當前機器，跨機靠 export／sync，但沒人提出完成形狀。

### task 何時才值得升成 world／lane

四位都先保留「短流程只是 task」。分界的說法略不同：獨立等待、反覆收件、跨回合恢復、需要
自己的 queue 時，才可能升 world／lane。工程師甚至提醒 workshop 不該只因等待就自動成 lane；
這表示升格不能只看時間長，而要看是否真的需要獨立執行與收件。

### 人能不能直接改 machine state

工程師說人可以改 `ready/<id>.json`，下一次 tick 採用；架構師、開發者則傾向由命令更新、markdown
只作 generated view；研究人員直接把真源放 markdown。三種都保留了「人可修」，但修的是 JSON、
命令還是 front matter 尚未收攏。

### non-invasive import 可以長成 module，但名字與責任未定

install／init／module add 三種名字背後是同一個想法：文件仍放 `wf/`，不把專案原目錄弄亂；機器
狀態放 `.aos/wf` 或另一個明示位置；upstream metadata 記模板來源。還未回答的是 module 只管理
安裝／升級，還是也負責 task runtime。

### `doctor` 可能比自動 upgrade 更安全

只有工程師提出 `doctor`：先找 placeholder、壞連結與孤兒路由，不替人合併政策。這條沒有多人
呼應，但與四位「upgrade 只顯示三方差異、不蓋客製」的邊界相容，所以讓它單獨留著。

## 明顯的坑

- **把推論寫成使用者痛點。**四位只從檔案看到 drift 與手工步驟；使用者尚未說自己最痛的是哪個。
  若先做 install、router 或 task DB，可能精準消滅一個他根本不在乎的步驟。

- **把所有 markdown 編成 JSON**。**四位獨立地都反對**：意圖、理由、例外與 gotchas 需要模型
  理解和人審；結構化副本只會和原文漂移。

- **同時手改 SESSION-LOG／WAIT_USER，又讓 `.aos` 當真源。**status 若是 generated view，就不能
  再接受另一條手工維護鏈；若 markdown 要可編輯，它就必須有明確反寫／reconcile 規則。

- **把 inbox 直接接到 `inst.tempd`**。**四位獨立地都分開兩者**：信可以不回，instruction 必須
  claim。缺少 `accept` 這道明示升格，知會信會變成強制工作。

- **活狀態放進通常不版控的 `.aos`，卻期待它自然隨 Git 跨機**。**四位都標記這是未知前提**；
  真源位置不拍板，任何 layout 都可能在第一天就放錯層。

- **upgrade 自動覆蓋客製 workflow**。**四位都只接受來源版本＋三方 diff**；開發者更明說只替換
  未修改檔。模板是基底，不是活實例的遠端真源。

- **把每個 workflow 都升成 lane。**四位都先保留 task；若只是「步驟多」或「等過人」，不代表
  它需要獨立 queue、kernel 與生命週期。

- **tick 先改 cursor，再 Deliver。**工程師明確要求成功投遞後才前進；順序反了，task 會被標成
  已喚醒，但 queue 裡沒有下一步。

## 要拿去問使用者的問題

下面把四人的問題去重成可以逐條回答的清單。第一題是**四位都問到**的核心；後面用來決定該先
機械化哪一層。

1. **最近一次你覺得 workflows「不是很好用」，當時具體在做什麼、卡在哪一步？**
   資深架構師直接問「最近一次」；其餘三位也都要求先確認實際痛點，不把檔案 drift 當答案。

2. **下面哪一類最常痛？如果只能消掉一步，你選哪個？**（**四位都問了這組分類**）

   - 初次安裝、填 placeholder，或把 template 新版升進既有專案；
   - 找不到／派錯該走的 workflow；
   - 跨 session 保存進度、WAIT_USER，或記得完成後清掉 open；
   - 記得跑 tick／處理到期項；
   - 文件寫了，但 agent 沒照流程做。

3. **`SESSION-LOG`／`WAIT_USER` 裡現在保留完成歷史，是你故意要的，還是因為常忘記清？**
   四位都把這個檔案現象解讀成可能 drift；需要你確認，才能知道 open-only 是否真是需求。

4. **open 狀態需要隨 Git 跨機、讓另一台機器／另一個人接手嗎？**
   **四位獨立地都把這列為自己最沒把握的一題。**若要，`.aos/wf/*.json` 不能在不版控時成為
   唯一真源；若不要，本機 machine state 才比較自然。

5. **你希望人直接編輯活狀態檔，還是只透過 `aos wf wait／resume／done` 改？**
   工程師接受直接改 JSON，研究人員偏向可編輯 markdown，架構師與開發者偏向命令＋generated view。

6. **inbox 現在最麻煩的是寄信撞名、忘記看、忘記歸檔，還是根本不麻煩？**
   工程師、架構師從檔案推論人工生命週期會痛，但 inbox 原本就是可忽略信件，不能未問先改成 queue。

7. **template 更新真的需要帶進既有專案嗎？還是安裝後各專案就各自分叉，不再追上游？**
   四位都提出三方合併，但這建立在「你想升級」的假設上；若本來就不追新版，source lock 的價值
   只剩追溯，不是 upgrade。

8. **哪些 workflow 真的需要自動喚醒？schedule／tick 是常用能力，還是這個 repo 後來長出的少數
   特例？**工程師、研究人員、開發者都提到 tick，但沒人有使用頻率證據。

## 續場資訊

本輪沿用前幾場的四個 codex session；它們仍保留完整前情。session id **只在 office Windows
那台機器有效**；`codex exec resume <id>` **不吃 `-s` 與 `-C`**。

| 身份 | session id |
|---|---|
| 資深工程師 | `01a03676-8fa3-7622-aee8-05801a7059d3` |
| 資深架構師 | `01a0367b-797f-7403-999e-fe2c685a8c10` |
| 資深研究人員（OS／體系結構） | `01a03683-95cb-7331-8528-d1513a6c806f` |
| 要接這個工具的開發者 | `01a03688-8b4c-70b0-87e3-ea28be9b7f9c` |

---

## 轉交提案（未拍板，不自行改規格／roadmap）

1. **先拿上一節的問題問使用者，不先把任一推論排進 roadmap。**最少要知道最近一次具體事故、
   只能消掉哪一步，以及 open 狀態是否需隨 Git 跨機；這三個答案會改變第一個功能與磁碟真源。

2. **若使用者確認「活狀態靠記憶」是痛點，再拍板真源版面。**候選是三位的
   `.aos/wf/tasks/*.json`／位置即狀態，加 `status --format md` 產生 view；或研究人員的
   `wf/open/{agent,user,peer}/*.md` 真源，`.aos` 只負責 Deliver／`.runi`。兩者不能同時不分主次。

3. **若走 machine-state 版本，先做最小垂直切片。**`wf start → wait → resume → done` 加 status，
   只覆蓋 SESSION-LOG／WAIT_USER；`WORKFLOWS.md` 仍由模型讀，所有理由與判準仍在 markdown。四位
   都認為不需要先把 workflow 編成 lane。

4. **inbox 只共用原子信封，不共用 instruction queue。**若要機械化，先拍板 `wf accept MAIL`
   的語意：只有明示接受才轉 open task／Deliver；未接受仍可忽略，保留 inbox 原本的寬鬆契約。

5. **若使用者確認安裝／升級才是痛點，另開 module/install 工作。**保存 source version／base hash，
   upgrade 產三方 diff，只自動替換未修改檔；客製 workflow 不覆蓋。`doctor` 可先做只讀檢查，是否
   需要由使用者拍板。

6. **tick／schedule 等使用頻率確認後再收。**候選最小狀態是 `next_at`；喚醒時先成功 Deliver，
   再更新 cursor。不要因為現有 repo 有定期工作流，就推論每個匯入 workflows 的專案都需要 scheduler。
