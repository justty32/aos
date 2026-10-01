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

<a id="2026-10-01-第四批aos-config-add-搬暫緩區擋板檔與停格檔照現狀"></a>

## 2026-10-01 第四批：`aos-config-add` 搬暫緩區、擋板檔與停格檔照現狀（已寫入 spec（commit 前由我補號））

〔使用者裁定 2026-10-01〕對[整理區 README 疑點](../../spec/settled/README.md#2026-10-01-第二批astra-審查與使用者裁定落實)「這輪落筆時發現」第 1 條（`aos-config-add` 的旗標）的裁定，加上擋板檔與停格檔的處理。使用者原話：「tick-blocked, tick/stop就先這樣。」

- **`aos-config-add` 搬暫緩區**：它是 2026-09-29 規劃、從沒寫過程式的「在 tick 外把設定檔裝進 `config/`」指令，整個先不做，旗標名等加回來時再定。B-625「改設定」表的普通設定那列與相關驗收搬到[暫緩區 tick](../../spec/settled/deferred/tick.md#暫緩b-625-加入普通設定aos-config-add)，格式 P-207 整條搬到[暫緩區 tick 協議](../../spec/settled/deferred/protocol/tick.md)；原處留一句指過去。現在要改 `config/` 就自己改（tick 外的寫入者算外部世界）。條號保留、不重用。
- **擋板檔（`tick-blocked`）與停格檔（`tick/stop`）先照現狀不動**：原本寫的「之後會詳細設計」保留，旁邊補一句「2026-10-01 使用者：先照現狀」。

改到的地方：[暫緩區](../../spec/settled/deferred/README.md)（檔案表、總表、區外暫緩的段落）、[暫緩區 tick](../../spec/settled/deferred/tick.md)、新檔[暫緩區 tick 協議](../../spec/settled/deferred/protocol/tick.md)；[tick/recovery.md](../../spec/settled/tick/recovery.md)、[tick/ 入口](../../spec/settled/tick/README.md)、[tick 協議](../../spec/settled/protocol/tick.md)（P-207 原處、P-213 一句）、[tick 核心](../../spec/settled/tick.md)（B-620 一句）、[整理區 README](../../spec/settled/README.md)（疑點 1 標已裁定）；區外就地標「暫緩（2026-10-01）」：[H-004 第 16 列](../../spec/cli/commands.md)、[A-102](../../spec/agent/configuration.md)、[C-07](../../spec/contracts.md)、[驗收入口](../../spec/conformance.md) V-03 一句、[協議條號表](../../spec/protocol/README.md) P-207；[plan README](../../plan/README.md) 第二段、[m1-tick-core](../../plan/m1-tick-core.md) 一句。

<a id="2026-10-01-第五批aos-publish-搬暫緩區aos-needs-改寫成-aos-tick-check-task"></a>

## 2026-10-01 第五批：`aos-publish` 搬暫緩區、`aos-needs` 改寫成 `aos-tick-check-task`（已寫入 spec（commit 前由我補號））

〔使用者裁定 2026-10-01〕針對[第二段草稿](../../plan/m2-system-tasks.md)（系統級任務）的回覆。git 相關的待問（1～8）使用者還在想，`aos-clean`、恢復前驗證、範本、範例檔（9～12）也還沒裁定，都留在草稿的待問；只有下面三條算裁定。

1. **`aos-publish`（發摘要）搬暫緩區，`aos-summarize` 也不做。** 使用者原話：「aos-publish我覺得要改名，我預期它的作用，就是把這一格的一些狀況總結成json檔案寫好」；討論後「那看來aos-summarize其實是暫時不需要了，拿掉。」B-624 的「發布摘要」一節搬到[暫緩區 tick](../../spec/settled/deferred/tick.md#暫緩b-624-發布摘要aos-publish)，P-206 的 `aos-publish` 那列搬到[暫緩區 tick 協議](../../spec/settled/deferred/protocol/tick.md#暫緩p-206-aos-publish-那列發摘要)，原處留一句指過去；P-307 的發布檔就地標暫緩。兩版範本拿掉 `summary`。之後若要，方向是「把這一格的狀況總結成 JSON」，名字不用 publish（publish 會跟傳訊混）。條號保留、不重用。
2. **`aos-needs` 改寫成 `aos-tick-check-task`（B-621、P-204，條號不變）。** 使用者原話：「aos-needs原來是一個程式...，其實可以簡單一些，也就是它會檢查指定的東西是否跑好，沒跑好，就去寫tick stop檔案」「那就aos-tick-check-task」。新規定：
   - 用法 `aos-tick-check-task [<任務 id…>]`，自己是任務表上的一項，不包別的指令。
   - 讀本格紀錄 `$AOS_TICK_CWD/<狀態資料夾>/tick/current.json`。指定的 id 都在本格紀錄裡且結束碼 0 → 什麼都不做；有任一個不是 0 或還沒跑 → 建停格檔 `tick/stop`（照現行停格檔規定），本格後面的項就不跑。
   - 不寫 id＝檢查本格前面已跑過的每一項。
   - 不管有沒有停格都回 0（停格是預料之中）；自己的錯（沒有 `AOS_TICK_CWD`、讀不到紀錄等）回 1。照 POC 總原則默認正常。
   - 停格擋掉整格剩下的全部項，接受。
   - 檔名 `tick/needs.md` 改成 [`tick/check-task.md`](../../spec/settled/tick/check-task.md)。舊的包裝寫法（`-- 原指令`、125）記在[暫緩區 tick 篇末「已撤回／被取代」](../../spec/settled/deferred/tick.md#已撤回被取代)。
3. **停格檔的未來方向（只記錄，不做）。** 使用者原話：「我覺得tick-stop這個檔案會變成特定json格式，存放一些資訊，然後可以用aos-tick-check-task-continue來去檢查其中的一些資訊，滿足後修改stop中的資訊。所以aos-tick仍會執行所有任務，但會變成執行前檢查stop，看看是否滿足特定條件，滿足的話就可以執行該任務。」記在 [B-620「停格檔與擋板檔」](../../spec/settled/tick.md)與 P-213 旁；現在停格檔規定不變。

改到的地方：[tick/check-task.md](../../spec/settled/tick/check-task.md)（原 needs.md，B-621 改寫）、[tick 協議](../../spec/settled/protocol/tick.md)（P-204 改寫、P-206 拿掉 `aos-publish` 列、P-200／P-202／P-208／P-213 各一句）、[tick/mq.md](../../spec/settled/tick/mq.md)（發布摘要一節搬走）、[tick/template.md](../../spec/settled/tick/template.md)（拿掉 `summary`、前置改用 `aos-tick-check-task`）、[tick/git.md](../../spec/settled/tick/git.md)、[tick/ 入口](../../spec/settled/tick/README.md)、[tick 核心](../../spec/settled/tick.md)（含停格檔未來方向）、[名詞](../../spec/settled/terms.md)、[慣例](../../spec/settled/conventions.md)、[整理區 README](../../spec/settled/README.md)、[暫緩區](../../spec/settled/deferred/README.md)與其 tick、tick 協議兩篇；範例 `tasks.template.valid.json`、`tasks.template-git.valid.json`；區外就地標註：[P-307](../../spec/protocol/messages.md)、[kernel 任務](../../spec/protocol/kernel-tasks.md)、[agent 任務](../../spec/protocol/agent-tasks.md)、[驗收入口](../../spec/conformance.md)、[協議入口](../../spec/protocol/README.md)、[spec 入口](../../spec/README.md)、[名詞](../../spec/terms.md)、[base 入口](../../spec/base/README.md)、[proto6 README](../../README.md)；[plan README](../../plan/README.md)、[m1-tick-core](../../plan/m1-tick-core.md)、[m2-system-tasks](../../plan/m2-system-tasks.md)。

<a id="2026-10-01-第六批tick-的-hooks外掛掛點"></a>

## 2026-10-01 第六批：tick 的 hooks（外掛掛點）（已寫入 spec（commit 前由我補號））

〔使用者裁定 2026-10-01〕使用者原話：「那就做外掛掛點，這個hooks就是模組」「after_cell？我以為是after_all，我們有cell嗎？ 2.可以一串。 3.吃，hooks中的掛點所提供的，比如"after_cell":[{},{},...]，就比照tasks。4.會記錄。 剩下都建議」。同日改裁定：「所以目前唯一的模組就是hooks...就不讓他當模組了，直接讓他變頂層key」。

- **hooks 是 tasks.json 的頂層鍵**，跟 `tasks` 同層：`{"hooks": {"after_all": [...]}, "tasks": [...]}`。起初定成模組（放 `modules.hooks`），同日改成頂層鍵，**不叫模組**；`modules` 照舊照收不理、讀表時整個展開，寫在 `modules.hooks` 底下的不會跑。沒寫 `hooks` 或沒寫 `after_all`：行為跟原本完全一樣。
- **只開一個掛點 `after_all`**（使用者說的 `after_cell` 就是它）：照表跑完之後跑，含被停格檔停下的那格。`before_all`、`before_task`、`after_task` 先不開；`hooks` 裡不認得的鍵照收不理。
- **一串、比照 `tasks`**：`after_all` 是陣列，每元素一個 inst 物件；`id` 可省（沒寫＝在 `after_all` 的位置轉字串，從 0 起）；吃 tasks.json 頂層預設（淺層合併、項蓋過）；跑法跟任務一模一樣（cwd 規則、`AOS_TICK_CWD`、`AOS_TASK_ID`、`AOS_TASK_INDEX`——ID／INDEX 是 hook 項自己的）。
- **展開時機比照 `tasks`**：讀表時 `hooks` 本身、`after_all`、每一元素各解一層；值的內部跑到時、合併預設後才照 inst 規則展開（這時 `$ref:""`／`#…` 指合併後的這一項）。不用 `modules` 那種整個展開。
- **極簡檢查比照 tasks**：`hooks` 是物件、`after_all` 是陣列、每項是物件、合併後有 `argv`，讀表那一層解得開；不合＝`bad_table`、回 1（開格前）。
- **不看停格檔**：停格了也照跑（這是它存在的理由）；每項的碼照實記、接著跑下一項；不影響 tick 的結束碼（照舊 0）。
- **會記錄**：寫在本格 `current.json` 的 `hooks.after_all`，格式同 `tasks` 每項，跟著換進 `last.json`。
- **不跑的時候**：擋板檔、busy、tick 自己出錯（表壞等）。
- **「剩下都建議」由 AI 隊定的細節**：紀錄在收尾（`ended:true`、`exit:0`）之後才寫 `hooks`，hook 讀 `current.json` 看得到整格結果與前面 hook 的碼；`after_all` 是空陣列時記 `"hooks":{"after_all":[]}`；`hooks` 不是物件也算 `bad_table`；`exec_failed` 那行的 id 寫成 `after_all/<id>`；hook 跑到時展開失敗照任務的規則自然丟錯、回 1（紀錄停在 `ended:true`、hooks 只到前一項）。新條號 B-635，協議擴充 P-202、P-203、P-213，不另開 P 號。

改到的地方：新篇 [tick/hooks.md](../../spec/settled/tick/hooks.md)（B-635）、[tick 核心](../../spec/settled/tick.md)（先講重點、一格怎麼走、任務表、頂層 `modules`、指示詞展開時機、極簡檢查、B-633 欄位表）、[tick/ 入口](../../spec/settled/tick/README.md)、[tick 協議](../../spec/settled/protocol/tick.md)（P-202 頂層 `hooks` 表、P-203 `exec_failed` 與環境變數、P-213 `hooks` 紀錄）、[慣例 C-10](../../spec/settled/conventions.md)、[名詞 T-10](../../spec/settled/terms.md)、[整理區 README](../../spec/settled/README.md)、[驗收入口](../../spec/conformance.md)新條號表；schema `tick-tasks`、`tick-record` 與 5 個新範例；程式 `lib/aos_tick_table.py`（讀 `hooks`、極簡檢查）、`lib/aos_tick_hooks.py`（新，跑 `after_all`）、`lib/aos_tick.py`、`lib/aos_tick_record.py`、測試 `tests/test_tick_hooks.py`（新）；[plan m1h](../../plan/m1h-hooks-module.md)（新）、[plan README](../../plan/README.md)、[src/py README](../../src/py/README.md)。

<a id="2026-10-01-第七批tick-模組的取捨node逾時歷史紀錄"></a>

## 2026-10-01 第七批：tick 模組的取捨（node、逾時、歷史紀錄）

〔使用者裁定 2026-10-01〕起頭：「我們改成來看aos-tick應該有啥模組」。候選有收尾、node、git、關卡、逾時、收屍、歷史紀錄、訊息。使用者原話：「node, 逾時跟我說說。歷史紀錄就不需要了。剩下都可以用hooks實現」「可以，node 跟逾時都照建議。node這塊我之後還會再想想，感覺總有哪裡不對」。

- **原則（建議，使用者接受）**：能寫成任務表一項的就不做模組；只有任務表做不到的（插在每項前後、停格後也得跑、要看 tick 內部狀態）才考慮模組。
- **歷史紀錄**：不做。
- **node**：tick 這邊不做 node 模組。「找 node」（有 `.aos/tasks.json` 的資料夾）若要做，是 daemon 的模組；上下層照路徑算；往上叫醒用 [hooks](../../spec/settled/tick/hooks.md) 的 `after_all` 掛 `aos-ctl wake <上層>`（前提：daemon `insts` 的鍵直接寫資料夾）。上層 git 不要提交下層 node 的 `.aos` 是 git 的事，跟 git 一起想。**使用者還在想，感覺總有哪裡不對**。
- **逾時**：不做模組，直接用系統的 `timeout`（如 `["timeout","300","make"]`，超時回 124，照一般失敗記）；整格逾時包在 daemon 那項 inst 外。要所有項套同一時限時再考慮 `modules.timeout`。
- **其餘候選**（收尾、關卡、收屍等）：用 hooks 實現或之後再說。停格與 git 先不動（使用者：「算了，停格這一塊先不動吧。git也先不動。」）。

<a id="2026-10-01-第八批紀錄只記非-0"></a>

## 2026-10-01 第八批：紀錄只記非 0

〔使用者裁定 2026-10-01〕使用者原話：「記錄這一塊，tasks如果結果是0，那就不用紀錄了。hooks也是。」AI 隊提的做法使用者回「好」。

- **`tasks` 只記結束碼不是 0 的項**，每筆 `{"id":…,"index":…,"exit":…}`（`index`＝它在 `tasks` 陣列的位置，同 `AOS_TASK_INDEX`；被訊號殺的照舊記 `signal` 不記 `exit`）。結束碼 0 的不記。
- **加 `ran`**：本格到目前為止跑完幾項 tasks（含失敗的；被停格檔擋掉的不算）。開格時 0，每跑完一項加 1、整份重寫。
- **`hooks.after_all` 一樣只記不是 0 的**，每筆 `{"id","index","exit"}`（index 是 hook 在 `after_all` 的位置）。hooks 不記 `ran`〔AI 隊定，簡單為主〕：hooks 不看停格檔、一定全跑，開始前先寫的 `after_all: []` 就表示開始跑了；tick 跑到一半被殺時看不出跑到第幾個，照 POC 默認不管。
- **`stopped_after` 照舊**記停下那項的 id；它就是位置 `ran-1` 那一項（成功的話不在 `tasks` 裡）。validate.py 的補充檢查改成：`index` 嚴格遞增、都小於 `ran`；有 `stopped_after` 時 `ran` 至少 1，`tasks` 最後一筆的 `index` 是 `ran-1` 時 id 要對得上。
- **`aos-tick-check-task` 的判斷跟著改**（B-621、P-204；程式還沒寫）：寫了 id＝有出現在本格紀錄的失敗清單才建停格檔，沒出現當成功（不分辨「還沒跑」，照 POC 默認一切正常，使用者把它排在那些項後面）；不寫 id＝失敗清單非空就停格。
- **另一條**：hook 跑到時展開失敗→tick 回 1，但紀錄已是 `ended:true`／`exit:0`，兩邊對不上。使用者 2026-10-01：照 POC 默認一切正常，**先不管**。

改到的地方：程式 `lib/aos_tick_record.py`、`lib/aos_tick.py`、`lib/aos_tick_hooks.py`；測試 `tests/test_tick.py`（新增 `RecordOnlyFailures`）、`tests/test_tick_hooks.py`；[tick 核心](../../spec/settled/tick.md) B-620、B-633；[tick 協議](../../spec/settled/protocol/tick.md) P-204、P-213；[tick/hooks.md](../../spec/settled/tick/hooks.md)；[tick/check-task.md](../../spec/settled/tick/check-task.md)；[tick/git.md](../../spec/settled/tick/git.md)（`kind` 回查與組的成敗判法各一句）；[驗收入口](../../spec/conformance.md)一句；schema `tick-record` 與 `examples/tick/tick-record.*`（14 份改寫、6 份新反例）、`examples/messages/validate.py` 補充檢查；[src/py README](../../src/py/README.md)；[plan m1-tick-core](../../plan/m1-tick-core.md)、[m1h-hooks-module](../../plan/m1h-hooks-module.md) 補註、[m2-system-tasks](../../plan/m2-system-tasks.md)（步驟 1、4 與裁定紀錄）。

<a id="2026-10-01-第九批紀錄拆檔"></a>

## 2026-10-01 第九批：紀錄拆檔

〔使用者裁定 2026-10-01〕使用者原話：「應該說，每跑一次task就要更新一次current.json，實在是...我是覺得啦，current.json這邊，也要引入指示詞，把容易被改動的弄成$ref指向其他檔案，不容易被改動的留在current.json」；AI 隊提的方案使用者確認：「1. 各一個檔。 2.隨你。 3.原位。」（1＝常改的欄位各一個檔；2＝檔名與細節由 AI 隊定；3＝停格檔 `tick/stop`、擋板檔 `tick-blocked`、鎖 `tick.lock` 原位不動。）

- **一格紀錄是一個資料夾**：`<狀態資料夾>/tick/current/`（本格）、`tick/last/`（上一格，同結構），四個檔：
  - `record.json`：不常改的 `version`、`seq`、`started_at_ms`、`ended`、`exit`、`stopped_after`，加上 `"ran":{"$ref":"ran.json"}`、`"tasks":{"$ref":"task-exits.json"}`，有 hooks 時再加 `"hooks":{"$ref":"hook-exits.json"}`。只在開格、收尾各寫一次。
  - `ran.json`：一個數字，每跑完一項重寫。
  - `task-exits.json`：結束碼不是 0 的任務 `[{"id","index","exit"|"signal"}…]`；開格寫 `[]`，有失敗時才重寫。
  - `hook-exits.json`：`{"after_all":[…]}`，結束碼不是 0 的 hook。
- **換紀錄**：在暫存資料夾 `tick/.current.tmp/` 寫好新的三個檔 → 刪 `last/` → `current/` 整個 rename 成 `last/`（沒有 `current/` 就只刪 `last/`，上一格算不知道）→ 暫存資料夾 rename 成 `current/`。`$ref` 是相對路徑，整個資料夾改名後仍指得對。`seq` 從 `current/record.json`、沒有就 `last/record.json` 接著數（照舊算法）。
- **讀的一方展開 `$ref`**：`aos_tick_record.read_record(資料夾)` 回展開後的完整紀錄（用 `aos_directives` 現成函式，只展開頂層各鍵），測試與之後的 `aos-tick-check-task` 都用它。schema `tick-record` 的根描述展開後的完整紀錄，`$defs/RecordFile` 描述 `record.json` 本體。
- **「隨你」由 AI 隊定的細節**：
  - `hook-exits.json` 何時建：任務表有寫 `hooks.after_all` 時，收尾那次先寫好 `{"after_all":[]}`、再寫 `record.json`（`ended:true` 加 `hooks` 的 `$ref`），所以 `record.json` 一樣只寫兩次（原本「開始跑 hooks 前寫 `after_all: []`」併進收尾那次，hook 開跑時讀得到）。沒寫 hooks 的格沒有這個檔、`record.json` 也沒有 `hooks` 鍵——展開後的語意跟拆檔前一樣。
  - 每項之後先寫 `task-exits.json`（有失敗時）再寫 `ran.json`，讀到 `ran:N` 時前 N 項的失敗一定看得到。
  - `record.json` 的鍵順序：`ran`、`tasks`、`hooks` 排在 `ended`、`exit`、`stopped_after` 前面（只為好看）。
  - 每個檔都是同資料夾暫存檔（`.<檔名>.tmp`）→ rename；開格前若有上次留下的 `.current.tmp/` 先刪。
- **舊的 `tick/current.json`、`tick/last.json` 不再使用**，POC 不管舊紀錄遷移；照 POC 總原則默認一切正常。

改到的地方：程式 `lib/aos_tick_record.py`（改寫，加 `read_record()`）、`lib/aos_tick.py`（收尾時告訴紀錄有沒有 hooks）、`lib/aos_tick_hooks.py`（拿掉 `start_hooks`）；測試 `tests/test_tick.py`（任務改用 `read_record()` 印紀錄、比對整個資料夾、新 `RecordFiles` 3 條）、`tests/test_tick_hooks.py`（新 1 條）、`tests/test_daemon.py`（讀 `seq` 的路徑）；[tick 核心](../../spec/settled/tick.md) B-620 環境變數表、結束碼表、B-633；[tick 協議](../../spec/settled/protocol/tick.md) P-200、P-203、P-204、P-211、P-212、P-213；[tick/hooks.md](../../spec/settled/tick/hooks.md)；[tick/check-task.md](../../spec/settled/tick/check-task.md)；[tick/git.md](../../spec/settled/tick/git.md)（固定排除的 `.aos/tick/` 本來就涵蓋整個資料夾，只補一句說明）；[tick/recovery.md](../../spec/settled/tick/recovery.md)；[暫緩區 tick](../../spec/settled/deferred/tick.md)（檔名註）；[慣例 C-10](../../spec/settled/conventions.md)；[名詞](../../spec/settled/terms.md)；[驗收入口](../../spec/conformance.md)；schema `tick-record`（加 `$defs/RecordFile`）、`examples/tick/tick-record-file.*`（2 正 3 反）、`examples/messages/validate.py`；[src/py README](../../src/py/README.md)；[plan m1-tick-core](../../plan/m1-tick-core.md)、[m1h-hooks-module](../../plan/m1h-hooks-module.md) 補註、[m2-system-tasks](../../plan/m2-system-tasks.md)。

<a id="2026-10-01-第十批hook-的環境變數"></a>

## 2026-10-01 第十批：hook 的環境變數

〔使用者裁定 2026-10-01〕使用者原話：「hook這塊，幫我添加AOS_HOOK_TYPE, AOS_HOOK_INDEX, AOS_HOOK_ID，我不確定怎麼命名，但反正就是標明他是屬於hook的哪類，然後AOS_HOOK_INDEX, _ID會替代TASK_ID, INDEX。但對於hook到特定任務的前後的，還是會有AOS_TASK_INDEX, AOS_TASK_ID，只是這時候他就是指向那個被hook的任務。」

- **三個變數**（命名由 AI 隊定）：
  - `AOS_HOOK_POINT`：掛點名，例如 `after_all`。使用者暫名 `AOS_HOOK_TYPE`；值就是掛點名，所以叫 POINT，跟 spec 名詞「掛點」一致（TYPE 容易跟任務表的 `kind` 混）。
  - `AOS_HOOK_INDEX`：這個 hook 在該掛點陣列裡的位置，從 0 起。
  - `AOS_HOOK_ID`：這個 hook 的 id；沒寫＝位置轉字串，不是字串時 `str()`。
- **hook 不再給 `AOS_TASK_ID`／`AOS_TASK_INDEX`**（`after_all` 不屬於任何任務）。`AOS_TICK_CWD` 照給。
- **一般任務照舊只有 `AOS_TASK_ID`／`AOS_TASK_INDEX`**，不給 `AOS_HOOK_*`。
- **繼承漏出**〔AI 隊定〕：原本任務的 `AOS_TASK_*` 是蓋在繼承環境上，外層的值會被蓋掉；但 hook 不放 `AOS_TASK_*`、任務不放 `AOS_HOOK_*`，外層（例如這個 tick 本身是別的 tick 的任務或 hook）帶進來的會漏下去。所以跑每一項前先把這五個（`AOS_TASK_ID`、`AOS_TASK_INDEX`、`AOS_HOOK_POINT`、`AOS_HOOK_INDEX`、`AOS_HOOK_ID`）從繼承的環境拿掉，再放這一項該有的；`envs` 清空、`envs` 最後疊上去的規則不變。
- **之後開掛在某個任務前後的掛點**（`before_task`、`after_task` 這類，目前沒開）：那種 hook 除了 `AOS_HOOK_*`，還會有 `AOS_TASK_ID`、`AOS_TASK_INDEX`，指向被掛的那個任務。只寫進 spec，不實作。
- 順帶解掉 [tick 系統級任務清單](../2026-10-01-tick-system-tasks.md) 記的「hook 的 `AOS_TASK_INDEX` 會跟任務撞號」。

改到的地方：程式 `lib/aos_tick.py`（`task_vars()`、`run_one()` 改收 `run_vars`）、`lib/aos_tick_hooks.py`（`hook_vars()`）、`lib/aos_tick_run.py`（`RUN_VARS`，先拿掉繼承來的）；測試 `tests/test_tick_hooks.py`（hook 拿到 `AOS_HOOK_*`、拿不到 `AOS_TASK_*`，任務拿不到 `AOS_HOOK_*`，外層環境帶進來的都不漏）；[tick 核心](../../spec/settled/tick.md) B-620 環境變數；[tick/hooks.md](../../spec/settled/tick/hooks.md) B-635；[tick 協議](../../spec/settled/protocol/tick.md) P-203；[慣例 C-10](../../spec/settled/conventions.md)；[名詞](../../spec/settled/terms.md)；[驗收入口](../../spec/conformance.md)；[protocol README](../../spec/protocol/README.md)；[src/py README](../../src/py/README.md)；[plan m1h-hooks-module](../../plan/m1h-hooks-module.md) 補註；[tick 系統級任務清單](../2026-10-01-tick-system-tasks.md)。

<a id="2026-10-01-第十一批daemon-模組"></a>

## 2026-10-01 第十一批：daemon 模組

〔使用者裁定 2026-10-01〕對 [plan m3m 五個模組草稿](../../plan/m3m-daemon-modules.md)的裁定：

- **node 不動**。使用者原話：「node這塊不要動，我有預感，node相關概念以後會不存在。剩下這些都值得做成模組。」所以不做 node 模組（[node 模組方向](#node-模組方向2026-10-01記錄用未排程)照留、不排程），模組一律以 daemon 設定檔 `insts` 的一項為單位。
- **重讀設定（`modules.reload`）**：R1～R4 照 plan 建議（SIGHUP 觸發；改週期＝上次結束＋新週期、過了就立刻跑；設定壞了整份不套用、stderr 一行、舊的照跑），**R3 改**：原話「R3這邊，如果最上層這些改了，那就stdout輸出警告。」——頂層 `cwd`、`modules` 改了不套用，在 daemon 的 stdout 印 `reload: need restart: cwd`／`modules`。已做，正本 [B-642](../../spec/settled/daemon/reload.md)、[P-122](../../spec/settled/protocol/daemon/reload.md)。
- **記住狀態（`modules.state`）**：S1～S3 照建議（不記上次結束時間；`stop_on_nonzero` 停掉的也跨重開；每次變動當場寫整份）。設定方式改，原話：「"state":{"$ref":...}會比較好，因為有時候它會頻繁被改動。」——寫成 `"modules": {"state": {"$ref": "aos-state.json"}}`，`$ref` 指的檔（以設定檔所在資料夾為準）就是狀態檔，展開後 `modules.state` 就是目前狀態 `{"insts": {...}}`（只列不正常的項）；檔不在當空的、不算設定錯，第一次要寫時才建。B-640「沒掛控制模組就重開 daemon 救回」跟著改：掛了記住狀態時重開救不回，要刪狀態檔。已做，正本 [B-643](../../spec/settled/daemon/state.md)、[P-123](../../spec/settled/protocol/daemon/state.md)。
- **訊息（`aos-mq`）先不做**（原話：「aos-mq先不做」）。
- **helper／帳號先不做**（原話：「帳號也先不做」）。
- **收屍／cgroup**：C1～C4 使用者還沒裁定，這批不做。

**AI 隊定的細節**（使用者可改，全文見 [plan m3m「做完了沒」](../../plan/m3m-daemon-modules.md#做完了沒)）：重讀時狀態以記憶體為準（不重讀狀態檔、新加的項從頭，套用完照記憶體寫一次檔）；狀態檔內容沒變不寫（沒異常就不建檔）；沒掛 `reload` 時 SIGHUP 照 Python 預設殺掉 daemon；`exec_out_path`／`exec_err_path` 改了照套、不警告；重讀壞掉時任何例外都接。

改到的地方：程式 `lib/aos_daemon.py`、新 `lib/aos_daemon_reload.py`、`lib/aos_daemon_state.py`、`lib/aos_daemon_ctl.py`；測試新 `tests/test_daemon_reload.py`、`tests/test_daemon_state.py`；spec 新 [daemon/reload.md](../../spec/settled/daemon/reload.md)、[daemon/state.md](../../spec/settled/daemon/state.md)、[protocol/daemon/reload.md](../../spec/settled/protocol/daemon/reload.md)、[protocol/daemon/state.md](../../spec/settled/protocol/daemon/state.md)，改 [daemon README](../../spec/settled/daemon/README.md)、[B-640](../../spec/settled/daemon/core.md)、[B-641](../../spec/settled/daemon/control.md)、[P-120](../../spec/settled/protocol/daemon/core.md)、[daemon 協議入口](../../spec/settled/protocol/daemon/README.md)、[慣例](../../spec/settled/conventions.md)、[名詞](../../spec/settled/terms.md)、[整理區入口](../../spec/settled/README.md)、[驗收入口](../../spec/conformance.md)、[protocol README](../../spec/protocol/README.md)、暫緩區 [總表](../../spec/settled/deferred/README.md)（B-603、B-608、P-116 標部分取代）與對應各篇；schema `daemon-core-config`（加 `modules.reload`、`modules.state`）、新 `daemon-module-state`、範例 `examples/daemon/module-state.*`、`core-config.modules.valid.json`、`core-config.state-not-expanded.invalid.json`、`validate.py`；[src/py README](../../src/py/README.md)；[plan m3m](../../plan/m3m-daemon-modules.md)、[plan 入口](../../plan/README.md)。

<a id="2026-10-01-第十二批cgroup-與帳號"></a>

## 2026-10-01 第十二批：cgroup 與帳號

〔使用者裁定 2026-10-01〕對 [plan m3m](../../plan/m3m-daemon-modules.md) 模組二、四、五剩下的待問。原話只留下 C1～C4 那句；其餘幾條當天在公司那台講的，這裡照當天寫進 spec 與 [SESSION-LOG](../../../wf/SESSION-LOG.md) 的內容整理，不是逐字。

- **收屍／cgroup（`modules.cgroup`）**：C1～C4 原話「都先按照建議。」——沒委派好的 cgroup v2 就自然丟錯、回 1，不退回（C1）；上限寫在 `insts` 那一項的 `cgroup` 鍵、cgroup 檔名原樣（C2）；直接 `cgroup.kill`，不先 SIGTERM（C3）；框名＝inst 字面值 sha256 前 16 hex，開框時 stdout 印一次對照（C4）。已做，正本 [B-644](../../spec/settled/daemon/cgroup.md)、[P-124](../../spec/settled/protocol/daemon/cgroup.md)。
- **重讀設定順帶改**：頂層 `exec_out_path`／`exec_err_path` 改了也跟 `cwd`、`modules` 一樣不套用、stdout 警告要重開（第十一批 AI 隊定的細節 5 原本是「照新的算」）。比的是設定裡寫的原字（含 `<inst>`）；新加的項的輸出路徑也照開起來時的設定算。已改 [B-642](../../spec/settled/daemon/reload.md)、[P-122](../../spec/settled/protocol/daemon/reload.md)。
- **訊息（`aos-mq`）要做**，排在 cgroup 之後：M1～M4 照建議（`aos-mq send`／`take`、信放在 daemon 記憶體、急件叫醒收件方、收件方自己 take）。已做（10-01 晚），正本 [B-645](../../spec/settled/daemon/mq.md)、[P-125](../../spec/settled/protocol/daemon/mq.md)。
- **帳號要做**，排在最後：模組鍵叫 `account`（不叫 helper）；**H1 不照建議**——要拆出 root 端、主程式降權。socket 先 chmod 666（H4 照建議），之後會有多個 socket，權限另外設計。還沒做，plan m3m 模組五的草稿要照這條重寫。

**AI 隊定的細節**（使用者可改）——收屍／cgroup：

1. 子程序進框用 `sh -c 'echo $$ > <框>/cgroup.procs && exec "$@"'` 墊一層，不用 `preexec_fn`（daemon 有很多執行緒，fork 後跑 Python 不安全）。pid 不變、碼原樣。
2. `exit=` 的 `ms=` 算到 `aos-exec` 結束，不含清框；有清到東西時 `exit=` 之後另印 `inst=<inst> reaped`，沒殘留不印。
3. 殘留程序還拿著輸出 pipe 時：pipe 另開執行緒讀、清完框才收齊，輸出照樣寫出。
4. 開起來時根上**所有**程序都搬進 `daemon/`（`systemd-run` 墊的殼之類也一起）；自己已經在 `.../daemon` 裡就取上一層當根（同一個 scope 裡重開）。框已經在就先清空再用。
5. 重讀設定：新加的項建框、寫上限，`added` 之後印對照；還在的項上限改了只重寫新設定寫的檔，拿掉的鍵**不還原**（要還原寫 `"max"`）；建框、寫上限出錯算重讀出錯（整份不套用），但出錯前已經寫進去的不還原。
6. 拿掉的項由它自己的執行緒在最後一次跑完、清完之後刪框；那時 inst 已經又被加回來就不刪，新的一項接著用同一個框。
7. Ctrl-C 照核心「直接退出、不殺子程序」，框留著，下次在同一棵子樹開起來時才清。
8. 控制模組、記住狀態不用改：清框期間 `status` 的 `running` 仍是 `true`；框不記進狀態檔。

改到的地方：程式新 `lib/aos_daemon_cgroup.py`，改 `lib/aos_daemon.py`（`Item.cgroup`／`frame`、`Setup.out_tmpl`／`err_tmpl`、`run_once()` 回三個值、`_gone()`、`main()` 建樹）、`lib/aos_daemon_reload.py`（`NEED_RESTART`、`_apply()`）；測試新 `tests/test_daemon_cgroup.py`（15 條，拿不到委派的 scope 時跳過），改 `tests/test_daemon_reload.py`；spec 新 [daemon/cgroup.md](../../spec/settled/daemon/cgroup.md)、[protocol/daemon/cgroup.md](../../spec/settled/protocol/daemon/cgroup.md)，改 [daemon README](../../spec/settled/daemon/README.md)、[B-640](../../spec/settled/daemon/core.md)、[B-642](../../spec/settled/daemon/reload.md)、[P-120](../../spec/settled/protocol/daemon/core.md)、[P-122](../../spec/settled/protocol/daemon/reload.md)、[daemon 協議入口](../../spec/settled/protocol/daemon/README.md)、[慣例](../../spec/settled/conventions.md)、[名詞](../../spec/settled/terms.md)、[整理區入口](../../spec/settled/README.md)、[驗收入口](../../spec/conformance.md)、[protocol README](../../spec/protocol/README.md)、暫緩區 [總表](../../spec/settled/deferred/README.md) 與 [daemon/cgroup.md](../../spec/settled/deferred/daemon/cgroup.md)（B-605 標部分取代）；schema `daemon-core-config`（加 `modules.cgroup`、`$defs/Item` 的 `cgroup`）、範例 `examples/daemon/core-config.cgroup.valid.json`、`core-config.cgroup-number.invalid.json`；[src/py README](../../src/py/README.md#收屍cgroupm3m-模組二)；[plan m3m](../../plan/m3m-daemon-modules.md)、[plan 入口](../../plan/README.md)。

**AI 隊定的細節**（使用者可改）——訊息（10-01 晚在家做）：

1. 訊息 socket 的收連線、1 秒逾時、壞請求只影響那一條，跟控制模組共用同一套程式（`aos_daemon_ctl.serve()` 多收一個處理函式）。不認得的欄位照收不理；`take` 帶了 `msg`、`from`、`urgent` 也忽略。
2. 急件寄給被 `stop_on_nonzero` 停掉的項：信照收、回 `{"ok":true}`、不跑（不回 `stopped` 錯誤：信是送到了）。
3. `aos-mq` 只有 `--` 開頭的算旗標：`-` 是從 stdin 讀 JSON，`-5` 是 JSON 負數（照 `aos-ctl` 的寫法，`aos-mq send b -5` 會被當成不認得的旗標）。`<JSON>` 不是 JSON 算 `usage` 錯。
4. `AOS_DAEMON_INST` 是空字串時 `from` 填 `null`、`take` 回 `no_inst`（同 `aos-ctl`）。
5. 重讀設定：還在的項是同一個物件，信箱照留；換 `modules.mq.socket` 算 `modules` 改了，只警告要重開。
6. 信不設上限；`take` 一次全部取走。daemon 重開信就沒了。

改到的地方（訊息）：程式新 `lib/aos_daemon_mq.py`、`lib/aos_mq.py`、`bin/aos-mq`，改 `lib/aos_daemon.py`、`lib/aos_daemon_ctl.py`、`lib/aos_daemon_reload.py`；測試新 `tests/test_mq.py`（14 條）；spec 新 [daemon/mq.md](../../spec/settled/daemon/mq.md)、[protocol/daemon/mq.md](../../spec/settled/protocol/daemon/mq.md)，改 [daemon README](../../spec/settled/daemon/README.md)、[B-640](../../spec/settled/daemon/core.md)、[B-641](../../spec/settled/daemon/control.md)、[P-120](../../spec/settled/protocol/daemon/core.md)、[P-121](../../spec/settled/protocol/daemon/control.md)、[daemon 協議入口](../../spec/settled/protocol/daemon/README.md)、[慣例 C-10](../../spec/settled/conventions.md)、[名詞](../../spec/settled/terms.md)、[整理區入口](../../spec/settled/README.md)、[驗收入口](../../spec/conformance.md)、[protocol README](../../spec/protocol/README.md)、[tick/mq.md](../../spec/settled/tick/mq.md)（狀態一句）、暫緩區 [總表](../../spec/settled/deferred/README.md)、[daemon/messaging.md](../../spec/settled/deferred/daemon/messaging.md)、[protocol/daemon/channel.md](../../spec/settled/deferred/protocol/daemon/channel.md)（B-614、P-119 標部分取代）；schema 新 `daemon-mq`、改 `daemon-core-config`，範例 `examples/daemon/mq_request.*`、`mq_reply.*`、`core-config.mq*`，`examples/messages/validate.py`；[src/py README](../../src/py/README.md#訊息與-aos-mqm3m-模組四)；[plan m3m](../../plan/m3m-daemon-modules.md)、[plan 入口](../../plan/README.md)。

<a id="2026-10-01-第十三批帳號模組"></a>

## 2026-10-01 第十三批：帳號模組

〔使用者裁定 2026-10-01 晚〕對 [plan m3m 模組五](../../plan/m3m-daemon-modules.md#模組五帳號modulesaccount)重寫後的 A1～A5（拆 root 端、主程式降權那一版）。使用者原話：「關於哪些賬號可以用，daemon設定檔中要有白名單和黑名單，然後名單支援prefix，比如agent-*。剩下都按照建議。用sudo　-u包一層這件事不管，這是不在規劃中的做法，風險自己承擔。」

- **A2 改**：`modules.account` 寫 `allow`（白名單）、`deny`（黑名單），字串陣列；結尾 `*` 當前綴（`agent-*`）。判斷順序、省略時的意思、預設帳號不受名單管等細節是 AI 隊定的，見 plan「帳號名單」：黑名單優先、都沒比到不准、`allow` 省略＝空、root 一律不准、`*` 只能在結尾。
- **A1、A3、A4、A5 照建議**：root 端是另一支小程式 `aos-daemon-root`；預設帳號的項不經 root 端；cgroup 子樹 chown 給預設帳號、root 端只把別的帳號的子程序放進框；root 端死掉就自然丟錯、daemon 回 1。
- **H2（inst 自己包 `sudo -u`）不管**：不在規劃中，aos 不寫進 spec、不保證，風險使用者自己承擔。
- 使用者問：`SUDO_USER` 現在用的話會不會是 lorkhan？——是：從 lorkhan 的 shell 打 `sudo aos-daemon …`（或 `sudo -i` 之後再開）就是 `lorkhan`；`su -`、root 直接登入、root 的 systemd unit／cron 開的沒有這個變數，要在 `modules.account.user` 寫明。
- 使用者問：帳號沒先在 Linux 建好會怎樣？——daemon 不建帳號。AI 隊提了 A6（開起來與重讀時就查、跑的時候才不見的那次 `exit=1`），待裁定。

- **追加**：使用者原話：「名單這塊OK，但如果allow不寫，然後deny裏面又出現預設賬號，那就報錯。」——`allow` 省略、`deny` 比得到預設帳號（含前綴、單獨 `*`，「出現」照比得到算，AI 隊解讀）＝設定錯、回 1。`allow` 有寫時同樣情況怎麼辦，AI 隊提了 A7（建議一樣報錯），待裁定。
- 使用者問：帳號這功能目前用在哪、是不是只出現在 daemon 設定？——現行程式沒有任何地方切帳號（全部用開的人的帳號跑）；inst 與任務的 `user` 已撤回（寫了當陌生鍵）。spec 裡另外還提到帳號的，都是暫緩或舊設計：tick 任務包 `aos-as` 換帳號（B-303，暫緩）、身分額度（B-301）、工作接件記 UID（base/execution.md）。帳號模組做出來後，它是唯一現行的切帳號方式，只出現在 daemon 設定檔（`modules.account` 與每項的 `account`）。

- **`aos-as` 暫緩**：使用者原話：「aos-as弄成暫緩。　目前切賬號這件事，都只在daemon config中做」——P-212 整條搬到 [tick 協議暫緩區](../../spec/settled/deferred/protocol/tick.md)；[tick 核心](../../spec/settled/tick.md)「任務的帳號」、[tick 協議](../../spec/settled/protocol/tick.md) P-202／P-203、[範本](../../spec/settled/tick/template.md)、[名詞](../../spec/settled/terms.md)、[aos-cg](../../spec/settled/tick/cg.md)、[git](../../spec/settled/tick/git.md)、[spec 入口](../../spec/README.md)、[plan 入口](../../plan/README.md)第五段改成「tick 不切帳號，要換帳號在 daemon 設定檔拆成另一項」；整理區 README 待問 1 結案。

- **A6、A7 照建議**：使用者原話：「A67都按你建議」。A6：開起來與重讀時就查每項帳號（查不到開起來回 1、重讀整份不套用），開起來之後才被刪的那一次 `exit=1`、照跑；A7：`allow` 有寫時 `deny` 比得到預設帳號一樣算設定錯。

帳號模組已做（10-01 晚），正本 [B-646](../../spec/settled/daemon/account.md)、[P-126](../../spec/settled/protocol/daemon/account.md)。

**AI 隊定的細節**（使用者可改）——帳號：

1. root 端與主程式之間用 `SOCK_SEQPACKET` 的 socketpair（一個封包一則 JSON，fd 用 `SCM_RIGHTS` 跟著請求走，不用自己切行）；root 端另開一個 session，終端機的 Ctrl-C 打不到它，它只看 socketpair 關了沒（也忽略 SIGINT、SIGHUP）。
2. root 端單執行緒：`select` 等 socket 與 SIGCHLD 的 wakeup pipe，`waitpid(-1, WNOHANG)` 收子程序；子程序在 exec 前出錯就在它的 stderr 寫一行、以 127 結束。
3. root 端也准預設帳號（主程式本來就是它，不多給什麼）；名單、root、查不到在開跑那一刻再核一次。
4. 預設帳號的項（包括 `account.user` 寫成預設帳號的）主程式自己開，不經 root 端（A3）。
5. 主程式降權時 `HOME`、`USER`、`LOGNAME` 也換成預設帳號的（sudo 開時它們常是 root 的），所以預設帳號的項看到的也是自己的。
6. root 端不見了（EOF）主程式**當場**退出（stderr 一行、刪 socket 檔、回 1），不等下一次要找它（A5 的做法再提早一點）。
7. 控制、訊息 socket 只有掛了帳號模組時才 chmod 666；沒掛照原本的權限。
8. 開起來時的帳號錯誤一律印 `aos-daemon: account: <說明>`（不是 `config:`），包括沒用 root 開。
9. 每項的 `account` 寫壞（不是物件、`user` 不是字串）：掛了模組＝設定錯；沒掛＝照不認得的鍵忽略。`user` 不收 UID 數字。
10. 名單只核「名字」：比對用帳號名，root 看 UID 0（所以 UID 0 的別名也擋）。

改到的地方（帳號）：程式新 `lib/aos_daemon_account.py`、`lib/aos_daemon_root.py`、`bin/aos-daemon-root`，改 `lib/aos_daemon.py`、`lib/aos_daemon_reload.py`；測試新 `tests/test_account.py`（21 條）；spec 新 [daemon/account.md](../../spec/settled/daemon/account.md)、[protocol/daemon/account.md](../../spec/settled/protocol/daemon/account.md)，改 [daemon README](../../spec/settled/daemon/README.md)、[B-640](../../spec/settled/daemon/core.md)、[P-120](../../spec/settled/protocol/daemon/core.md)、[daemon 協議入口](../../spec/settled/protocol/daemon/README.md)、[慣例](../../spec/settled/conventions.md)（結束碼表）、[名詞](../../spec/settled/terms.md)、[整理區入口](../../spec/settled/README.md)、[驗收入口](../../spec/conformance.md)、[protocol README](../../spec/protocol/README.md)、暫緩區 [總表](../../spec/settled/deferred/README.md)、[daemon 目錄](../../spec/settled/deferred/daemon/README.md)、[helper.md](../../spec/settled/deferred/helper.md)、[helper-actions.md](../../spec/settled/deferred/daemon/helper-actions.md)、[startup-and-ipc.md](../../spec/settled/deferred/protocol/daemon/startup-and-ipc.md)、[provision-and-runner.md](../../spec/settled/deferred/protocol/daemon/provision-and-runner.md)（B-303、B-609、P-102、P-107、P-108 標部分取代）；schema `daemon-core-config`，範例 `examples/daemon/core-config.account*`；[src/py README](../../src/py/README.md#帳號m3m-模組五)；[plan m3m](../../plan/m3m-daemon-modules.md)、[plan 入口](../../plan/README.md)。

<a id="2026-10-01-第十四批aos-mq-取信"></a>

## 2026-10-01 第十四批：aos-mq 取信

〔使用者裁定 2026-10-01 晚〕使用者原話：「取信改成只能取自己的信箱。然後可以選擇要取來自誰的，不選就全部。」推翻第十二批 M3（取信不限自己）。

使用者先問了四題，答覆要點：

1. 收件 inst 跟寄件人不在同一個 daemon：`aos-mq send` 只連自己 daemon 的訊息 socket、只在這個 daemon 的 `insts` 找收件人，找不到回 1、`unknown_inst:`；跨 daemon 送信先不做。收件人逐字比對，同一個檔寫法不同（`b.json`／`./b.json`）也算不同的項。
2. `<JSON>` 是 JSON 文字本身，不是檔案路徑；給 `-` 從 stdin 讀（要寄檔案內容就 `aos-mq send b - < msg.json`）。
3. 原本 `take [<inst>]` 的 `<inst>` 是「取誰的信箱」，不是篩寄件人——這題引出本批裁定。
4. 多封信：一封一行的 JSON（JSON Lines）`{"from":…,"msg":…}`，先寄的在前；沒信什麼都不印、回 0。

做法：

- `aos-mq take [--from <寄件 inst>]`：不收 `<inst>`，只取 `AOS_DAEMON_INST` 那一項的信箱（沒有就 `no_inst`）；`--from` 只取 `from` 等於它的信，其他照原順序留在信箱；不給就全部取走。
- socket 的 `take` 請求多一個可省的 `from`（字串）。
- **「只能取自己」只在 `aos-mq` 這一側擋**：socket 不驗身分，直接連 socket 送 `{"take":"<別項>"}` 照樣取得到。要不要在 daemon 端驗身分（例如看連線方是不是那一項的子孫程序），待使用者決定。

**AI 隊定的細節**（使用者可改）：`--from` 只收一個；不能篩 `from` 是 `null` 的信（從 shell 手打寄的），要的話不帶 `--from` 全取；人在 shell 沒設 `AOS_DAEMON_INST` 就取不了信（要手動取就自己設這個變數）。

改到的地方：程式 `lib/aos_daemon_mq.py`、`lib/aos_mq.py`；測試 `tests/test_mq.py`（15 條，新 `test_take_own_mailbox_only`、`test_take_from_filter`）；spec [B-645](../../spec/settled/daemon/mq.md)、[P-125](../../spec/settled/protocol/daemon/mq.md)、[驗收入口](../../spec/conformance.md)；schema `daemon-mq`（take 的 `from`）、範例 `mq_request.take-from.valid.json`、`mq_request.take-from-number.invalid.json`；[src/py README](../../src/py/README.md#訊息與-aos-mqm3m-模組四)；[plan m3m](../../plan/m3m-daemon-modules.md) 模組四。

<a id="2026-10-01-第十五批aos-mq-peek-與多個寄件人"></a>

## 2026-10-01 第十五批：aos-mq peek 與多個寄件人

〔使用者裁定 2026-10-01 晚〕對第十四批後攤出的四題。使用者原話：「1.a,2.可以有aos-mq peek，但手打這塊我們不管。 3.--from可以多個，比如--from a c d...。不管shell手打，from是null的，那就是--from後面不接任何東西。 4.跨daemon寄信不管。」

1. **daemon 不核對取信的人**（選 a）：照 POC「能連就能做」，直接連 socket 送 `{"take":"<別項>"}` 照樣取得到；「只能取自己」只在 `aos-mq` 那一側擋。之後設計各 socket 權限時再說。
2. **加 `aos-mq peek [--from …]`**：跟 `take` 一樣只對自己的信箱（`AOS_DAEMON_INST`）、一樣的輸出，但信不取走。socket 加 `{"peek":"<inst>","from":…}`，回應同 `take`。是給任務用的；人在 shell 手打怎麼看信 aos 不管。
3. **`--from` 收多個**：`--from a c d`；`--from` 後面什麼都不接＝取寄件人是 `null` 的信。`take`、`peek` 都適用，篩掉的照原順序留著。
4. **跨 daemon 寄信不管**：從「先不做」改成「不在規劃中」，aos 不管、不保證。

**AI 隊定的細節**（使用者可改）：

1. `--from` 後面接的參數收到下一個 `--` 開頭的參數為止（`-x` 這種一個 `-` 開頭的也算寄件人）；`take`／`peek` 不認得的旗標（例如 `--urgent`）照舊回 `usage`。
2. `--from` 可以重複寫、全部疊起來：`--from --from a`＝null 加 a。
3. socket 上 `take`／`peek` 的 `from` 改成**非空陣列**，元素是寄件 inst 字串或 `null`；不給＝全部；空陣列、字串、數字都是 `bad_request`（第十四批的單一字串寫法不再收）。CLI 不會送出空陣列。
4. 人在 shell 沒有 `AOS_DAEMON_INST` 時 `take`、`peek` 都回 `no_inst`，照「手打這塊我們不管」不另外處理。

改到的地方：程式 `lib/aos_daemon_mq.py`（`peek`、`from` 陣列）、`lib/aos_mq.py`；測試 `tests/test_mq.py`（20 條，新 `test_from_many`、`test_from_nothing_is_null`、`test_from_repeated_adds_up`、`test_peek_does_not_take`、`test_flag_after_from`）；spec [B-645](../../spec/settled/daemon/mq.md)、[P-125](../../spec/settled/protocol/daemon/mq.md)、[驗收入口](../../spec/conformance.md)；schema `daemon-mq`（`peek`、take／peek 的 `from` 陣列）、範例 `mq_request.take-from.valid.json` 改陣列、新 `mq_request.peek-from.valid.json`、`mq_request.take-from-empty.invalid.json`、`mq_request.peek-from-string.invalid.json`；[src/py README](../../src/py/README.md#訊息與-aos-mqm3m-模組四)；[plan m3m](../../plan/m3m-daemon-modules.md) 模組四。

<a id="2026-10-01-第十六批擋板檔只看存不存在"></a>

## 2026-10-01 第十六批：擋板檔只看存不存在

〔使用者裁定 2026-10-01 晚〕使用者原話：「先來做tick-blocked這塊的微調：首先我覺得改一下，改成只看存不存在，然後存在的話就直接結束tick，stderr不印東西，這算是正常機制結束。正常機制結束的話stderr不應該印東西。hook也根本不會啓動。」

- **擋板檔 `<狀態資料夾>/tick-blocked` 只看存不存在**（`os.path.lexists`）：空檔、資料夾、沒讀權、壞 symlink 都算在；核心不打開、不讀原因。內容 aos 不看，要留原因給人看可以寫。
- **在就直接結束**：回 0、**stderr 不印**（拿掉原本的 `blocked:` 那行）、不開格、不寫紀錄、不加 `seq`、hooks 根本不啟動。
- **原則記進慣例 C-08**：正常機制結束，stderr 不印。`busy:`、停格檔的 `stopped:` 現在還印，要不要跟著改沒裁定（AI 隊只記一句「另議」，沒改）。
- 停格檔 `tick/stop` 改名 `tasks-blocked`、內容可指定行為那段還在跟使用者討論，這批沒動。

改到的地方：程式 `lib/aos_tick.py`（`_run_locked()` 改用 `lexists`、`read_reason()` 只剩停格檔用）；測試 `tests/test_tick.py`（`Step2Blocked` 改看 stderr 空、新 `test_blocked_only_existence`：空檔／資料夾／壞 symlink／chmod 000；`AOS_DIRNAME` 兩條）、`tests/test_tick_hooks.py`（`NotRun.test_blocked`）、`tests/test_daemon.py`（`test_blocked` 改成 stderr 沒有 blocked）；spec [tick 核心](../../spec/settled/tick.md) B-620 停格檔與擋板檔表與結束碼表、[tick 協議](../../spec/settled/protocol/tick.md) P-203（拿掉 `blocked` 代碼）、P-213、[hooks](../../spec/settled/tick/hooks.md)、[名詞](../../spec/settled/terms.md)、[慣例 C-08](../../spec/settled/conventions.md)、[驗收入口](../../spec/conformance.md)；[src/py README](../../src/py/README.md)。

