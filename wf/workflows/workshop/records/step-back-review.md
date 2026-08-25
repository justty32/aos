# 三場研討會的回頭審視
← [workshop](../README.md)｜審視：[核心行程、子行程，與外部處理器的契約](core-process-and-subprocess.md)／[四個懸而未決的設計選擇](four-open-choices-tradeoffs.md)／[agent loop 的實作架構與基礎 core 功能](agent-loop-architecture.md)

| | |
|---|---|
| **主題** | 重新回頭審視三場研討會的全部產出：哪些該收回、哪些未驗證、下一步只留什麼 |
| **開場** | 2026-08-25 |
| **已跑輪數** | 一輪（回頭審視） |
| **狀態** | 進行中 |
| **參與身份** | 資深工程師 / 資深架構師 / 資深研究人員（作業系統／體系結構） / 要接這個工具的開發者 |
| **缺哪個角度** | 沒有「普通用戶」——使用者先前拿掉了那個身份。所以**沒有「這東西人看不看得懂」的視角** |
| **reasoning effort** | `xhigh` |
| **參與者** | **與〈四個懸而未決的設計選擇〉及〈agent loop〉是同一批人**（同一批 codex session 續下來）；他們沒參加〈核心行程、子行程，與外部處理器的契約〉，那場是另外四個人談的。 |

## 先讀這段（500 字懶人包）

**現在先砍／延後：**公開 `publish`、通用 `effect`，以及多世界、lane／proc-table、capability、
promotion、UUID／generation、活搬、平行 join、分層 kernel。保留單一 world、本地 kernel、現有
`.runi`；publish 先只是 Deliver 內部寫法，unknown 先由 adapter／人處理。

**現在先做：**一、最小 `aos deliver`，只做驗證、唯一 temp、rename，不承諾跨回合 key 去重。
二、選一支真 LLM CLI，用腳本跑「模型→一個具名工具→模型」。三、逐點注入 Ctrl-C／hard kill，
記下每一步哪個檔才是事實。

三位獨立指出更優先的缺口：模型輸出不能直接變任意 argv；首版先用固定工具映射，必要時人工核准
或 sandbox。四位都主張：機制只有在實跑中重複痛過，才申請進 core。

---

這輪不是第四場發想，而是回頭審前三場留下的方向。使用者的要求是：

> **這次是重新回頭審視。**

前幾輪為了求「多」，禁止參與者評判與否決；本輪為了求「準」，明文解除那條規則。邊界是
對事不對人，而且**先審自己說過的**：任務書原話是「自己收回一條，比反駁別人一條更有價值」。
任何機制若被砍掉，下面都會交代原本的問題暫時由誰承擔。

## 四位收回了什麼

最有訊號的不是四位否定別人，而是他們看過三場完整產出後，**四位不約而同收回了自己上一場
剛收攏出的兩項前置功能**：公開 Publish 與通用 Effect。

| 收回／延後什麼 | 誰收回 | 為什麼收回 | 砍掉後，問題由誰負責 |
|---|---|---|---|
| **公開 Publish API** | **四位各自都明確收回** | 目前只證明 Deliver 內部需要 temp＋rename；通用檔／目錄發布、跨 filesystem、fsync 與斷電契約都沒有 workload 證據 | Deliver 內部保留私有 publish helper；其他腳本若要更新自己的 state／cursor，暫時自行 temp＋rename，等重複出錯再抽公開 API |
| **通用 Effect／Effect resolve 作為近期 core 前置** | **四位各自都明確收回** | 它誠實標 unknown，卻不能消除「遠端已做、本機未記」；provider 查詢與冪等仍各家不同，T5 也尚未實跑出重複痛點 | `.runi` 讓本地批次停住；provider wrapper／adapter 記簡單日誌，unknown 交給人 retry／放棄／採納，不先做通用 core ABI |
| **平行 `effect_join`／barrier** | 工程師收回自己的 `effect_join`；研究人員、開發者也把平行 join 列為尚不存在的問題 | 首版連串行「模型→一工具→模型」都沒跑過，先為平行工具造 barrier 沒有證據 | driver 先只跑串行；真的出現多工具並行後，再由腳本負責掃結果並暴露共同形狀 |
| **現在就定 events／calls／cursor 的耐久版面** | 架構師明確收回；其餘三位也都改成先用腳本落 prompt／response／result | 三場裡提出了多套資料夾名，沒有一套經真 CLI 或 crash 驗證 | T5 腳本先選最小檔名；它是實驗資料，不是 core ABI，重複後再升格 |
| **`slot@generation` 與永久身分** | 研究人員明確收回自己的 generation；工程師、架構師、開發者也都把活搬／舊 receipt 誤投列為預測問題 | 沒有第二個 world、沒有活搬，也沒有一次 stale receipt 事故 | 先用路徑定位且不承諾活搬；真的發生同名新世界誤收舊結果時，再加 generation |
| **lane／proc-table／capability／promotion 這組通用行程機制** | **四位獨立地都說整組走得太前面** | 從 Linux 行程隱喻推導出控制平面與磁碟 ABI，但目前只有一個人的新專案、單一 queue，agent loop 一次都沒跑 | agent 的續跑由 driver 腳本負責；`aos exec` 仍只推一個 folder。第二個 world、共享 writer 或真正的權限需求出現後再重開 |

四位沒有收回所有東西。**本地、單層的 `kernel.json` 仍被視為簡單的頭尾指令來源；`.runi` 仍
保留未完成回合；原子 Deliver 仍是四位都承認的現存缺口。**被收回的是在 workload 出現前，
把它們向上長成繼承政策、process manager、通用 WAL 與可搬身分。

---

## 一、「多位獨立提出」會不會其實是共同偏見

答案是：**四位現在都認為有，而且不只一條。**他們都是系統／架構／OS／外掛契約背景，擅長先
找 crash window、所有權、提交與升級問題；這讓「四位獨立提出」仍是重要訊號，卻不是需求已存在
的證據。

### 共同偏見一：把「agent 多走幾回合」過早類比成 Linux 行程

**四位獨立地都指出同一個長歪點**：從普通 instruction 可以呼叫另一個 `aos exec`，一路實體化
成 lane、root 行程、proc-table、capability、receipt、promotion、join、可搬身分與跨 lane commit。
這些機制回答的是「很多耐久行程同時存在時怎麼管」，但目前還沒有第二個 world、共享 writer 或
活搬需求。

資深工程師說這是把 workflow 的 owner／receipt／恢復寫成通用 ABI；資深架構師稱為 OS 隱喻
過擬合；研究人員說 CPU 被尚不存在的 process manager 包圍；要接工具的開發者則指出，長歪始於
把「指令可呼叫另一個 exec」變成需要全域權力與永久身分的耐久行程。

### 共同偏見二：把故障分析直接排成近期產品功能

[agent loop 的 R2](agent-loop-architecture.md)中，四位 4／4 選了 Publish → Deliver → Effect。
本輪**四位又各自收回 Publish 與 Effect 作為近期前置**：這個 4／4 反映的是四人都重視 WAL、
斷電、多檔交易與外部副作用，不代表 T5 已證明需要公開 API。

Deliver 是例外：投遞在現有三步交接裡確實沒有函式，腳本現在就得重寫唯一 temp＋rename；因此
四位仍保留它。Publish 與 Effect 回到「若腳本反覆痛，再升 core」。

### 這個共同偏見的實際後果

三場把大量篇幅花在未出現的第二世界、活搬、平行工具與 exactly-once 周邊；反而沒有先固定一支
真 LLM CLI、跑完一次模型→工具→模型，也沒有先決定模型輸出可不可以碰檔案、網路與憑證。四位
不是說那些系統問題永遠不存在，而是收回它們的**時間順位**。

---

## 二、哪一條假設從頭到尾沒人檢查過

### `deliver --key` 的跨回合冪等其實沒有帳本

資深工程師與資深架構師**兩位獨立地檢查到同一個洞**：前一場把同 key 同內容說成 Already、
異內容說成 Conflict；但 aggregate 成功後會刪掉投遞檔。沒有一份耐久 receipt ledger，下一次
重送 `K` 時已沒有舊內容可比，根本不知道它是不是同一次。

所以最小 Deliver 現在只能承諾：驗證 payload、建立唯一同目錄 temp、write-all、rename 到 queue。
key 可以留作檔名／correlation 提示，但**不能在沒有 ledger 的情況下宣稱跨回合去重**。若日後真
遇到重送事故，要嘛另養 ledger，要嘛把去重範圍明確縮到「檔案還留在 queue 時」。

### 沒人實測 LLM CLI 是否真像一個純函式

資深研究人員與要接工具的開發者**兩位獨立地指出**，三場一直假設可以把 prompt 送進某支 CLI，
再得到完整、穩定、可解析的 tool call；但 session、streaming、schema、截斷、取消、exit code、
Ctrl-C 後狀態都沒有用真 CLI 驗證。工程師、研究人員、開發者**三位獨立地都追問同一個最基本的
問題：首支 CLI 到底是哪一支？**；架構師則先問這支 CLI 會在全信任實驗裡跑，還是會碰真實資源。

在這個假設未驗證前，events／calls、Effect 狀態與恢復 API 都可能是在替不存在的 I/O 形狀設計。
T5 的第一個產物應是觀察紀錄：CLI 在每個成功、失敗與中斷點實際留下什麼。

### failure 與 trust 的範圍一直沒定義

工程師、研究人員、開發者分別追問 Ctrl-C、hard kill、斷電是不是同一個承諾；架構師則要求先
說 T5 是全信任實驗，還是模型能碰真實檔案、網路與憑證。沒有這兩條邊界，「durable」「可恢復」
與 capability 都只是在各自想像不同故障／威脅模型。

---

## 三、這東西還簡潔嗎：是哪一步開始長歪的

使用者反覆說的是：

> **複用、簡潔，是目標。**

> **CPU 做的事情非常簡單：取出下個指令，執行，然後繼續取指令。**

四位的回看不是「`aos exec` 已經變複雜」。**四位都說 exec 本身仍可保持簡單**：彙整、claim、
套本地 kernel、執行、release。開始長歪的是周邊把還沒發生的 workflow 問題提早做成耐久 OS ABI。

| 還算簡單、可保留 | 開始長歪的延伸 | 誰這樣判斷 |
|---|---|---|
| 單一 world 的 `.aos`、本地單層 kernel、`inst.json`／tempd／`.runi` | kernel 分層繼承、父政策與多層版本現場 | 工程師、架構師、研究人員、開發者都保留本地 kernel，並把分層列為未有實例 |
| 普通 instruction 呼叫另一個命令 | 把呼叫關係固定成 lane／root／proc-table／capability／promotion 的通用行程樹 | **四位獨立地都把這裡標成主要長歪點** |
| 唯一 temp＋rename 的原子投遞 | 公開檔／目錄 Publish、跨 filesystem 與斷電 durability 契約 | **四位都把公開 Publish 收回**，先降為 Deliver 內部 helper |
| `.runi` 留住本地未完成批次 | 通用 Effect／recover 想替所有 provider 與副作用做恢復 | **四位都把 Effect 延後**；unknown 暫歸 adapter／人 |
| 串行 driver 決定要不要投下一批 | 平行 join、barrier、跨 lane commit 與 exactly-once receipt | 工程師收回 join；四位都說目前沒有平行 workload |

所以本輪沒有否定使用者已收下的 `kernel.json`；它被收窄回**每個 world 自己的序言／尾聲**。被
否定的是：在 agent loop 一次都沒跑之前，就讓 kernel 繼承、行程親緣、可搬身分與外部效果一起
變成標準的一部分。

---

## 四、從第一原理重來，會長出同一套東西嗎

**四位獨立地從頭推，都長出幾乎同一個最小版本，而且沒有長回 lane／proc-table／Effect。**只
保留使用者指定的三個前提：「資料夾是世界／一回合是一批指令／`rename` 是唯一的原子操作」，
再加已拍板的本地 kernel，得到的是：

```text
<world>/.aos/{kernel.json, inst.json, inst.tempd, .runi}
aos exec <world>
aos deliver <world> -
driver 腳本 + 真 LLM CLI + 一個受限工具
```

最小 golden slice 的實際順序是：

1. driver 腳本組 prompt，呼叫一支**已指名**的真 LLM CLI。
2. response 先寫 temp，再 rename 成完整結果。
3. translator 只接受具名工具，把它映射到預先固定的 argv；未知工具停住。
4. `aos deliver` 把工具 instruction 原子投進 queue；`aos exec` 推一回合。
5. 工具結果同樣 temp＋rename，再 Deliver 回 driver／模型。
6. 模型回 final 時不投遞下一批，loop 自然停止。

crash 時沿用 `.runi` 停住，不自動假裝恢復遠端效果。腳本可以寫 attempt／response 日誌，但先不
宣告那套檔名是 core ABI。逐點 kill 這條三回合鏈，記錄哪一步重複、哪一步難寫、哪一步無法判定，
才決定下一個 core 原語。

四位版本的差異只在命令叫 `aos deliver` 還是 `aos core deliver --to BASE -`，以及 state 檔的
名字；**沒有一位從第一原理重新推導出公開 Publish、通用 Effect、UUID、promotion 或 process
manager 是首版必需。**

---

## 五、有沒有哪個問題其實不存在

使用者的實際處境是：**一個人的專案、`core/inst` 剛落地、agent loop 還沒跑過一次。**四位依這個
尺度，把問題分成「現在有證據」與「等觸發條件出現再重開」：

| 目前先當作不存在／不承諾 | 現在有什麼證據 | 砍掉後由誰負責 | 什麼出現時再重開 |
|---|---|---|---|
| 同一 OS 行程推多世界、World multiplex | 還沒有第二個 world | 一次只跑一個 `aos exec <folder>` | 啟動成本或協調需求真的要求同一行程同時持有兩個 world |
| lane／proc-table／root capability／跨 lane commit | 沒有多 lane、共享 writer 或惡意子行程 | driver 依序呼叫；同一使用者權限下先當守約工具 | 第二個長壽 world、共享寫入或必須強制隔離的執行者出現 |
| 活搬、UUID、`slot@generation`、路徑與身分分離 | 沒有活搬，也沒有 stale receipt 誤投 | 用路徑定位；移動視為停機後另開，不承諾續接 | 真正要帶著未完成 join／receipt 搬，或同名重建收錯結果 |
| job→lane promotion、A／B scheduler 可替換 | 連一條 agent loop 都沒跑過 | 首版不分 job／lane；driver 只投下一批 | 某個工作真的需要跨回合等待、獨立 queue 與恢復 |
| 平行工具 join／barrier | 首版可串行，沒有平行工具 workload | driver 一次只叫一個工具 | 串行成為實測瓶頸，或模型一次 tool calls 必須並行 |
| 分層 kernel／父政策 | 單機單人，沒有大量子世界要同步政策 | 每個 world 一份本地 kernel，由人／腳本更新 | 多份 kernel 實際漂移，且重複升級已成痛點 |
| 通用 Effect 與 exactly-once 外呼 | remote unknown 是真問題，但尚無一支 CLI 的實際故障資料 | provider adapter 記 attempt；unknown 停住交給人 | 同一套 run／resolve 在兩個 adapter 以上重複，且狀態能脫離 provider 語意 |
| Deliver 的跨回合 key 去重 | aggregate 會刪檔，現在沒有 ledger 可支持承諾 | Deliver 只保原子發布；caller 自己避免重送 | 真正發生重送，並能定義 ledger 壽命與清理政策 |

這裡的「不存在」不是永遠不做，而是**現在不把預測寫成 ABI**。四位的共同門檻是：先有第二個
實例、一次實際事故，或至少兩支腳本重複同一段難寫機制，再讓它申請進 core。

---

## 六、有沒有漏掉比上面全部都重要的事

有兩塊，而且四位都把它們排到抽象設計之前。

### 模型輸出的執行權與威脅模型

資深工程師、資深架構師、要接工具的開發者**三位獨立地指出同一個更高優先風險**：若 translator
把模型輸出的任意 argv 直接交給 POSIX 執行，prompt injection 就取得了使用者的檔案、網路、憑證
與命令權限。前面討論的 capability 若所有程式都跑同一 UID，只是約定，擋不住這件事。

首版責任不能丟給不存在的通用 capability：三位給的最小邊界是**具名 tool allowlist → 固定 argv
映射**；未知工具停住，視威脅模型再加人工核准或 OS sandbox。使用者必須先說 T5 是全信任玩具，
還是會碰真實資料與憑證，才能知道哪一層是必要的。

### 一條真的可執行、可殺死、可觀察的 golden slice

**四位獨立地都要求先跑真 CLI 並注入 crash**：工程師要真實 LLM CLI＋受限工具來回；架構師要
最小 loop 並逐點 crash；研究人員把它叫 executable golden slice；開發者要求端到端與 crash-window
測試。這不是再寫一份規格，而是實際跑模型→工具→模型，在每一步記：

- 哪個檔一旦 rename 就是事實；
- Ctrl-C、hard kill、斷電各留下什麼；
- `.runi` 何時擋住重啟，人工要處理什麼；
- CLI 的 stdout、streaming、exit、截斷與 tool-call schema 實際長什麼；
- 哪一段 temp＋rename／掃檔／補投真的重複到值得進 core。

研究人員的一句話收住了這輪：

> **先跑出可殺死、可觀察的 loop；除 deliver 外，讓重複痛點再申請進 core。**

---

## 續場資訊

本輪沿用〈四個選擇〉與〈agent loop〉兩場的四個 codex session；它們仍保留前情。session id
**只在 office Windows 那台機器有效**；`codex exec resume <id>` **不吃 `-s` 與 `-C`**。

| 身份 | session id |
|---|---|
| 資深工程師 | `01a03676-8fa3-7622-aee8-05801a7059d3` |
| 資深架構師 | `01a0367b-797f-7403-999e-fe2c685a8c10` |
| 資深研究人員（OS／體系結構） | `01a03683-95cb-7331-8528-d1513a6c806f` |
| 要接這個工具的開發者 | `01a03688-8b4c-70b0-87e3-ea28be9b7f9c` |

---

## 轉交提案（未拍板，不自行改規格／roadmap）

1. **拍板近期 scope 回撤。**近期 core 候選只保留最小 Deliver；公開 Publish、通用 Effect、
   lane／proc-table／capability／promotion／UUID／generation／join／分層 kernel 全部退回「有實測
   觸發條件再重開」。這會改變前兩場的 roadmap／規格方向，必須由使用者確認，書記不自行回寫。

2. **拍板最小 Deliver 的誠實契約。**只承諾 schema／大小檢查、唯一同目錄 temp、write-all、
   rename 入 queue；不承諾沒有 ledger 支撐的跨回合 Already／Conflict。仍要由使用者定 CLI 名稱、
   BASE／world 傳法，以及是否只保 rename 可見性或另有 fsync 選項。

3. **指定 T5 的第一支真 LLM CLI 與最小 golden slice。**範圍收成單一 world、單一串行工具、
   模型→工具→模型三回合；driver／adapter 先是腳本，prompt／response／result 檔名也先是實驗格式，
   不直接升成 core ABI。

4. **先定威脅模型，再讓模型碰工具。**使用者需決定 T5 是全信任實驗，還是會碰真實檔案、網路
   與憑證。首版至少採具名工具 allowlist 與固定 argv；未知工具停住。人工核准或 sandbox 是否
   立即需要，取決於這個拍板。

5. **定義 crash 測試承諾。**分開 Ctrl-C、hard kill、斷電，不再混稱「可恢復」；逐點 kill 並
   記錄 `.runi`、temp、已 rename 結果與人工處置。第一輪可以只觀察，不先承諾自動恢復全部情況。

6. **採用「有證據才升 core」的重開門檻。**兩支腳本重複同一發布交易，再考慮公開 Publish；
   兩個 provider adapter 重複同一 unknown 狀態機，再考慮 Effect；第二個長壽 world／共享 writer
   出現，再重開行程機制；平行工具成為實際需求，再談 join／barrier；stale receipt 真出現，再加
   generation／ledger。

7. **三份舊紀錄先維持歷史，不直接當規格。**本輪審視若獲使用者拍板，再把保留／撤回項轉交
   roadmap 或規格；在那之前，[核心行程紀錄](core-process-and-subprocess.md)、[四個選擇紀錄](four-open-choices-tradeoffs.md)、
   [agent loop 紀錄](agent-loop-architecture.md)都只是研討過程，不由書記改寫成新真源。
