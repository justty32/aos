# 2026-09-30 使用者方向（十一）：tick 是 aos 的衡量基準

← [裁定索引](README.md)｜[筆記索引](../README.md)

本份收：第二十批（09-30，第十九批修正輪進行中）。全部裁定後批優先，見[裁定索引](README.md)。以下皆為〔使用者方向 2026-09-30，第二十批〕。**尚未落進 spec。**

## 方向

1. **tick 是 aos 體系的衡量基準。** 排程時以 tick 為基本單位，例如「這個任務要花十個 tick」。
2. **排程行為也在 tick 任務表上做。**
3. **整個 aos 體系都應該基於 tick。**
4. **先前說的 daemon IPC（tick–daemon 通道，[第十九批](10-tick-minimal-core.md)第 9 條）是唯一的逃生口。**

## 追答（同日）

1. **一個 tick 的長度**：每個 tick 有標準長度（由它的週期 `interval_ms` 決定），「10 個 tick」大約等於 10 個週期（b）。
2. **「花幾個 tick」算誰的**：算**安排它的上層**的 tick（b）。例如上層說「給你 10 格」，就是上層的 10 格。
3. **排程的做法**：aos 的排程行為就是**一個程式，掛在 tick 任務表上，只在每次 tick 時執行**。就這個原則。
4. **哪些毫秒改成 tick**：aos 內部自己決定的改成 tick（保留期、失聯判斷、重試間隔、預算等）；外部世界規定的保留毫秒（LLM 供應商限流窗口、HTTP 逾時、daemon 叫醒 tick 的週期等）（b）。
5. **唯一逃生口**：對——除了 tick–daemon 通道上的事（登記、掛行程、叫醒、傳訊），其他所有事都必須在某一格 tick 裡做，不准有別的背景程序或常駐服務繞過 tick。
6. **上下層週期不同造成的落差不管。** 上層說「給你 10 格」算上層的格，下層週期短就多跑幾格。
7. **反應速度就是一格。** 排程每格才跑，「立刻處理」最快是下一格；只有走通道的急件叫醒例外。spec 裡「收到就處理」改成「下一格處理」。
8. **cgroup、git 從標準配備拿出來**（使用者請記錄者評估後，三項都接受）：
   - **git 做成任務表上的兩項任務**：開格一項（上一格做到一半就還原到上次提交）、收尾一項（看本格各項結果，成功提交、失敗還原失敗組）。**核心多開放「本格每項結束碼紀錄」**讓後面的任務讀得到。「提交成功才刪原件」改成下一格開格時刪上一格已提交的原件；git 與無 git 的日誌備援合成同一種模式。needs／group 的失敗整組還原跟著搬進收尾任務。tick 本身不再保證整格原子，掛了 git 任務才有。
   - **cgroup 拆開**：node 框與資源上限歸 daemon／helper；一格結束後殺殘留歸 daemon 收尾（已有）；每項任務一框改成**包裝程式**（例如 `aos-cg -- 原指令`），要的任務才包。放棄「沒包裝的任務一結束就清殘留」。
   - **切換使用者也做成包裝**（例如 `aos-as <帳號> -- 原指令`），由它請 helper 開程序並交鎖。
   - **「標準配備」改成「標準任務表範本」**：git 開格 → 收件 → 使用者任務（需要的包 `aos-cg`／`aos-as`）→ 投件 → 發摘要 → 清理 → git 收尾。tick 核心剩：鎖、照表跑、上下層、每項結束碼紀錄。推翻第十九批的「標準配備同一支 aos-tick 分層」「有備援仍算全掛」等結構。
9. **拆出來的這些就是「系統級任務」。** git 開格／收尾、收件、投件、發摘要、清理等從 tick 核心拆出、掛在任務表上的程式，統稱系統級任務，任務表上以 `kind: "system"` 標記；標準任務表範本就是預設的一組系統級任務。`aos-cg`、`aos-as` 這類包裝**不算系統級任務，是普通程式**——任務會用到的工具。

## 改寫計畫疑點的裁定（同日）

題號對應[第二十批改寫計畫](../reviews/2026-09-30/batch20-plan.md)的疑點。

1. **任務可以叫核心停掉本格剩下的任務**：~~核心認一個特別的結束碼~~（同日改口）**改成偵測特定檔案**——任務要停掉本格就建立約定的檔案，核心每跑完一項檢查它，存在就不跑後面的項。檔名、誰清除、整格結束碼由落 spec 隊寫成建議預設。
2. **needs（前一項失敗就跳過後一項）做成包裝 `aos-needs`**（b），核心不做。
3. **git 收尾靠存檔點找失敗組的改動**：每組跑完打一個存檔點（a）。
4. **投件與發摘要搬到 git 收尾之後**（b），保住「先提交再送出」。
5. **「git 與無 git 合成一種模式」＝核心的結束碼紀錄直接取代日誌**（c）。
6. **任務的 `user` 保留**；跟 tick 帳號不同時核心回 125，要切帳號就自己包 `aos-as`（a）。
7. **起點時間戳直接換成格數**（b）。
8. **CLI 或工具在 tick 之外上鎖改檔：當成外部世界，不管**（c）。

疑點 9～14 與上一輪留下的 4 題使用者未答，落 spec 時照計畫的建議預設與暫定寫，條文標「暫定」。

## 進行順序（同日）

**先把 tick 與 daemon 的 spec 基礎設計好，假設 cgroup 與 git 都不存在；下一步才把這兩個納入。** 本輪改寫只做 tick 核心、系統級任務（不含 git 任務）、daemon（不含 cgroup）與通道；git 開格／收尾任務、`aos-cg`、daemon 的 node 框與上限等，先移到明確標「下一步納入」的位置，不在本輪設計。kernel、agent、LLM 等其他篇等基礎定了再跟上。
- **任務環境變數命名**（同日）：`AOS_TASK_ID` 是字串，照任務表該項 `id` 原樣；第幾項用 **`AOS_TASK_INDEX`**（從 0 起算，等於任務表陣列位置）。整格共用的用 `AOS_TICK_*`，這一項專屬的用 `AOS_TASK_*`。結束碼紀錄裡「在哪一項之後停」記 `id` 字串。
- **daemon 何時暫停 node**（同日，先答 a＋c，隨即修正）：**停格檔 `.aos/tick/stop` 只在任務層面**，只阻擋本格剩餘任務，daemon 不因它暫停 node；**擋板檔 `.aos/tick-blocked` 才阻擋之後的格**，有它時 daemon 不開格。不看結束碼。
- **tick／daemon 基礎輪的疑點**（同日）：以下四題接受暫定、改為定案——沒有 cgroup 時 daemon 重啟清不掉舊程序（接受）；daemon 自己的開格故障仍自動暫停 node（保留當安全閘）；沒有 git 時當機留下的消費副本當成已收；清理預設 `retention_ticks` 100000、`interval_ticks` 1000。
- **任務表欄位**：先只定基本欄位；`group`、`needs` 不列入，**當成陌生 key**（任務是 inst 超集，不認得的鍵照收、核心忽略）。
- **整理區**（同日）：把已定的 tick 與 daemon 基礎整理好，和其他東西（kernel、agent、LLM、CLI 等）分開，放進一個獨立區域 `proto6/spec/settled/`；其他篇整理好、跟上新基礎後再一起放進去。同時開始**納入 cgroup 與 git** 輪（先出改寫計畫與疑點）。

## 納入 cgroup 與 git：疑點裁定（同日）

題號對應[納入 cgroup 與 git 的改寫計畫](../reviews/2026-09-30/batch20-cg-git-plan.md)第五節。

- **疑-7：准，照第十八批 Q19。** node 在自己框裡另開子框、留常駐程序也是逃生口，**不管**——這不在 aos 管轄範圍內（計畫第四節「跟唯一逃生口衝突」一項因此不算衝突）。
- **git 背景自動整理（gc／maintenance）：不管**，只在文件建議使用者關掉。使用者追問「或是我們執行時自己不啟用？」——記錄者回答可以：aos 自己呼叫 git 時帶 `-c gc.auto=0 -c maintenance.auto=false`，不動使用者的設定、只管 aos 自己那幾次呼叫；落 spec 時以此為預設，另寫建議。
- **疑-3：人手改的東西不管。** 文件告訴人：要手改 node 內容，先暫停（pause）再改；不做 rescue ref。
- **疑-5：噴警告。** 掛了 git 任務但 git 不能用時印警告；記錄者理解為一律照沒 git 的做法繼續（不寫擋板）。
- 其餘照計畫建議：疑-1 a、疑-2 b、疑-4 b、疑-6 b、疑-8 a、疑-9 a、疑-10 b、疑-11 a、疑-12 a。

## astra 審整理區：裁定（同日）

題號對應 [astra 審整理區報告](../reviews/2026-09-30/astra-settled-report.md)。

- **裁-1 多個任務共用通道收件：③ 每個 node 只准一個任務取件（通道消費者），由它分派。** 〔同日改口〕~~分派以先搶先贏為基礎~~——**分派怎麼做 aos 不管**，由那個取件任務的實作自己決定。〔同日再補〕**取件的就是收件系統級任務（`kind:"system"` 的收件，範本裡原叫 aos-inbox）**，不另設定「哪個任務來收」。
- **裁-2 daemon 自己的計時：② 只有叫醒週期、OS 收尾寬限這類外部／OS 層的保留毫秒；政策性的保留期（例如診斷保留期）改用所屬上層的格數。**

- **收件系統級任務改名**（同日，再改）：不叫 inbox——「inbox」這個名字使用者之後要拿去別處用；~~暫名 aos-intake~~ 使用者定名 **`aos-sysinbox`**。
- **通道取件與一般收件分開**（同日）：**通道取件由 `kind:"system"` 的 `aos-sysinbox` 處理**；其他取件（一般收件）用的任務不一樣，**隨意，aos 不管**。
- **一般檔案收件不歸 aos 管**（同日，選 a）：收件（檔案收件區 `requests/`、`responses/` 的讀取、回 -32601、刪原件等）**就是一個程式、掛在任務表上的一個普通任務，就這樣而已**；不是系統級任務，aos 不規定它怎麼做。系統級任務裡管「收」的只剩 `aos-sysinbox`（通道取件）。
- **系統級收送改名為系統訊息佇列 `aos-mq`**（同日）：使用者說系統級的收件寄件不該用寄信收信描述，比較像 aos 的系統級 IPC、更像消息處理系統。定名 **`aos-mq`**（中文「系統訊息佇列」），一支程式兩個子指令：每格開頭 `aos-mq get`（id `mq-get`，從通道取出本格訊息，取代 aos-sysinbox）、每格收尾 `aos-mq post`（id `mq-post`，取代 aos-outbox）。取出後怎麼分派 aos 不管。
- **`aos-mq post` 只走通道**（同日，選 a）：送出只經 tick–daemon 通道送進對方的佇列，**不再寫對方的 `requests/`**。檔案收件區（`requests/`、`responses/`）的收與寫都只是普通程式，aos 不管。
- **aos-git 的分工**（同日，使用者原話整理）：`aos-git open`／`close` 處理的都是 tick、daemon 相關，以及 `kind:"system"` 任務相關的東西。`kind:"system"` 那一串任務之間**夾雜 `aos-git mark` 做存檔**（範本自帶）；**其他 kind 的任務要自己呼叫、摻入 `aos-git` 做存檔**，範本不替它們插存檔點。
  - **提交與還原的範圍：只限 aos 自己的東西**（選 b）：`.aos/`、任務表、系統級任務動到的檔。使用者任務改的檔，aos 不提交也不還原，要存檔就自己呼叫 `aos-git`。因此 aos 不再保證整格原子，**只保證 aos 自己的東西——也就是 `kind:"system"` 任務與 tick／daemon 基底——是原子的**（使用者原話）。
  - 失敗時還原到「往前最近的存檔點」（不分範本放的或任務自己打的）：記錄者建議，使用者未另表示，暫定。

## 修正輪暫定的裁定（同日）

- **格數不倒退：改成不保證。** 預設不 fsync，斷電或 WSL 強關後格數可能倒退；可用 `aos-daemon --firstdo-fsync`／`aos-tick --firstdo-fsync` 開啟「開格那一次 fsync」，開了才保證不倒退（旗標名照使用者原話）。
- **回應也走 `aos-mq`**：佇列同時收請求與回應。
- **佇列授權判準選 c**：仍看某資料夾的寫權，換成 `.aos/mq/` 底下的資料夾（不再看 `requests/`）。
- **`mq-post` 送不出去的：不保留、不重試，但留下失敗紀錄，下一格清掉。**
- **daemon 的 pause 存檔間隔與事項批次：保留毫秒**（daemon 不在格內）。
- **runner 當收屍人：定案**（原修正輪暫定）。runner 讓子程式另開程序群組，主程式結束就殺光名下後代再回報；daemon 收尾對 runner 送兩次 SIGTERM（第一次轉給子程式、第二次叫它清空）。runner 意外死掉時，掛回 daemon 的程序一律殺掉、那一格記結果不明。
- **納入 cgroup／git 輪的 13 題暫定**（整理區 README 疑點 1～13）：使用者說「隨意」——照暫定寫法改為定案；沒給做法的（同 ID 請求與回應撞檔名）由落 spec 者挑最簡單的做法。

## 2026-10-01：POC 默認一切正常

〔使用者方向 2026-10-01〕Python POC（[plan 第一段待問 8](../../plan/m1-tick-core.md#待問)）。使用者原話：「我們都默認所有東西都OK都正常，先不考慮邊緣狀況」「紀錄這邊，我們都默認紀錄是好的」「舊紀錄不管，我們都默認紀錄能讀得懂」「--firstdo-fsync...先不做吧，我們先做單純的」「別人正在跑？默認沒有別人在跑，這個不管，或是直接報錯。然後也不需要判斷上下層。」「表不合法也拿掉，回 0／1 就好」「帳號不對，也不管」。

- **總原則**：默認環境一切正常——檔案寫得進、讀得懂、沒壞、不斷電。不為異常寫處理，出事就讓它自然丟錯（Python traceback，回 1）。
- **紀錄**：`current.json`／`last.json` 默認是好的；舊紀錄讀不懂（`record_unreadable`）不處理。寫紀錄失敗回 1、跟任務失敗分不出來，照舊。
- **`--firstdo-fsync`**（含 `AOS_TICK_FIRSTDO_FSYNC`）：POC 先不做。
- **同資料夾互斥（B-602）**：~~默認沒有別人在跑，整個拿掉——不取鎖、不回 75、不傳鎖 fd。~~（同日加回最簡版，拿不到鎖回 ~~2~~ 0，見下面「aos-tick 最簡互斥與讀表時機」與「結束碼慣例改版」）
- **上下層判定（B-628）**：不需要，拿掉。
- **任務表不合法**：拿掉驗表與回 2，默認表是對的；整格碼只剩 0／1。
- **帳號**：tick 不看 `user`、不回 125，照自己的帳號跑。
- spec 規定本身不刪，只標〔使用者方向 2026-10-01：POC 先不做〕。

<a id="aos-結束碼慣例待統一更新-spec"></a>

### aos 結束碼慣例（已寫入 spec（commit 前由我補號））

〔使用者方向 2026-10-01〕使用者原話：「我預期0是通用正常結束，1是通用錯誤結束，2是通用正常中斷。所以block檔應該算2。任務的結束碼這塊我們也按照這樣的慣例。你可以先規定aos體系下的結束碼慣例。」「確實要拿掉退路，aos-tick就是在指定了--node之後，去吃.aos/inst.json，這是必要。」「以上都拿先記錄下來，之後統一拿去更新spec。」「停格檔算是正常結束，甚至不算中斷。關於block和stop檔案，這塊的機制我之後還會詳細設計」「任務出錯，不算在tick的錯誤內」「任務回2也只記一筆，照常跑下一項」。

**同日改版（取代上面原話裡的「2＝通用正常中斷」「block檔應該算2」）**〔使用者方向 2026-10-01〕使用者原話：「結束碼這塊，我覺得不要2了，只要是正常的，不須多做處理的，通通0，0以外就是需要額外處理的東西。或者說0，就是在我們預料之中，算是正常狀況的事情，一切正常都歸類在0，0以外就是不正常。」「只有0才是普通結束，正常中斷也改成0。」「改成0，還有0以外。1就是通用錯誤，所以沒特別設置結束碼的錯誤都設1。」

**這節是正本，已寫入 spec（commit 前由我補號）**（到時新增一篇整理區規定、給新條號，並在舊碼表處標註指過來；見下面「待改的 spec 處」）。使用者的整體圖像：外層是定期執行的 `aos-exec`，它讀的 `inst.json` 的 `argv` 第一個就是 `aos-tick`。

**慣例本身（改版後）**

- **0＝預料之中**：一切正常都歸 0，含「正常中斷」（該停就停、不用多做處理的）。只有 0 是普通結束。
- **非 0＝不正常，要額外處理。**
- **1＝通用錯誤**：沒特別指定碼的錯一律回 1（檔案讀不到／寫不進／格式壞、參數錯、argv 用法錯、程式起不來、其他沒接住的錯）。argv 用法錯算 1（Python argparse 預設 2，要改）。沒接住的例外照 Python 預設回 1、traceback 進 stderr。
- **特別指定的碼**照各自規定保留（例如 inst 規定的 125／126／127、子程式碼原樣傳出），都屬「非 0」。
- 不再有「2＝正常中斷」。讀任務結束碼時只分 0 與非 0，紀錄裡照實記原碼。
- 注意：外部程式不懂這慣例（例如 `grep` 回 1 表「沒找到」）。不特別處理——慣例只約束 aos 自己的程式；外部程式要放進任務表，由使用者自己包一層轉碼。
- ~~0＝正常結束；1＝錯誤結束；2＝正常中斷（該停就停，不是出錯）。aos 自己的程式只回這三種。讀任務結束碼時：0、1、2 照上；其他碼一律當 1 看。~~（同日改版作廢）

**aos-tick 的碼**（只講 tick 自己，任務的碼完全不影響它）

| 狀況 | 回 |
|---|---|
| 照表跑完（不管任務回 0、1、2、其他碼、被訊號殺，都照實記進紀錄、照常跑下一項） | 0 |
| 看到停格檔 `.aos/tick/stop`，剩下不跑：**不算中斷**（紀錄照舊記 `stopped_after`） | 0 |
| 同資料夾上一格還沒跑完（拿不到 `.aos/tick.lock`，stderr `busy:`），不開格（不寫紀錄、不加 `seq`） | ~~2~~ 0（改版） |
| 有擋板檔 `.aos/tick-blocked`，不開格（不寫紀錄、不加 `seq`，照原規定；stderr `blocked:`） | ~~2~~ 0（改版） |
| tick 自用的檔（`tick-blocked`、`stop`、`current.json`、`last.json`、`tasks.json`）讀不到／寫不進／格式壞、argv 用法錯、`AOS_DIRNAME` 不合法、`--node` 不對、~~`--node` 底下沒有 `.aos/inst.json`~~ `--node` 資料夾底下沒有 `.aos/tasks.json`、任務表不合極簡檢查 | 1（直接中斷、stderr，不分發生時機、不補救） |

aos-tick 現在只回 0／1。busy、擋板仍各印一行 stderr（`busy:`、`blocked:`），外層要分可以看 stderr。

**aos-exec 的碼（改版後，本輪已改程式）**

| 狀況 | 回 |
|---|---|
| 子程式跑完一次：它的結束碼原樣傳出（含 0、被訊號 N 殺＝128+N、找不到程式 127、沒執行權 126） | 原碼 |
| aos-exec 自己失敗，那次沒跑（inst 壞、指示詞解不開、`.json` 不存在、mkdir／cwd／重導向失敗） | 125（inst 特別指定，保留） |
| 用法錯：argv 錯（含 argparse 的）、`--timeout-ms` 負數、目標不存在、資料夾目標找不到 inst、inst 目標給了 `--`、`AOS_DIRNAME` 不合法 | ~~2~~ 1 |
| 沒接住的例外 | 1（Python 預設） |
| `-h`／`--help` | 0 |

`run_target()` 回的 `(code, "usage")` 的 code 也由 2 改 1；`kind` 照舊分 child／aos／usage。aos-exec 外包 `aos-tick` 時 tick 的 0／1 原樣傳出。

- **拿掉退路**：不再「沒有 `.aos/` 就交給 aos-exec 跑 `inst.json`」（作廢 [plan 第一段待問 5、6](../../plan/m1-tick-core.md#待問) 那條）。`--node` 指的資料夾必須有 `.aos/inst.json`，沒有就回 1；任務仍照 `.aos/tasks.json`。
- **擋板檔與停格檔的機制使用者之後會詳細設計，目前做法是暫定。**
- 整格碼只剩「tick 自己」的意思後，紀錄收尾的 `exit` 只會是 0（擋板、busy 不寫紀錄；出錯時紀錄停在 `ended:false`）。
- 先前一度定的「任務回 2 讓剩下不跑、tick 回 2」「任務錯讓 tick 回 1」「錯誤優先」同日都撤回；「停格檔與任務回 2 部分重疊」的待議也隨之刪掉。

**待改的 spec 處**（統一更新時照這節改，舊文不刪就劃線或註記〔使用者方向 2026-10-01〕指向新篇）

- [P-203](../../spec/settled/protocol/tick.md#p-203aos-tick-與任意任務程式建議預設未拍板) 的結束碼表（0／1／2／75）與 argv 用法錯的碼：改成 aos-tick 只回 0／1（busy、擋板都 0）。
- [B-620](../../spec/settled/tick.md#b-620任務註冊表照表依序跑)：擋板檔回 1 → 0、停格檔回 1 → 0、「任務表」處「沒有 `.aos/` 照 aos-exec 跑」的退路。
- 新增的通用慣例篇：寫改版後的「0＝預料之中、非 0＝要額外處理、1＝通用錯誤、特別指定的碼另列」，不要寫成 0／1／2。
- [B-633](../../spec/settled/tick.md#b-633每項結束碼紀錄與格數)／P-213 與 `node-tick-record` schema 的描述：「`stopped_after` 時 `exit` 必須是 1」「exit 1 時有失敗或停下」這類跨欄位規則（schema 的 `exit` enum 本來就收 0／1／2，不用改）。
- 其他寫「整格回 0／1」或把任務失敗算成整格失敗的地方（V-03 相關場景等）。
- ~~從 proto5 複製的 `aos-exec` 這輪不改碼，跟慣例不合處：用法錯回 2（慣例要 1，且 2 會被讀成正常中斷）；自己失敗（inst 壞、`user` 不合）回 125；子程式的碼原樣傳出（126／127、128+N 都會冒出來）。~~（改版後已改程式：用法錯 2 → 1；125／126／127 與子程式碼屬特別指定的碼，保留，見上面「aos-exec 的碼」）spec 要改的：[inst.md](../../spec/base/inst.md)「inst 目標」的「資料夾裡兩個位置都沒有＝用法錯（2）」與執行一節「runner 的用法錯誤回 2」改 1，conformance 裡寫 aos-exec「用法錯 2」的地方同。
- spec 其他命令列（`aos node check`、`aos work trace`、kernel 工具、ops、daemon 設定錯等）也多寫「2 用法錯」、有的用 2 表「不合法」：改版後的慣例照字面是「沒特別指定的錯都 1」，這些是不是一律改 1、還是當「特別指定」保留，統一更新時逐條定（本輪只改了 aos-tick 與 aos-exec 的程式）。
- [P-203](../../spec/settled/protocol/tick.md#p-203aos-tick-與任意任務程式建議預設未拍板) 的 argv 那段與 [B-602](../../spec/settled/tick.md#b-602同一資料夾一次一格互斥鎖)「認哪個資料夾」：`--node` 改照下一節（省略用 `./`、相對轉絕對、資料夾看 `.aos/tasks.json`、給檔當任務表）；拿掉「必須絕對路徑」與「`.aos/inst.json`／`inst.json` 正規化成資料夾」。上面碼表「`--node` 底下沒有 `.aos/inst.json`」也照下一節改成 `.aos/tasks.json`。

<a id="aos-tick---node-怎麼認待統一更新-spec"></a>

### aos-tick `--node` 怎麼認（已寫入 spec（commit 前由我補號））

〔使用者方向 2026-10-01〕使用者原話：「如果--node xxx，xxx沒指定，那就是默認./。然後這邊我要加個機制：如果xxx是檔案，那該檔案必須符合task.json格式，而該檔案所在的資料夾yyy，將其作為--node yyy，後續正常執行。aos-tick --node xxx，判斷是否合法，應該是要判斷是否有.aos/task.json，和inst.json分開。」（`task.json` 即現有的 `tasks.json`。）

**這節是正本，已寫入 spec（commit 前由我補號）**（見上面「待改的 spec 處」P-203 argv 那條）。取代上一節「`--node` 底下必須有 `.aos/inst.json`」那半句；退路照舊拿掉。

- **沒給 `--node`**：用目前目錄 `./`。**相對路徑**一律轉成絕對路徑再用（拿掉「必須絕對路徑」）；node id 仍是絕對路徑。
- **`--node` 是資料夾**：合法＝有 `.aos/tasks.json`；不看 `.aos/inst.json`（tick 跟 inst.json 分開）。沒有就回 1、stderr 一行。
- **`--node` 是檔**：這個檔就是這一格的任務表；它所在的資料夾 yyy 當 node，擋板檔、停格檔、紀錄都在 `yyy/.aos/` 下。`yyy/.aos/tasks.json` 在不在都不管。`yyy/.aos/`、`yyy/.aos/tick/` 不在就建（只建資料夾）。「必須符合 tasks.json 格式」：~~照 POC 默認一切正常，不另驗，讀壞了自然丟錯回 1~~（同日再改：照下一節的極簡檢查，不過回 1）。
- **`--node` 指的東西不存在**：回 1。
- 結束碼照上一節碼表（0／1／2），不變。
- **表裡的相對路徑與指示詞**（同日追加）：以 node 根為中心——給檔時就是該檔所在的資料夾（叫 `.aos` 時是它的上一層，見下）。
- 實作時自己定的（使用者沒講，可改）：給的檔所在資料夾叫 `.aos` 時（例如 `yyy/.aos/tasks.json`），node 取 `.aos` 的上一層 `yyy`，不照字面當 `yyy/.aos`；舊的 `--node yyy/.aos/inst.json` 因此變成「拿 inst.json 當任務表」，沒有 `tasks` 陣列、過不了極簡檢查回 1。stderr 代碼 `no_tasks`（資料夾沒有 `.aos/tasks.json`）、`no_node`（不存在）。

<a id="aos-tick-讀任務表的極簡檢查待統一更新-spec"></a>

### aos-tick 讀任務表的極簡檢查（已寫入 spec（commit 前由我補號））

〔使用者方向 2026-10-01〕使用者原話（依序）：「task.json的格式錯誤的話，那aos-tick就是回1，這應該算在非正常錯誤」「所謂的格式錯誤，就是該填的沒填，然後不符合{"tasks":[]}這樣的格式，其他就不檢查。」「kind不填」「最外層不用檢查_metainfo，每一項也只需要檢查argv」「拿掉」（指任務表的 `methods`）「沒寫id的時候，那就是以其在tasks陣列中的index做id。直接數字轉字串。默認不重複」。檔名確定是 `tasks.json`。

**這節是正本，已寫入 spec（commit 前由我補號）。** 取代上面「POC 默認一切正常」裡「任務表不合法：拿掉驗表」那條與「表壞自然丟錯」的做法。

- **格式錯算 tick 自己的錯**：stderr 一行（`bad_table: …`）、回 1。給檔（`--node` 是檔）時一樣。
- **只查這幾件**：讀得到、合法 JSON、頂層是物件且有 `tasks` 陣列；每一項（整份 `$ref` 先展開，展開不了也算格式錯）是物件且有 `argv`。
- **沒寫 `id` 的項**：id＝它在 `tasks` 陣列的位置（從 0 起，跟 `AOS_TASK_INDEX` 同）直接轉字串，例如 `"0"`、`"3"`；紀錄、`AOS_TASK_ID`、`stopped_after` 都用它。跟別項寫的 id 撞了也不管（默認不重複）。
- **其他一概不查**：外層與每項的 `_metainfo`、`id`、`kind`（不必填，「kind不填」）、值的型別、`kind` 的值、`id` 重不重複、陌生鍵。格式上 `_metainfo` 外層與每項仍照寫、不省略，只是 tick 不擋。
- **`methods` 從規範拿掉**：寫了就當陌生鍵照收、不理（跟 `group`、`needs` 一樣）。理由：第二十批後檔案收件是普通程式、`aos-mq` 不看 `methods`，aos 自己沒有程式用它。
- 每項沒寫 `_metainfo`：從 proto5 複製的 `aos_inst` 本來就當 posix 第 1 版，照跑；寫了但值不對，跑到那一項展開成 inst 時自然丟錯（traceback）、回 1（前面的項已跑，紀錄停在 `ended:false`），`aos_inst` 不改。
- 實作自己定的（可改）：
  - ~~檢查在「換紀錄」之後（照 B-620 順序），所以表壞的那格仍佔一個 `seq`、紀錄停在 `ended:false`。~~（同日改：移到換紀錄之前，見下一節）
  - `id` 不是字串時 `AOS_TASK_ID` 用 `str()`（紀錄照原值寫）。

**待改的 spec 處**（統一更新時照這節改）

- [P-202](../../spec/settled/protocol/tick.md#p-202任務註冊表建議預設未拍板) 的欄位表與 `node-tasks` schema 的 `required`：`kind` 改不必填；`id` 不再是核心必查（schema 是否仍列必填，統一更新時定）；`methods` 與其「同一項不重複」檢查刪掉。
- [B-620](../../spec/settled/tick.md#b-620任務註冊表照表依序跑)「讀表與誰驗什麼」：核心只做上面的極簡檢查，不過回 1。
- [B-633](../../spec/settled/tick.md#b-633每項結束碼紀錄與格數)／P-213 與 `node-tick-record` schema：`id` 的說明補「任務表沒寫 `id` 時是位置字串」；上面「任務環境變數命名」那條的 `AOS_TASK_ID` 同。

<a id="aos-tick-最簡互斥與讀表時機待統一更新-spec"></a>

### aos-tick 最簡互斥與讀表時機（已寫入 spec（commit 前由我補號））

〔使用者方向 2026-10-01〕理由：外層定期跑 `aos-tick`，上一格沒跑完下一格就來，這是正常使用會碰到的。

**這節是正本，已寫入 spec（commit 前由我補號）。** 取代上面「POC 默認一切正常」裡「同資料夾互斥整個拿掉」那條，和上一節「實作自己定的：檢查在換紀錄之後」那條。

- **加回最簡互斥**：開格前對 `<node>/.aos/tick.lock` 取非阻塞 `flock`（不存在就建）。拿不到就 stderr 一行 `busy: …`、回 ~~2（正常中斷）~~ 0（同日結束碼改版：預料之中），不寫紀錄、不加 `seq`。拿到就整格持鎖、程序結束自然放。
- **鎖 fd 不傳給任務**（Python `os.open` 預設不可繼承、`Popen` 預設 `close_fds`）；沒有 `AOS_TICK_LOCK_FD`、不回 75。任務留下的後代因此也不會佔住鎖。
- **讀表移到換紀錄之前**：任務表讀不到或極簡檢查不過 → `bad_table:`、回 1，**不算開過一格**：不換 `current.json`／`last.json`、不加 `seq`。
- **一格的順序**：認 node 與任務表 → 取鎖 → 看擋板檔 → 讀表（極簡檢查）→ 換紀錄 → 刪停格檔 → 照表跑 → 回結束碼。
- **不做**：任務逾時、tick 被殺時清它的孩子（留給 daemon 段）。任務輸出預設照 inst 接 `/dev/null`，不動。
- **照舊**：檔在 `.aos/` 裡時 node 取上一層；只寫 `--node` 不給值算用法錯回 1；`id` 非字串時 `AOS_TASK_ID` 照 `str()`。
- 實作自己定的（可改）：鎖在擋板之前（照原 B-602「取鎖是定位資料夾之後第一件事」）；同時被佔又有擋板時回 `busy:`（兩者都是 ~~2~~ 0，只差 stderr）。認資料夾失敗時還沒取鎖、什麼都不建。鎖檔 tick 不刪。

**aos-tick 碼表補一列**（已併進上面「aos 結束碼慣例」碼表）：同資料夾上一格還沒跑完（拿不到 `.aos/tick.lock`）→ ~~2~~ 0，不寫紀錄、不加 `seq`。

**待改的 spec 處**

- [B-602](../../spec/settled/tick.md#b-602同一資料夾一次一格互斥鎖)：拿不到鎖的碼 75 → ~~2~~ 0；拿掉「鎖 fd 傳給任務」與 `AOS_TICK_LOCK_FD`（P-203 環境變數表同）；「POC 先不做」的標註改成「最簡版已做」。
- [B-620](../../spec/settled/tick.md#b-620任務註冊表照表依序跑)「一格怎麼走」：讀表移到換紀錄之前；表壞不佔 `seq`。
- [B-633](../../spec/settled/tick.md#b-633每項結束碼紀錄與格數)：「表壞的格也佔一個 `seq`」一類的話拿掉。

<a id="aos_dirname-狀態資料夾的名字待統一更新-spec"></a>

### `AOS_DIRNAME` 狀態資料夾的名字（已寫入 spec（commit 前由我補號））

〔使用者方向 2026-10-01〕aos-tick 讀環境變數 `AOS_DIRNAME` 決定 node 狀態資料夾的名字；使用者追加原話：「aos-exec那邊，我覺得可以加上這個AOS_DIRNAME」。

**這節是正本，已寫入 spec（commit 前由我補號）。之後 aos 所有程式都照這個變數。**

〔使用者方向 2026-10-01，同日再改〕使用者原話：「如果AOS_DIRNAME是空的，那就從找.aos/inst.json改成找inst.json。」

- **三態**（要分得出「沒設」與「空字串」）：
  - **沒設**＝`.aos`。
  - **設了但空字串**＝不用子資料夾，直接用 node／目標資料夾本身。~~沒設或空字串＝`.aos`。~~（同日再改）
  - **其他值**＝這個名字，只換名字，位置仍在 node（或 aos-exec 的目標資料夾）裡。
- **不合法**：值含 `/`、或是 `.`、`..` → 用法錯，stderr 一行。碼照各程式自己的用法錯：`aos-tick` 回 1；`aos-exec` ~~照它現有的碼回 2~~ 回 1（同日結束碼改版）；daemon 用的 `spawn_target` 丟 `SpawnFailed`。空字串合法。
- **aos-tick**：所有原本寫死 `.aos` 的地方都照它——`tasks.json`、`tick.lock`、`tick-blocked`、`tick/stop`、`tick/current.json`／`last.json`、`--node` 合法判斷（資料夾要有 `<名字>/tasks.json`）、檔案模式「所在資料夾叫這個名字就往上取一層」的特判。環境變數照常傳給任務，不另處理。
  - 空字串時：上面這些都直接在 node 資料夾下（`<node>/tasks.json`、`<node>/tick.lock`、`<node>/tick-blocked`、`<node>/tick/stop`、`<node>/tick/current.json`／`last.json`）；「往上取一層」的特判不適用（檔所在的資料夾照字面當 node）。
- **aos-exec**：資料夾目標「先 `<目標>/.aos/inst.json`、再 `<目標>/inst.json`」的 `.aos` 照它；空字串時只找 `<目標>/inst.json`。不合法只在資料夾目標時擋（直接給檔、`.json` 目標不受影響）。
- 實作：判斷放 `proto6/src/py/lib/aos_dirname.py` 一處，aos-tick 與 aos-exec 都 import 它。

**待改的 spec 處**

- [inst.md「inst 目標」](../../spec/base/inst.md)：資料夾目標找 `.aos/inst.json` 的 `.aos` 改照 `AOS_DIRNAME`。
- [P-203](../../spec/settled/protocol/tick.md#p-203aos-tick-與任意任務程式建議預設未拍板)、P-202、P-213、B-602、B-620、B-633 等寫死 `.aos/…` 的地方：註明 `.aos` 是 `AOS_DIRNAME` 的預設值；P-203 環境變數表加 `AOS_DIRNAME`（任務照常繼承）。
- 新增一處通用規定（跟「aos 結束碼慣例」同篇或相鄰）：`AOS_DIRNAME` 的意思、三態（沒設＝`.aos`、空字串＝資料夾本身、其他＝名字）、不合法的值，以及「aos 所有程式都照它」。
- [inst.md「inst 目標」](../../spec/base/inst.md) 另補：`AOS_DIRNAME` 空字串時只找 `<目標>/inst.json`。

<a id="aos-exec-不認得頂層-user待統一更新-spec"></a>

### aos-exec 不認得頂層 `user`（已寫入 spec（commit 前由我補號））

〔使用者方向 2026-10-01〕使用者原話：「aos-exec應該也不需要認得頂層user吧。」

**這節是正本，已寫入 spec（commit 前由我補號）。**

- 從 proto5 複製的 `aos_inst`／`aos-exec` 撤回 proto6 加的「認得頂層 `user`」（解析帳號、跟目前身分不同就 `UserNotGranted`、型別錯 `UserInvalid`、都回 125）。回到 proto5 原樣：`user` 當不認得的鍵照 inst 規則忽略，照目前身分跑。
- aos-tick 原本「交給 `load_obj` 前先拿掉 `user`」因此多餘，拿掉；tick 本來就不看 `user`（見上面「POC 默認一切正常」）。
- 現在 proto6 的 aos-exec 跟 proto5 不同的只剩「資料夾目標」那一處：先找 `<目標>/.aos/inst.json` 再找 `<目標>/inst.json`，`.aos` 照 `AOS_DIRNAME`。

**待改的 spec 處**

- [inst.md](../../spec/base/inst.md) 的頂層 `user`（「形狀與版本」「先決定身分，切完才解析」等處）：aos-exec 不認得它；`user` 是否還留在 inst 第 1 版、留給誰（例如之後的 daemon／runner 切帳號）用，統一更新時定。
- B-620「任務的帳號」、P-202 欄位表裡 `user` 的說明：核心與 aos-exec 都不看。
- 寫「`user` 跟目前身分不同就 125」的地方（含 conformance 場景）。

<a id="2026-10-01最核心-daemon待統一更新-spec"></a>

## 2026-10-01：最核心 daemon（已寫入 spec（commit 前由我補號））

〔使用者方向 2026-10-01〕使用者原話：「daemon就是叫aos-exec，所以他存著的清單就是inst.json的路徑，以路徑做id……所以daemon管node這件事，會變成可掛載的模組。」草稿與細節見 [daemon 核心草稿](../2026-10-01-daemon-core-sketch.md)，細部 plan 見 [m3-daemon-core](../../plan/m3-daemon-core.md)。

**這節是正本，已寫入 spec（commit 前由我補號）。**

- **daemon 叫 `aos-exec`，不直接叫 `aos-tick`。** 它存的清單是一份份 `inst.json` 的路徑，**以路徑當 id**；~~路徑末段是 `/inst.json` 時省略這段當 id（`/n/a/inst.json` 的 id 是 `/n/a`，`/jobs/b.json` 照原樣）~~（同日撤回，id 就是字面值，見下面「設定檔追加裁定」）。
- 所以 **「daemon 管 node」變成可掛載的模組**：daemon 核心只是定期叫 `aos-exec` 跑清單上的 inst，不認得 node；要定期跑一個 node，就在 node 放一份 `argv` 開頭是 `aos-tick` 的 `inst.json`，把它的路徑加進清單。
- **設定檔可設**：某項的 `aos-exec` 結束碼非 0 時，要不要停掉該項。
- **只有 0 是普通結束**（照上面「aos 結束碼慣例」改版）；`aos-exec` 的碼改成 0／非 0（本輪已改程式，見該節「aos-exec 的碼」）。
- **週期從上一格結束起算、不補跑**；daemon 開起來時每項先各跑一格。
- **Ctrl-C**：daemon 直接退出，不殺也不等正在跑的格。
- **第一版不要 socket。**
- **設定檔欄位隨意**，實作者定。

**待改的 spec 處**

- [daemon 整理區](../../spec/settled/daemon/README.md)（B-601～B-613 等）：開格核心改成「定期叫 `aos-exec` 跑清單上的 inst」；node 登記、socket／IPC、runner、收尾寬限、state 存讀等第一版不做的，標〔使用者方向 2026-10-01：第一版先不做〕。
- [inst.md](../../spec/base/inst.md)「登記的 id 就是這個目標路徑」與 tick 的正規化：~~改成上面「末段 `/inst.json` 省略」的 id 規則~~ 改成「id 就是清單上 `inst` 的字面值」（設定檔追加裁定）。
- [P-101](../../spec/settled/deferred/protocol/daemon/startup-and-ipc.md#p-101啟動設定與-socket建議預設未拍板) 的啟動設定：補上下面的設定檔長相（`insts`、頂層 `cwd`／`interval_ms`／`stop_on_nonzero`）。

**設定檔追加裁定（使用者 2026-10-01，已寫入 spec（commit 前由我補號））**

使用者原話：「設定檔這塊可以。其中的inst的值，反正後面的路徑是要直接丟給aos-exec的，所以既可以是資料夾也可以是檔案，反正只要符合aos-exec的解析規範就好。inst寫相對路徑時，改成以daemon啟動時所在的cwd為起點，或是設定檔頂層添加一個key："cwd":"./"在insts旁邊。頂層key還可以加上interval_ms, stop_on_nonzero，作為所有insts的默認設定。所謂id也不用特別算了，就直接是inst的值，捨棄我剛剛說的。」細節見 [m3 步驟 1](../../plan/m3-daemon-core.md#步驟-1讀設定檔)。

- **`inst` 原樣交給 aos-exec**：資料夾或檔都行，daemon 不檢查、不解析。
- **相對路徑的起點**：頂層可選 `cwd`；沒寫＝daemon 啟動時的工作目錄；`cwd` 是相對路徑時也以 daemon 啟動時的工作目錄為起點。daemon 開 aos-exec 子程序時把工作目錄設成這個起點、`inst` 原樣當參數。
- **頂層預設**：頂層可選 `interval_ms`、`stop_on_nonzero`，每項自己寫的蓋過頂層；兩邊都沒有 `interval_ms`＝設定錯、回 1，`stop_on_nonzero` 兩邊都沒有＝`false`。
- **id 就是 `inst` 字面值**，撤回上面「轉絕對路徑、末段 `/inst.json` 省略」；同字面值重複默認不會發生。

**m3 待問裁定（使用者 2026-10-01，已寫入 spec（commit 前由我補號））**：所有項都停了 daemon 照樣開著、不退出；每次印的那一行前面加印出那刻的本地時間（ISO 8601 帶時區，例如 `2026-10-01T15:04:05+08:00 id=a exit=0 ms=812`）；aos-exec 子程序的 stderr 由設定檔頂層可選 `exec_err_path` 決定往哪寫（`<inst>` 換成 inst 字面值、指檔時換成所在資料夾，接在檔尾、純文字；沒寫＝daemon 自己的 stderr；共用出口每次先加一行標頭、收齊再寫、不交錯）。細節見 [m3 待問 3～5](../../plan/m3-daemon-core.md#待問)。

**m3 實作後追加裁定（使用者 2026-10-01，已寫入 spec（commit 前由我補號））**

使用者原話：「關於印出來的樣子，其實不用是id，應該是inst=j/r.json這樣。id這個概念其實可以不存在於daemon核心了。」「前面1,2,3都按照建議。」「daemon config json的頂層可以加上一個key: modules。然後整份daemon config都可以用aos dirictive去解析，所以這樣就不會太過膨大。」「控制模組這塊的細節我還要再想想」；追問後：「$ref 照建議，從設定檔所在資料夾算，算完之後才讓cwd那個key被應用。」細節見 [m3 步驟 1](../../plan/m3-daemon-core.md#步驟-1讀設定檔)。

- **daemon 核心沒有 id**：撤回上面「以路徑當 id」「id 就是 `inst` 字面值」；一項就是它的 `inst` 字面值（加在 `insts` 的位置）。stdout 印 `<時間> inst=<inst 字面值> exit=… ms=…`、`<時間> inst=… stopped`；stderr 標頭照舊 `index=… inst=…`。
- **實作回報三點照建議**：stderr 標頭一律加（含 `<inst>` 個別檔）；inst 沒有資料夾部分時 `<inst>` 換成 `.`；daemon 退出後 aos-exec 寫 stderr 吃 SIGPIPE 被殺，照默認一切正常不處理。
- **整份設定檔先經 aos 指示詞展開再讀**（跟 inst 同一套）：`$ref` 相對檔名以設定檔所在資料夾為準；展開完才套頂層 `cwd`（可以是引進來的值；相對的照舊以 daemon 啟動時的工作目錄為準），`inst` 值再以起點為準。
- **頂層 `modules`**：可選、是物件；之後一個模組一個鍵（例如 `"modules": {"control": {...}}`）。核心只認得、不解讀內容；目前沒有任何模組。
- ~~**控制模組細節使用者還在想**：m3n 暫停、待重寫。~~（同日裁定，見下一小節）

**待改的 spec 處**（追加）：P-101 的設定檔長相補 `modules` 與「整份先展開指示詞、`$ref` 以設定檔資料夾為準、展開完才套 `cwd`」；[inst.md](../../spec/base/inst.md)「登記的 id」改成「daemon 核心沒有 id」。

**`insts` 改成物件＋控制模組裁定（使用者 2026-10-01，已寫入 spec（commit 前由我補號））**

使用者原話：「daemon config中，其實可以是{"insts":{"jobs/report.json":{...},"haha.json":{...}}}。然後控制模組這塊，wake的功能改一下，改成可以調設定，比如正在跑的話是否就不跑了(但仍然叫幾次都只補一次)，或是這次跑完，原本後續週期性的那次就不跑了，或是弄成單獨指令也可以。aos-ctl status應該要只能看一個項的狀態，也就是自己所在的這項。1.夠了。2.可以。3.隨便放，就一個。4.算。5.訊息模組不算在此。」追補：「應該說wake/pause/resume/status都是指向某一項inst任務」。細節見 [m3 步驟 1](../../plan/m3-daemon-core.md#步驟-1讀設定檔)、[m3n](../../plan/m3n-control-module.md)。

- **`insts` 是物件**：鍵＝inst 字面值，值＝該項設定物件（`interval_ms`、`stop_on_nonzero`；`{}`＝全用頂層預設）。撤掉陣列寫法與項內 `inst` 鍵，不相容。stderr 標頭的 `index` 照鍵的順序從 0 數。（已改程式）
- **控制模組**（m3n，~~只寫了 plan~~ 2026-10-01 已做）：設定放 `"modules": {"control": {"socket": "<路徑>"}}`，有寫就是開、沒寫就是沒掛（不要 `enable_control`）；一個 daemon 一個 socket，路徑隨設定；能連 socket 就能做所有事，不另設權限。
- **指令只收四個**：`wake`、`pause`、`resume`、`status`（不收 reload、shutdown）；**每個都指向單一一項**（以 inst 字面值指名），沒有「對全部」的形式；叫醒算控制模組的一部分；訊息模組（aos-mq）不走這條 socket。
- **wake 可帶選項**：正在跑時要不要補一次（叫幾次都只補一次照舊）、跑完後原本週期要不要照舊；細節見 m3n。使用者定名：「正在跑就不補」＝`"skip_while_running": true`（預設 `false`＝跑完補一次）；「不影響原本排程」＝`"keep_schedule": true`（預設 `false`＝叫醒跑完後週期從這次結束重新算，原本那次不另外跑；`true`＝原本那次照常跑）。兩個都留在 wake 上，不拆單獨指令。
- **`aos-ctl status` 只看一項**：不帶參數就看自己所在那項（`AOS_DAEMON_INST`）。環境變數 `AOS_DAEMON_SOCKET`、`AOS_DAEMON_INST`（取代先前草稿的 `AOS_DAEMON_ID`）。

**待改的 spec 處**（追加）：P-101 的設定檔長相改成 `insts` 物件；B-607 叫醒／暫停照 m3n；[P-117 通道變數](../../spec/settled/deferred/protocol/daemon/channel.md) 的 `AOS_DAEMON_SOCKET` 留、加 `AOS_DAEMON_INST`、憑證不做。

**m3n 待問 1 先照建議做（2026-10-01，使用者要直接開工，使用者可改；已寫入 spec（commit 前由我補號））**

使用者要控制模組直接開工，m3n 唯一的待問（暫停中、已停時叫醒怎麼辦、resume 要不要順便跑）先照 plan 建議寫進程式，標「照建議先做，使用者可改」（[m3n 待問](../../plan/m3n-control-module.md#待問)）：

- **暫停中 wake**：跑一次，跑完照樣暫停（暫停只停週期，不擋人手叫）。
- **被 `stop_on_nonzero` 停掉的項 wake**：回 `{"ok":false,"error":"stopped"}`、不跑；要救用 resume。
- **resume**：清掉暫停與已停，一律馬上跑一次（等於一次不帶選項的 wake）。

**待改的 spec 處**（追加）：[B-607 叫醒暫停](../../spec/settled/deferred/daemon/registration.md#b-607叫醒暫停故障停格與格次序號) 補上這三條。

## node 模組方向（2026-10-01，記錄用，未排程）

〔使用者方向 2026-10-01〕記錄用，還沒排進任何一段。

- ~~**叫醒、暫停、狀態一覽放進 daemon 核心，但不在第一版**；做的時候用檔觸發、不開 socket。~~ 已被控制模組（[B-641](../../spec/settled/daemon/control.md)，socket 版）取代〔使用者 2026-10-01；astra 報告「要使用者裁定」第 2 點〕。
- **node 由 daemon 掃根資料夾自動找**：有 `tasks.json` 的資料夾就是 node，不用一個個寫進清單。
- **上下層只照資料夾包含關係算**（資料夾在誰裡面，誰就是上層）。
- **node 模組第一版只做兩件事**：「找 node」與「上下層＋叫醒往上傳」。訊息、cgroup、常駐行程在它之上另成模組。

## 2026-10-01 統一更新 spec

上面各節（含「待改的 spec 處」各條）與當天追加的裁定（`AOS_NODE_DIR` 改名 `AOS_TICK_CWD`、拿掉 `AOS_TICK_RECORD`、`aos-tick` 目標改位置參數、stderr `no_target`）已一起寫進 spec（commit 前由我補號）。原則：spec 跟現行程式與裁定一致；今天加的〔POC 先不做〕〔作廢〕註記收掉；先不做的規定不刪，搬到[暫緩區](../../spec/settled/deferred/README.md)，條號保留、不重用，每條標「暫緩」或「已被 X 取代」。

改了哪些篇：

- **新開**：[通用慣例](../../spec/settled/conventions.md)（C-08 結束碼慣例、C-09 `AOS_DIRNAME`、C-10 環境變數總表）；[daemon/core](../../spec/settled/daemon/core.md)（B-640 最核心 daemon）、[daemon/control](../../spec/settled/daemon/control.md)（B-641 控制模組與 `aos-ctl`）；[protocol/daemon/core](../../spec/settled/protocol/daemon/core.md)（P-120）、[protocol/daemon/control](../../spec/settled/protocol/daemon/control.md)（P-121）；[名詞](../../spec/settled/terms.md) T-11；[暫緩區](../../spec/settled/deferred/README.md) 入口與 `deferred/tick.md`、`deferred/terms.md`、`deferred/protocol/daemon/README.md`。
- **改寫**：整理區 [README](../../spec/settled/README.md)、[tick](../../spec/settled/tick.md)（B-626、B-602、B-620、B-633 照新規定，其餘各條修打架的句子）、[tick 協議](../../spec/settled/protocol/tick.md)（P-200～213）、名詞 T-07、T-10、[daemon 入口](../../spec/settled/daemon/README.md)、daemon 協議 P-100。
- **搬到暫緩區**：B-628、T-09；B-602、B-620、B-633 的部分；整套舊 daemon（B-504、B-601、B-603～615）與舊 daemon 協議（P-101～119）；B-303（helper、`aos-as`）。被新設計取代的：B-615（被 `modules` 取代）、P-101（被 P-120、P-121 取代），B-601、B-607、P-103、P-105、P-106、P-117 部分取代。
- **區外**：[inst](../../spec/base/inst.md)（`AOS_DIRNAME`、用法錯 1、aos-exec 不認得 `user`、daemon 核心沒有 id）、[驗收入口](../../spec/conformance.md)（V-01 正本表與條號表、V-03 標暫緩並加「2026-10-01 新增場景」）、[contracts](../../spec/contracts.md) C-01 一處連結、[名詞與責任](../../spec/terms.md)、[ops](../../spec/protocol/ops.md) 一處；搬家連帶的相對連結全 repo 重算。
- **schema／範例**：`node-tasks`（`id`、`kind` 不必填、拿掉 `methods`）、`node-tick-record`（`exit` 只收 0）；新增 `daemon-core-config`、`daemon-ctl` 與範例；`validate.py` 跟著改。
- 改寫時發現、要使用者裁定的點列在[整理區 README「疑點」](../../spec/settled/README.md#2026-10-01-統一更新要使用者裁定的)。

<a id="2026-10-01daemon-輸出socket-欄位inst-user"></a>

## 2026-10-01：daemon 輸出、socket 欄位、inst `user`（已寫入 spec（commit 前由我補號））

〔使用者方向 2026-10-01〕使用者原話：「aos-exec的輸出，也可以放在aos daemon config的頂層，類似exec error path那樣去設定。不設定的話默認/dev/null。然後exec error path沒設定的話也幫我改成默認/dev/null。socket收到看不懂的欄位就不理他。inst頂層的user欄位不留。」

- **`exec_out_path`**：daemon 設定檔頂層新鍵，接 `aos-exec` 子程序的 stdout；規則全照 `exec_err_path`（`<inst>` 替換、inst 是檔換成所在資料夾、沒有資料夾部分換 `.`、相對以起點為準、接檔尾、父資料夾自動建、每次收齊再一次寫出、有內容才寫、一律加標頭）。標頭在時間後面多一欄 `stdout`／`stderr`：`== <時間> stdout index=<n> inst=<inst> ==`。同一次兩條都有就先 stdout 段再 stderr 段。
- **兩個鍵沒寫都丟到 `/dev/null`**，不再接到 daemon 自己的 stdout／stderr；要接回就寫 `"/dev/stdout"`、`"/dev/stderr"`。daemon 自己印的那一行（`inst=… exit=… ms=…`、`stopped`、`paused`、`resumed`）照舊在 daemon 的 stdout。整理區疑點 8（`aos-exec` 的 stdout 可能跟 daemon 的行交錯）因此結案。
- **控制 socket 看不懂的欄位照收不理**（程式本來就是這樣）。C-07 放寬表單列一行「現行控制 socket：忽略」，嚴格拒絕只剩舊設計的 daemon IPC（暫緩區）。疑點 6 結案。
- **inst 頂層 `user` 不留**：inst.md 拿掉 `user` 的定義與「先決定身分，切完才解析」整節（直接刪、不搬暫緩，記在[暫緩區撤回表](../../spec/settled/deferred/tick.md#已撤回被取代)）；任務是 inst 超集，任務表的 `user` 一併拿掉；schema、範例、P-201／P-202 等照改。寫了 `user` 就是不認得的鍵、忽略。疑點 9 結案。程式 `aos_inst` 本來就忽略，不用改。

改到的地方：[B-640](../../spec/settled/daemon/core.md)、[P-120](../../spec/settled/protocol/daemon/core.md)、[P-121](../../spec/settled/protocol/daemon/control.md)、[C-07](../../spec/contracts.md)、[inst](../../spec/base/inst.md) 等；程式 `lib/aos_daemon.py`、測試 `test_daemon.py`／`test_ctl.py`；[plan m3](../../plan/m3-daemon-core.md)、[src/py README](../../src/py/README.md#aos-daemon第三段最核心-daemon)。

## 2026-10-01 第二批：astra 審查修正、tick 層改名、拆篇、tasks.json 頂層預設（已寫入 spec（commit 前由我補號））

〔使用者方向 2026-10-01〕處理 [astra 審查](../reviews/2026-10-01/astra-spec-sync-report.md)，加上同日幾條新裁定。使用者原話：「不用特別弄清單，就全部」（`AOS_DIRNAME` 空字串時 git 管什麼）；「好，就這個。tick執行時後他自己有自己的cwd，這個頂層key cwd不會影響tick自己的cwd，但是其相對路徑由tick的cwd開始算。」「展開指示詞的時候不整份解好，而是只解到tasks。」「daemon config file也是，最頂層cwd不影響daemon自身，相對路徑也是基於daemon的cwd。但是指示詞這塊，daemon config file是全部產開」「tasks.json頂層也應該有modules。」

**這節是正本，已寫入 spec（commit 前由我補號）。**

- **A. astra 必修 1～9 全修**：擋板改成「daemon 照常叫，由 tick 自己擋」，舊 daemon 才有的通道、格後清理、node 框標明只適用暫緩區、移出現行核心依賴表；恢復前驗證的舊授權流程標暫緩；新 daemon 協議入口列明不適用的舊共用條文；wake 照最後一次「沒被 skip 丟掉」的；控制請求 schema 不多禁欄位；暫緩區訊息授權統一引用 B-614；`AOS_TICK_TOKEN` 標「現行控制不使用；舊通道憑證暫緩，未來另定」；`stopped` 行可能被別項穿插；`mq-get` 排序、H-036、T-09 連結修正。
- **B. 設計問題**：設計 3 改用 schema 的條件規則表達「頂層沒給 `interval_ms` 時每項必填」，範例腳本不再重複判定；設計 1（`aos-cg` 收尾殺到自己）記在暫緩區已知問題，不改；設計 2 因 D 結案。
- **C. tick 層的 node 改名**：中文「工作資料夾」，英文 `tick dir`。`settled/protocol/node.md`→`settled/protocol/tick.md`（tick 協議）；schema `node-inst`→`inst`、`node-tasks`→`tick-tasks`、`node-tick-record`→`tick-record`；範例 `examples/node/`→`examples/tick/`；P-200 與系統級任務各條的 node 改工作資料夾。暫緩區的「上層 node／下層 node」與 kernel、agent 各篇的 node 不動。
- **D. 撤回「目標給檔就當任務表」**：`aos-tick [<目標>]` 的目標只能是資料夾（沒給＝`./`），任務表只有 `<目標>/<AOS_DIRNAME>/tasks.json`；給檔＝用法錯、回 1。記進暫緩區撤回表。表只有一個位置，所以 astra 設計 2 不成立。
- **E. `AOS_DIRNAME` 空字串時 git 管整個工作資料夾**：不列清單，使用者自己的檔也會被提交、還原（B-630、C-09）。
- **F. 拆篇**：`settled/tick.md` 只留核心（B-626、B-602、B-620、B-633、B-627）；其餘搬到 `settled/tick/`：template（B-629）、needs（B-621）、cg（B-634、B-631）、mq（B-623、B-624）、git（B-630、B-622、B-632）、recovery（B-625），每篇開頭標狀態。條號不變。
- **G. tasks.json 頂層預設**：頂層可放 inst 的七個欄位（`argv`、`cwd`、`envs`、`stdin`、`stdout`、`stderr`、`exit`）當每一項的預設，淺層合併、項自己寫了就整個蓋過；`_metainfo`、`id`、`kind` 不是預設。頂層 `cwd` 不改 tick 自己的 cwd，相對路徑從工作資料夾算。讀表時只把頂層七個預設欄位與 `modules`、`tasks`、每一項解一層（頂層其他鍵不解），值的內部跑到那一項、合併完才照 inst 規則展開。極簡檢查多一點：合併後要有 `argv`。
- **G 追加：tasks.json 頂層 `modules`**：可選，比照 daemon 設定檔一個模組一個鍵；目前 tick 沒有模組，核心照收不理；不是 inst 欄位、不當預設；讀表時只解一層，內部留給模組（tick 核心不讀它，整份展開只會讓壞的模組設定害整格 `bad_table`）。〔第三批改成讀表時整個展開，見篇末〕
- **跟 daemon 設定檔的對照**：兩邊頂層 `cwd` 都不影響程式自己；相對路徑起點一個是 daemon 啟動時的 cwd、一個是工作資料夾；指示詞 daemon 整份先展開、tasks.json 只到 `tasks` 這層。對照表放 C-11。
- **H. flaky 測試**：`test_ctl.py` 的 `test_keep_schedule` 約十次錯一次，改成等第一次真的跑完再叫醒、判準放寬到 1.5 秒。只動測試。
- **astra「要使用者裁定」**：第 1 點由 E 定；第 2 點見上面「node 模組方向」，檔觸發那句已被控制模組取代。

改到的地方：[整理區 README](../../spec/settled/README.md)（檔案清單、閱讀順序、對外依賴分出「只適用舊 daemon」、疑點）、[名詞](../../spec/settled/terms.md)、[通用慣例](../../spec/settled/conventions.md)（C-09、C-10，新開 C-11）、[tick 核心](../../spec/settled/tick.md)與 [tick/ 子篇](../../spec/settled/tick/README.md)、[tick 協議](../../spec/settled/protocol/tick.md)、[daemon](../../spec/settled/daemon/README.md) 與 [daemon 協議](../../spec/settled/protocol/daemon/README.md)、[暫緩區](../../spec/settled/deferred/README.md)（撤回表、已知設計問題、舊 daemon 各篇）、[inst](../../spec/base/inst.md)、[contracts](../../spec/contracts.md) C-01、[驗收入口](../../spec/conformance.md)（條號表、V-03 場景）；schema 與範例、`validate.py`；程式 `lib/aos_tick.py`、`lib/aos_tick_table.py` 與測試。

<a id="2026-10-01-第三批tasksjson-的-metainfo-與-modules"></a>

## 2026-10-01 第三批：tasks.json 的 `_metainfo` 與 `modules`（已寫入 spec（commit 前由我補號））

〔使用者裁定 2026-10-01〕對[整理區 README 疑點](../../spec/settled/README.md#2026-10-01-第二批astra-審查與使用者裁定落實)「這輪落筆時發現」各條的裁定（`aos-config-add` 旗標那條還沒定）。

- **頂層 `_metainfo` 不是必填**：tick 本來就不查，schema 的 `required` 拿掉、文件改成可省（疑點 3）。
- **每項的 `_metainfo` 照 inst（aos-exec）的規則**：可省，沒寫＝posix 第 1 版；寫了就照 inst 規則驗，跑到那一項、合併頂層預設後交給 `aos_inst.load_obj` 時才驗，驗不過跟其他「跑到某項展開失敗」一樣（自然丟錯、回 1）。程式本來就是這樣，只補 spec、schema、docstring 與測試。
- **頂層 `modules` 讀表時整個展開指示詞**，跟 daemon 設定檔一致，不再只解一層（疑點 4 推翻原暫定）。`$ref:""`／`#…` 指整份 tasks.json、相對檔名以工作資料夾為起點；展開失敗＝`bad_table`、回 1。核心照收不理、不當預設。
- **照現寫法，使用者說 OK**：頂層陌生鍵讀表時不解（疑點 5）；`AOS_DIRNAME=""` 時跟固定排除同名的使用者檔風險自負（疑點 2）；整項 `$ref` 或從別檔引進的預設值，合併後的 `$ref:""`／`#…` 指合併後的這一項（疑點 6）。

改到的地方：[B-620](../../spec/settled/tick.md)、[P-202](../../spec/settled/protocol/tick.md)、[C-11](../../spec/settled/conventions.md)、[整理區 README 疑點](../../spec/settled/README.md)、`tick-tasks.schema.json` 與新範例 `tasks.no-metainfo.valid.json`；程式 `lib/aos_tick_table.py`（`modules` 整個展開）、測試 `test_tick.py`、[src/py README](../../src/py/README.md)。
