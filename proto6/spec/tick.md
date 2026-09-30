# 通用 tick：核心、標準配備與提交

← [規格入口](README.md)｜[daemon](daemon.md)｜[kernel 樹](scheduling/README.md)｜[agent 任務](agent/README.md)

依據：[09-29 新架構](../notes/2026-09-29-kernel-tree.md)、[使用者裁定](../notes/2026-09-29-verdicts.md)第三～十二批、[第十八批](../notes/verdicts/09-special-computing-os.md)、[第十九批](../notes/verdicts/10-tick-minimal-core.md)。下文「任務表」指 node 內的任務註冊表；與 daemon 登記表的區別見[名詞](terms.md)。

〔使用者方向 2026-09-30，第十九批〕**tick 是一個定期被執行的程式**（`aos-tick`），怎麼被執行不管：daemon、cron、人手都行（B-627）。tick 執行時的目前目錄（cwd）就是它的**管轄區**。〔第十八批〕tick 不跟 once、LLM 嘗試、agent 一輪這些計算單位共用外殼（[T-07](terms.md)）。

〔使用者方向 2026-09-30，第十九批〕**本篇的保證以標準配備全掛為前提**（B-629、B-630）；沒全掛時出現的錯誤不在保證範圍內，不逐條寫退化。cgroup 或 git 走備援（B-631、B-632）仍算全掛，保證照那兩條寫的較弱版本。只有核心三件事（B-602、B-620 的照表跑、B-628）不依賴標準配備。

## B-626：三層的界線：核心、標準配備、其他掛載

〔使用者方向 2026-09-30，第十九批；推翻第十八批 Q22「tick 與系統性任務是基底」〕tick 分三層：

1. **核心**：本質上是加了一些功能的 aos-exec（[inst](base/inst.md)），只做三件事：同資料夾互斥鎖（B-602）、照任務表依序跑（B-620）、上下層判定（B-628）。核心只要 Python 3.9 與 flock，不靠 daemon、git、cgroup 或 helper。
2. **標準配備**：aos 出廠就附、預設全掛、不能拆的一包（B-629），例如 git 提交、needs、收件、投件、切換使用者、cgroup 框、once。
3. **其他掛載**：kernel、agent、clock、自訂任務等，都是任務表上的普通項目。

- **同一支程式**〔疑點裁定 1〕：標準配備跟核心是同一支 `aos-tick`，只在規格上分層；不另做掛勾或包裝程式，也沒有關掉其中一塊的旗標或設定。
- **一格的流程**：定位管轄區 → 取鎖（B-602）→ 全掛檢查（B-630）→ 讀任務表、驗形狀（B-620）→ 照陣列順序一項一項跑 → 放鎖、回結束碼。標準配備在這條流程上加自己的工作：格首回到基線、替沒人宣告的 method 回 -32601、切換使用者、開 `task-*` 框、每組提交後投件與刪原件、發布摘要（B-621～625、[B-202](base/execution.md)）。
- **管轄權是約定，不是前提**〔第十九批第 2、5 條〕：tick 對管轄區有最高裁量權，這是 aos 體系裡的約定。Linux 權限上碰不到某些東西時，tick 照樣跑完一格，碰不到的那件照各自規則失敗。管轄區可以重疊，風險自己承擔；aos 體系裡的慣例是不重疊、可以包含（B-628）。
- **`kind:system`**：留給以後真正屬於標準配備、要寫在任務表上的任務；預設範本沒有 system 類任務（kernel 設定檢查是 kernel 類，[P-814](protocol/kernel-tasks.md)）。
- **`aos-clean` 屬標準配備**〔疑點裁定 2〕：範本裡它仍是 custom 類、排在最後的一項任務；算不算標準配備看程式本身，不看任務表寫的 kind。
- kernel、agent、custom 類（含自訂種類）的任務屬其他掛載；它們的外殼、逾時與取消延後（[P-008](protocol/README.md#p-008)）。

**驗收：**範本任務表沒有 system 類任務也能正常跑；回 -32601、投件、刪原件、清框不需要任何任務宣告。在沒有 daemon、git 與 cgroup 的機器上，同資料夾互斥、照陣列順序跑、上下層判定照常成立。

## B-602：同一資料夾一次一格：互斥鎖

〔使用者方向 2026-09-30，第十九批，核心〕**同一資料夾同時只能跑一個 tick。** 這把鎖屬核心，不依賴 git、cgroup 或 daemon。

- **認哪個資料夾**〔第十九批第 7 條〕：辨識一個 tick 看資料夾路徑或 inst.json 路徑；給的是 node 資料夾裡的 `.aos/inst.json` 或 `inst.json` 時，一律正規化成那個資料夾（[inst 目標](base/inst.md#inst-目標檔案或資料夾)）。tick 在這個資料夾裡跑，cwd 就是它；argv 見 [P-203](protocol/node.md)。
- **鎖檔**：`.aos/tick.lock`，ignored，不存在就建立。不放 git 管理目錄；git 還原、`aos-clean` 與一般清理都不得移除或替換它。
- **取鎖**：定位資料夾之後第一件事就是對鎖檔取**非阻塞**獨占 flock；拿不到回 75，什麼都不做，也不在程式內重試。全格持鎖。
- **任務繼承**：任務繼承同一個 open file description 的鎖 fd，號碼放環境變數 `AOS_TICK_LOCK_FD`。工具以 fstat 對上鎖檔並核對獨占鎖，才算在 tick 內；沒有繼承鎖就自己取同一把鎖，不能只信環境變數。任務不得解鎖，退出前關閉自己的副本。這是同帳號的合作約定，不是授權。
- **後代也擋下一格**：只要還有任何程序握著這份鎖（例如任務留下的後代），下一格就拿不到鎖、回 75；這一點不需要 cgroup 就成立。把後代清掉是標準配備的事（[B-202](base/execution.md)、B-631）。經切換使用者用別的帳號開的任務不一定繼承鎖 fd，它的後代由 cgroup 框清。
- daemon 不同時開同一 node 的兩格，是 daemon 自己的排程（[B-601](daemon.md)），不是互斥的來源。

〔建議預設，未拍板〕其他人、agent、工具要改受這格管理的檔案，也須協調這把鎖或先暫停 tick；否則它們的改動可能被標準配備一起提交或還原（B-622）。這是所有寫入者共用的規則，不另外禁止工具改檔。

**驗收：**同資料夾同時跑兩個 `aos-tick`，一個回 75、不改檔；用資料夾路徑與 `.aos/inst.json` 路徑各跑一次，搶的是同一把鎖；前一格留下握著鎖 fd 的後代時，在沒有 cgroup 的機器上下一格也回 75；沒有 git repo 也取得到鎖。

## B-620：任務註冊表：照表依序跑

〔使用者方向 2026-09-29；2026-09-30 第十九批改寫〕任務表只放 `.aos/tasks.json`，陣列位置就是順序。**每項任務是 inst 的超集**：一份 [inst](base/inst.md) 加 aos 的欄位（`id`、`kind`、`group`、`needs`、`methods`）。欄位、JSON 與 schema 以 [P-202](protocol/node.md) 為準，本節只定意思。

**核心做的**〔第十九批，核心〕：

- 開格時讀一次表，只驗四件事：是合法 JSON、`_metainfo` 對、每項（整份 `$ref` 展開後）是合法 inst、`id` 在本表唯一。
- 照陣列順序一項一項照 inst 跑，前一項結束才開下一項；任務以可信 wait 的正常退出 0 算成功。
- `kind`、`group`、`needs`、`methods` 與其他欄位核心不看，交給標準配備（B-629）。
- 核心的結束碼：0 全部成功、1 有任務失敗或被跳過、2 argv 或任務表不合法（尚未開任務）、75 鎖被占；3、125 屬標準配備的提交（[P-203](protocol/node.md)）。

**標準配備另驗的**：`methods` 重複、`needs` 指到不存在或後面的項、循環、非連續 group、類別順序錯。〔暫定，計畫疑-8 未答，照 a〕`kind` 的分段保留：`system` 最前，中段 `kernel`／`agent` 可交錯，`custom` 最後；只驗、不重排，排錯算表壞。〔使用者方向 2026-09-30，第十八批〕kernel 可以自訂任務種類（[T-06](terms.md)）；〔暫定〕寫成「類別.名稱」（例如 `agent.review`），類別只能是 `kernel`、`agent`、`custom`，只看點前的類別排順序，名稱的意思由定義它的 kernel 解釋。`system` 不開放自訂。

**表壞了**（上面兩類任一項）整表拒絕載入，任務一項也不跑，不退回舊表；tick 回 2。標準配備在本 node 寫一件 `config_invalid` 事項指出 `.aos/tasks.json` 哪裡錯，同一問題沿用同一 `issue_id`（[S-405](scheduling/operations.md)）。任務各自開檔讀自己的設定。

**任務的帳號**〔使用者方向 2026-09-30，第十九批，疑點裁定 4；推翻第十八批「任務表不准 `user`」〕：任務可以帶 `user`。省略就用這個 node inst 的 `user`，也就是 tick 自己的有效帳號；帶了而且跟 tick 的帳號不同時，由標準配備的切換使用者開這一項（B-629），准不准照該 node 的身分額度核（[B-301](base/identity-resources.md)）。不另設服務帳號（第九批）；沒有 helper 時整棵樹都是通用 user，帶了別的帳號的那一項照 inst 回 125、不寫 `exit`。要 root 的固定步驟交 helper（[B-609](daemon.md)）；管成員的事（例如成員收件區權限）由上層 kernel 在自己的 tick 用自己的帳號做。任務類別不授予身分或權限。

- **`methods`**〔第十七批〕：node 接受哪些檔案請求由任務表決定，每項用 `methods` 宣告自己處理哪些 method；同一 method 只能由一項任務宣告。由標準配備的收件讀（B-623），method 的意思與 -32601 的條件見 [B-501](base/transport.md)。
- **一個 module 一項任務**：收件、產生請求及處理結果都在該項內做；投件與清收件原件交標準配備，任務不另登記清收件工作。
- 〔使用者方向 2026-09-29〕資源 module、`aos-clean`、收信程式都是同一張表上的普通項目，不再分 pre／post 掛勾；有權限者同樣能直接跑這些程式。資源 module 的啟用與父層限制見 [scheduling/admission](scheduling/admission.md)。

**驗收：**任務帶 `user` 整份照收；帶了跟 tick 不同的帳號、沒有 helper 時那一項回 125，其餘照表處理。表裡 `id` 重複時一項都不跑、回 2。

## B-628：上下層判定：預設看資料夾包含、可登記覆蓋

〔使用者方向 2026-09-30，第十九批第 2、8 條，核心；推翻「上下層看登記、與目錄位置無關」〕每個 tick 都有上層與下層。

- **預設上層**：從本 tick 的資料夾往上找，最近一個「有 tick 的資料夾」。〔暫定，計畫疑-10 未答，照 a〕「有 tick」跟投件時「目標是不是 node」同一個判準：資料夾裡有 `.aos/inst.json` 或 `inst.json`（[inst 目標](base/inst.md#inst-目標檔案或資料夾)）。路徑逐段比對，不展開 symlink（沿 [T-03](terms.md)）。找不到就沒有上層。這是純路徑計算，不靠 daemon。
- **登記覆蓋**〔疑點裁定 5〕：經 daemon 登記時可以指定上層（`parent_id`），蓋過預設。覆蓋要**新舊兩個上層都同意**（舊上層指資料夾推得的那個）；覆蓋後**管轄權仍跟著資料夾**，覆蓋只改管理關係：誰分資源、誰叫醒、誰能解除登記。覆蓋存在 daemon 的登記裡，只在 daemon 底下有；cron 或人手跑的 tick 只看資料夾。登記規則與重啟後怎麼長回來見 [B-606](daemon.md)。
- **有效上層**：有覆蓋就是覆蓋的那個，否則是預設上層。**下層**是有效上層是我的 tick。
- **換上層兩條路**〔撤第十八批「只有重新登記一條路」〕：
  1. **搬資料夾**：搬進別的 tick 的資料夾，新位置最近的那個自動成為預設上層。路徑就是 id，所以等於舊 id 解除、新 id 重登；引用舊路徑的回址會失效，風險自負（T-03）。
  2. **改登記**：用 `parent_id` 覆蓋（B-606）。
  兩條都要被搬的那棵先暫停、程序全空（沿第十八批 Q10）。
- 〔建議預設，未拍板〕**身分繼承**：inst 的 `user` 省略時繼承上層，指的是有效上層（[inst](base/inst.md)）。
- 〔建議預設，未拍板〕**巢狀 git**：上層的 git 提交不管下層 tick 的資料夾，把它們整個排除（寫進 git 管理目錄的 `info/exclude`，不改 `.gitignore`），免得上層還原時蓋掉下層。

**驗收：**`/a` 與 `/a/b` 都有 `.aos/inst.json`、`/a/x` 沒有時，`/a/b` 與 `/a/x/c` 的預設上層都是 `/a`；沒有 daemon 也算得出來。只有新上層同意的覆蓋被拒。覆蓋後 `/a` 對 `/a/b` 資料夾的管轄不變，叫醒與分資源改由新上層做。

## B-629：標準配備：清單與掛載方式

〔使用者方向 2026-09-30，第十九批第 12 條與疑點裁定 1～3、8、9〕標準配備是 aos 出廠就附、預設掛上的一包功能，**必須全掛、不能拆開**。後續設計以它為前提。

| 元件 | 做什麼 | 正本 | 完整路線要的機制；沒有時 |
|---|---|---|---|
| git 提交 | 格首回基線、group 提交與還原、落盤、擋板、合併提交 | B-621、B-622、B-625 | git ≥ 2.36；沒有走 B-632 |
| group 與 needs | 組內全成功才生效、前置成功才跑、表的依賴檢查 | B-620、B-621 | 同 git 提交 |
| 收件 | 分派 method、回 -32601、壞件只報一次、刪原件（Q1）、去重與補投 | B-623、[B-501](base/transport.md)、[B-503](base/transport.md) | 同 git 提交 |
| 投件與鬧鐘 | 先提交再送（Q2）、目標檢查、鬧鐘、經通道送 | B-624 | 同 git 提交 |
| 發布摘要 | 每組提交後發布 `published.json` | B-624、[P-307](protocol/messages.md) | 同 git 提交 |
| `aos-clean` | 過了保留期的清理 | [B-404](base/storage.md) | 同 git 提交 |
| 切換使用者 | 依 node inst 與任務的 `user` 切帳號、佈建動作 | [B-303](base/identity-resources.md)、[B-609](daemon.md) | root helper、通道；沒有只算功能受限 |
| cgroup 框 | node 框、每任務 `task-*`、收尾、上限、量測 | [B-202](base/execution.md)、[B-204](base/execution.md)、[B-605](daemon.md) | cgroup v2 委派子樹、Linux 5.14；沒有走 B-631 |
| once | 經通道把行程掛到 daemon 跑、砍掉、收結果、取消 | [B-203](base/execution.md)、[B-613](daemon.md) | 通道；沒有只算功能受限 |
| 通道傳訊 | 經通道送訊息給同一 daemon 底下的 tick；收件任務自己取 | B-623、B-624、[B-614](daemon.md) | 通道；沒有只算功能受限 |
| daemon 端 | 重啟清空、排空停機 | [B-603](daemon.md)、[B-604](daemon.md) | daemon |
| 全掛檢查 | 看每塊走哪條路 | B-630 | — |

- **怎麼掛**〔疑點裁定 1〕：跟核心同一支 `aos-tick`，預設就在；沒有關掉其中一塊的旗標或設定，也不支援只掛其中幾樣。
- **功能受限不算沒掛**〔疑點裁定 3〕：沒有 helper（只能用通用 user）、沒有通道（不是 daemon 開的格）只是用不到那幾樣功能，那幾樣照各自規則回錯，不警告。
- **有備援就算全掛**〔疑點裁定 8、9〕：cgroup 或 git 不能用（沒 sudo、版本不夠、壞掉）時，標準配備改走內建備援，仍算全掛，只是保證較弱；每項保證在完整與備援下各是什麼見 B-631、B-632。「沒全掛」只剩標準配備本身不能跑（B-630）。
- **欄位歸屬**：任務表的 `kind`、`group`、`needs`、`methods` 由標準配備讀，核心不看（B-620）。
- **通道**：daemon 開 tick 時給的通道（環境變數、憑證、事務）以 [B-612～614](daemon.md) 為正本；任務繼承這些環境變數，在投件權就是執行權（[T-08](terms.md)）之下這是預期行為。
- 〔建議預設，未拍板〕**切換使用者怎麼開任務**：任務帶的 `user` 跟 tick 的帳號不同時，tick 把這一項的 inst（去掉 aos 的欄位）寫成 ignored 的 `.aos/jobs/task-<開格毫秒>-<序號>.json`，經通道用 `node.mount` 掛到 daemon、由 helper 以該帳號開 runner（[B-613](daemon.md)），再用 `node.show` 等它結束、取結束碼，才跑下一項。它跑在 daemon 的掛載框，不在 `task-*`，也不繼承鎖 fd。沒有通道、沒有 helper 或額度不准時這一項回 125。

**驗收：**同一支 `aos-tick` 在有 cgroup、git 的機器與沒有的機器上都算全掛，只有 B-630 印出的路線不同；沒有 helper 時只帶通用 user 的任務照跑。

## B-630：全掛檢查：走完整還是備援

〔使用者方向 2026-09-30，第十九批第 12 條與疑點裁定 3、8、9〕

- **何時查**：tick 取鎖後、讀任務表前查一次，這格內路線不換；`aos-tick --check` 只查、不取鎖、不跑任務（[P-203](protocol/node.md)）。daemon 啟動時照同一套查自己那側（[B-605](daemon.md)）。
- **查什麼**〔建議預設，未拍板〕：
  - **cgroup 框**：cgroup v2 掛著、Linux ≥ 5.14、自己在本 node 的 `n-<h>/tick` 框裡（`/proc/self/cgroup` 的路徑結尾，`<h>` 見 [B-605](daemon.md)）、node 框的 `cgroup.procs` 與 `cgroup.subtree_control` 寫得進去。都成立走完整路線，否則走 B-631。
  - **git 提交**：`git --version` ≥ 2.36、`git rev-parse --absolute-git-dir` 在本資料夾成功、有初始 commit、`git status --porcelain` 跑得完。都成立走完整路線，否則走 B-632。
  - helper 與通道不查，沒有只算功能受限（B-629）。
- **印出路線**：每格在 stderr 印一行，例如 `standard: cgroup=full git=fallback`；兩塊都走完整才是完整保證，任一塊走備援就是備援保證。走備援不寫事項。
- **沒全掛**：只剩標準配備本身不能跑，例如標準配備的程式載不起來、`aos-clean` 找不到、`.aos/journal/` 建不起來。這時在 stderr 印出缺了什麼，然後——
  - **有終端機**（stdin 與 stderr 都是終端機）：問 y／n。答 y 照跑，錯誤自己承擔；〔建議預設〕答 n 不跑、回 2。
  - **沒終端機**（daemon、cron 叫起的）：**照跑，只記警告**。警告寫 stderr；〔建議預設，未拍板〕另在本 node 寫一件事項，`reason:"standard_incomplete"`、`issue_id:"standard-incomplete"`，open 或 done 已有就不再寫，不每格重報。

〔使用者方向 2026-09-30，第十九批〕現行「沒 cgroup v2 就拒絕啟動」「不在框就拒跑」都改成這一套。

**驗收：**不在 node 框裡跑 `aos-tick`，stderr 印 `cgroup=fallback` 並照常跑完；沒有 repo 的資料夾印 `git=fallback` 並照常跑完；`aos-clean` 找不到時有終端機會問，答 n 回 2、不開任務，沒終端機照跑並有一件 `standard-incomplete` 事項。

## B-631：cgroup 框的備援〔建議預設，未拍板〕

〔使用者方向 2026-09-30，第十九批，疑點裁定 8〕cgroup 不能用時（沒 sudo 拿不到委派子樹、kernel 太舊、不在 node 框裡），標準配備改用不需要 root 的機制頂替。**準備方式**：不用 sudo 時首推 systemd 的使用者委派子樹，例如 `systemd-run --user --scope -p Delegate=yes aos daemon --config …`；細節與其他做法見 [B-605](daemon.md)，準備好就走完整路線。

備援的做法：

- **收後代**：`aos-tick` 開格時設 `PR_SET_CHILD_SUBREAPER`，任務留下的孤兒都掛回 tick。每個任務照 inst 另開 session／process group。任務主程序結束後，對它的 process group 送 SIGKILL，再反覆找 tick 名下剩下的子程序，逐一 SIGKILL 並 wait，直到沒有才跑下一項。
- **上限**：只能用每個程序各自的 rlimit：記憶體用 `RLIMIT_AS`、CPU 時間用 `RLIMIT_CPU`，exec 任務前設，子程序繼承但各自算。不用 `RLIMIT_NPROC`（它算整個帳號）。〔暫定〕值從哪來：走備援時 daemon 的 `cgroup_*` 動作回 `unsupported`（[B-605](daemon.md)），上層 kernel 分的額度寫不到成員身上，所以成員的額度**只記帳、不擋**；rlimit 只取 tick 自己啟動時已有的值（部署者或 shell 事先設的），標準配備不另算、不另設。
- **量測**：只有已 wait 的子程序的 `getrusage`（CPU 時間、最大 RSS）。
- **daemon 那側**：daemon 同樣設 subreaper，收尾時對 tick 的 process group 與掛回 daemon 的孤兒送 TERM、等寬限、再 KILL（[B-603](daemon.md)、[B-604](daemon.md)）。

| 保證 | 完整（cgroup） | 備援 |
|---|---|---|
| 任務結束後代清空 | 看 `task-*` 的 populated，`cgroup.kill` 一次清完，另開 session 也跑不掉 | 只清得到掛回 tick 的程序；經外部服務（systemd、at 等）開的、換成別的帳號的清不到 |
| tick 自己被殺之後 | daemon 收尾 `tick` 與 `task-*`，下格格首再清 | daemon 開的格，孤兒掛回 daemon、由它收尾；人手、cron 跑的掛到 init，清不到，只靠鎖擋下一格（B-602） |
| daemon 重啟清空舊程序 | 照受管框逐一收尾（B-603） | 舊 daemon 的孤兒已掛到 init，清不到；還握著鎖的會讓該 node 下一格回 75 |
| 資源上限 | node 框的總量上限（記憶體、CPU、pids） | 每個程序各自的上限，不是總量；沒有 pids 上限 |
| 用量量測 | cgroup 計量 | 只算已 wait 的子程序，粗略 |
| OOM 判定 | 有 oom_kill 證據才標 OOM（B-204） | 沒有證據，一律不標 OOM，只留訊號 |
| 逃生口 | node 自開子框留常駐程序（B-605） | 沒有；任務留下的常駐程序會被清掉 |

**驗收：**不在 cgroup 框裡跑時，任務 fork 後 setsid 的後代在該任務結束後被清掉，下一項開始前已經沒有；單一程序超過記憶體上限的任務失敗，結果不標 OOM。

## B-632：git 提交的備援：檔案日誌〔建議預設，未拍板〕

〔使用者方向 2026-09-30，第十九批，疑點裁定 9〕git 不能用時（沒裝、版本低於 2.36、沒有 repo 或 repo 壞掉），標準配備改用**檔案日誌**頂替提交。要走完整路線：裝 git ≥ 2.36，讓 node 資料夾是有初始 commit 的 repo（`aos node new` 會建，[P-210](protocol/node.md)）；檢查步驟見 B-630。

- **完成紀錄**：每組全部成功時，標準配備在 ignored 的 `.aos/journal/` 寫一筆：暫存檔完整寫入 → fsync → rename 成正式名 → fsync 目錄。寫之前，本組寫的消費副本與待送檔先各自 fsync。紀錄落盤就算這組「已提交」；格式見 [P-205](protocol/node.md)。
- **Q1**：完成紀錄落盤後才刪跟消費副本 bytes 相同的收件原件（B-623）；沒有完成紀錄的副本不算證據，下一格可以重收、覆寫。
- **Q2**：完成紀錄落盤後才投出本組的待送檔、發布摘要（B-624）；投出後把待送檔搬到 `.aos/journal/sent/{requests,responses}/<id>.json`，保留期內留著供補投，過期由 `aos-clean` 清（[B-404](base/storage.md)）。
- **needs 與 group**：跨組依賴看前組有沒有完成紀錄。組內有失敗就不寫紀錄，本組開始後新出現的待送檔不投，搬到 `.aos/journal/discarded/` 留給人看；依賴它的組跳過。
- **沒有還原**：失敗組與當機時寫到一半的改動留在工作區，不回到基線。
- **紀錄寫不進**（滿碟、I/O 錯）：跟 commit 失敗一樣停止後續組、回 3、寫擋板檔（B-622）。
- **換回 git**：git 之後能用了，第一格不還原，先把整個工作樹提交成一個 commit（訊息 `aos-tick adopt`），之後走完整路線；日誌由 `aos-clean` 照保留期清。

| 保證 | 完整（git） | 備援（檔案日誌） |
|---|---|---|
| 組內全成功才生效 | 一個 commit；失敗還原整組 | 有完成紀錄才算生效；失敗不還原，改動留著 |
| 格首回到基線 | 回到最近 commit | 不回 |
| 做完才刪原件（Q1） | commit 落盤後刪 | 完成紀錄落盤後刪（保住） |
| 先提交再送（Q2） | commit 落盤後投；失敗組的待送檔被還原 | 完成紀錄落盤後投；失敗組的待送檔不投（保住） |
| 依賴讀已完成結果 | 前組 commit 成功 | 前組有完成紀錄（保住） |
| 同 ID 重送補投原回應 | 從 git 歷史撈（B-503） | 從 `.aos/journal/sent/` 撈，只在保留期內 |
| 歷史、回溯、讀同一版本 | 有 | 沒有，只能讀目前的檔案 |

**驗收：**沒有 git 的機器上，任務收了件而在寫完成紀錄前被殺，下一格原件還在、重收；紀錄落盤後被殺，下一格補刪原件、不重吃。失敗組的待送檔沒有投出。同 ID 重送時從 `.aos/journal/sent/` 補投原 bytes。

## B-621：group 與 needs

〔使用者方向 2026-09-29；第十九批改歸標準配備〕以下是標準配備的 group 與 needs（B-629）；沒有 git 時「提交」「還原」照 B-632。組內全成功才一起生效，任一失敗就還原這組的 git 管理範圍；`needs` 的前置成功才執行。前面已提交的組不因後面失敗而撤回。

〔建議預設，未拍板〕採最小的順序語意：

- 同組項目連續，每項只屬一組。`needs` 只能指向本表前面的任務；缺依賴、循環或非連續 group 算表壞（B-620）。
- 同組可依賴前項本次執行成功；跨組則須等前項所在組提交成功。任務預設以正常退出且碼為 0 表示本步成功，不代表整件產品任務完成。
- 組內有失敗或因前置不成立而跳過，該組不提交，餘下項目跳過並還原。該組先前暫時成功的任務，也不能供後續組當成有效前置。
- 後面的獨立組可以繼續，依賴失敗組的組跳過。依賴只管本格，不沿用上格的成功旗標，也不另做跨格任務排程器。

## B-622：git 提交與還原

〔使用者方向 2026-09-29；第十九批改歸標準配備，推翻「git 就是 tick 引擎本身」〕標準配備的 git 提交把每個 node 資料夾當成一個 git repo。一格開始前，受管理的工作區回到最近一次 commit；每組成功便 commit 它的變動，失敗便還原到該組開始時的 commit。外部收件與不想管理的內容放 `.gitignore`。不用帳本或 SQLite，也不另存一套提交提案與收據。鎖不在這裡（B-602）；沒有 git 時照 B-632。

〔使用者方向 2026-09-30，第十八批〕**落盤**：git 最低版本 2.36（檢查見 B-630）。aos 自己的程式每次呼叫 git 都帶 `-c core.fsync=committed,reference`，不靠 repo 或使用者的 git 設定；這樣 commit 成功時物件與 ref 都已落盤，之後才刪收件原件（B-623）、才投件（B-624）。

〔建議預設，未拍板〕第一格前先有初始 commit。每組開始固定這組的管理範圍，以基線 commit 的 ignore 規則管理這組的修改、新增、刪除與 index；還原包含已暫存及尚未 `add` 的本組新增檔，卻不能清掉 ignored 收件與工作資料夾。任務改 `.gitignore` 不能逃出還原範圍：不採失敗工作樹的新 ignore，已追蹤檔不因新增 ignore 脫管，新規則從下一組開始算。不用全樹 `git clean -x`，不遍歷 git 管理目錄或子 repo（第十九批依方案 A 從 [P-205](protocol/node.md) 搬上）。沒變動不 commit。任務自行換 HEAD／分支、或後代還沒清空時，保留現場，不盲目還原。

〔建議預設，未拍板〕commit 或還原失敗時停止這個 node 的後續任務與新一格，保留既有 commit 並報出原因，修復後才恢復；不把未提交工作當成功。本格故障回 3 並寫擋板檔；之後的格首看到擋板檔回 125、不碰工作樹。修復者暫停、持鎖、核對 repo 後移除擋板。停格由 daemon 依 [B-607](daemon.md) 做，錯誤摘要走[待處理事項](scheduling/operations.md)，不能只寫在即將還原的檔案裡。擋板檔位置與提交訊息格式見 [P-205](protocol/node.md)。

〔建議預設，未拍板〕這裡的「原子」只指**同一 repo 的已提交版本與恢復基線**，不保證執行期間多個工作檔同時變動。需要一致狀態的查詢或正式輸出讀同一 commit。ignored 檔、另一個 repo、外部 workspace 與 API／寄信等不可逆後果不會跟著還原。

## B-623：收件：分派、-32601，commit 後才刪原件（Q1）

〔使用者方向 2026-09-29；第十九批改歸標準配備〕以下都是標準配備的收件做的（B-629）。

**分派與 -32601**〔第十七批；第十九批從 B-620 搬來〕：開格載入任務表後、跑第一項前，列一次 `requests/` 裡已發布的請求；method 沒有任何任務宣告的，照 [B-501](base/transport.md) 回 -32601：原件複製進追蹤區當消費證據、錯誤回應放進待送區，自成一組提交後照 B-624 投出、照下面刪原件（路徑與提交訊息見 [P-202](protocol/node.md)、[P-205](protocol/node.md)）。有宣告的留給那項任務自己讀。

**接件前核對回址**〔建議預設，未拍板；第十九批依方案 A 從 [P-303](protocol/messages.md) 搬上〕：處理 method 的任務接件前，核對 `reply_to` 是可用的 node 回件位置、目前身分投得進它的 `responses/`；回不了就不接納會產生副作用的請求，保留原件及本地錯誤供修正，不能先執行再假裝已回覆。接納後固定原請求的 `reply_to`，回應隨狀態提交後照 B-624 投出；投遞遇暫時性失敗只補送已提交的回應，不重做請求。`reply_to` 不是來源或授權證明（B-501）。

〔使用者方向 2026-09-29〕**Q1**：訊息及工具／LLM 結果落在 ignored `requests/`、`responses/`。任務先把原件逐 byte 複製到追蹤區，留下消費證據；**標準配備在這組 commit 成功後才刪與已提交副本 bytes 相同的收件原件**。commit 前當機，原件仍在，下格可重收；commit 後當機，依已提交證據補清原件，不重吃。原件跟已提交副本不同就報衝突並保留（[B-503](base/transport.md)）。組歸屬由 commit 邊界決定，不另寫 task／group 欄位。沒有 git 時「commit」換成 B-632 的完成紀錄。

〔使用者方向 2026-09-30，第十八批〕**壞掉的收件錯誤只報一次**：`requests/` 裡讀不懂、沒有合法 ID 或安全回址、因而回不了錯誤回應的件，發現的一方（標準配備的收件或宣告該 method 的任務）在本 node 寫一件事項；〔暫定〕`issue_id` 由檔名固定算出（[P-601](protocol/ops.md)），`.aos/attention/` 的 open 或 done 已有同一 `issue_id` 就不再寫，所以同一個壞件不會每格重報。原件留在收件區不動，過了保留期由 `aos-clean` 刪（[B-404](base/storage.md)）。只算 `requests/`，`responses/` 與同 ID 異內容的衝突照各自規則。

〔使用者方向 2026-09-30，第十九批，疑點裁定 7〕**通道上的暫存訊息**：同一 daemon 底下別的 tick 經通道送來的訊息，daemon 放在記憶體；標準配備的收件不代取，由要收的那項任務自己上通道用 `node.take` 取（[B-614](daemon.md)），格式跟檔案收件相同。取走後怎麼落地、要不要留消費副本由那項任務決定；不保證送達，daemon 當掉就丟。〔建議預設〕沒人取的訊息不回 -32601。

請求 ID、同 ID 衝突及保留期內的去重見 [base/transport](base/transport.md)，完整檔案發布與儲存位置見 [base/storage](base/storage.md)，追蹤區路徑見 [P-206](protocol/node.md)。

**驗收：**沒有任務宣告的 method 由標準配備回 -32601、原件被清，任何任務都沒讀到它；argv 少了 `aos` 或跟 method 不符，由宣告它的任務回 -32601。同一個壞收件連跑多格只有一件事項。

## B-624：派出：先 commit 請求，再送出（Q2）

〔使用者方向 2026-09-29；第十九批改歸標準配備〕任務把帶固定 ID 的請求或回應放進追蹤的 `.aos/outbox/`，**標準配備在所屬 group commit 成功後才投出**；失敗組的待送檔一起還原。LLM／工具結果留待後續格收，不在原地等遠端工作結束。待送封套與鬧鐘紀錄的格式見 [P-206](protocol/node.md)。沒有 git 時照 B-632。

每組 commit 成功後，標準配備從該 commit 發布 `.aos/summary/published.json`、投出待送 message、照 B-623 刪收件原件；新格恢復後也補做發布與投件，只用已提交內容。投件成功後移除待送檔，刪除在下一組或格末一起提交；刪除本身就是變動，不造空 commit。提交前當機可再投相同 bytes，接收方依 [B-503](base/transport.md) 去重。能投件不等於能經 daemon 叫醒對方；誰來叫醒見 [S-201／202](scheduling/admission.md)。

〔使用者方向 2026-09-29 晚，第十五批〕**投件只查一件事：目標是不是一個 node**（照 [inst 目標](base/inst.md#inst-目標檔案或資料夾)的找法：`target_node` 是資料夾，且有 `.aos/inst.json` 或 `inst.json`）。

- 不是 node，或投件時沒有寫入權限：在 stderr 印一行（`target_not_node`／`target_not_writable`），這封不投、不重試、不改投別處，待送檔跟成功投件一樣移除（原檔仍在 git 歷史），不寫待辦。權限補上後要再送，由投件者重新產生待送檔。
- 送出遇到暫時性錯誤：留著待送檔，下格再投。
- 是 node 就投進去，之後 aos 都不管：對方有沒有裝任務、有沒有被 tick、多久才處理，都不過問。

〔使用者方向 2026-09-30，第十九批第 9 條〕**經通道送**：待送的**請求**（`.aos/outbox/requests/`）帶 `channel:true` 時，本格有通道就改用 `node.send` 經 daemon 送（[B-614](daemon.md)），訊息跟檔案投件是同一個 JSON-RPC 物件；回應一律走檔案投件。`urgent:true` 是急件，送到時 daemon 叫醒收件 tick，只在走通道時有用。誰能送看寄件 tick 的帳號對收件 tick 的 `requests/` 有沒有寫權（疑點裁定 6），由 daemon 判。〔建議預設，未拍板〕處理結果：

- 送成功：跟檔案投件一樣移除待送檔。不保證送達。
- `mailbox_full`：留著待送檔，下格再試。
- `forbidden`：跟 `target_not_writable` 一樣印一行、移除待送檔。
- 本格沒有通道（`no_channel`），或其他錯誤（例如收件 tick 不在同一個 daemon 的 `not_registered`、`message_too_large`）：改走檔案投件，照上面的規則。

〔使用者方向 2026-09-29 晚，第十五批〕**鬧鐘（可選）**：待送封套可帶 `alarm_ms`。投出成功後標準配備在 ignored 的 `.aos/alarms/` 記一筆；到期後本 node 的下一格去看，那封原件還在對方收件區就算沒被處理，在 stderr 印 `request_not_handled`；不寫待辦、不重投、不取消。原件已被取走就算處理了，不印。看完不管結果都刪掉這筆。aos 不為鬧鐘另外叫醒 node，要準時就讓這個 node 有定期 tick；沒設就完全不等、不逾時。經通道送出的不設鬧鐘。〔使用者方向 2026-09-30，第十八批〕agent 範本對每個請求預設帶鬧鐘（[P-706](protocol/agent-tasks.md)）；被丟掉的件沒有鬧鐘、兩者對不上的問題延後（[P-008](protocol/README.md#p-008)）。

可重投同 ID、同 bytes 的已提交封套，這只是補投同一封檔案，不授權重做不明的工具／LLM 執行。〔第十九批〕once 由 module 後續讀已提交材料，經通道用 `node.mount` 掛到 daemon（[B-613](daemon.md)），不往待送區塞 IPC。無可信結果且不能證明未執行的工作記 unknown，不自動再執行；見 [S-401](scheduling/operations.md)。

## B-625：當機恢復、設定與清理

〔使用者方向 2026-09-29〕經 daemon 跑的 node，daemon／VM 重啟先按 [B-603](daemon.md) 清空舊程序。各 node 下一格在鎖內還原未 commit 的變動，已提交組與完整結果檔保留；收件重複按 Q1 處理，未明的工具／LLM 請求按 Q2 處理。能恢復本地 tick 不等於能重做 unknown 外部工作。沒有 git 時不還原，照 B-632。

設定修改、重要設定暫停手改、普通設定匯入，以 [A-102](agent/configuration.md) 為正本。恢復 tick 前須完成該流程，不能把合法手改當作未提交任務還原。

〔使用者方向 2026-09-29〕**別濫用 git**：沒變動不 commit；實作可定期合併提交，也可用 git submodule 分開高頻與不常變動的部分。清理見 [B-404](base/storage.md)。

〔建議預設，未拍板〕沒變動的成功組視為完成，不製造空 commit。合併提交的維護須暫停、持鎖，保留可恢復的目前版本及仍被請求或設定引用的 commit 或內容；不能為省 commit 把「先提交再送出」延到送出之後。使用 submodule 時各 repo 有自己的提交邊界，父 repo 的 commit 只管 gitlink，不代表子 repo 工作區也已提交／還原，不承諾跨 repo 的 group 原子性。

## B-627：人手或 cron 直接跑一格：風險自負

〔使用者方向 2026-09-30，第十九批第 12 條；撤第十八批審稿裁定 16「不在框就拒跑」〕`aos-tick` 誰都能直接跑（人手、cron、其他程式），不看自己在哪個 cgroup，照常做完一格；風險由跑的人自己承擔。

- 直接跑的格沒有通道，用不到 once、通道傳訊與切到別的帳號（B-629 的功能受限）。
- 不在 node 的 cgroup 框裡時，全掛檢查走 cgroup 備援（B-630、B-631），照常跑。
- 同一資料夾 daemon 正在跑一格時，直接跑的那格拿不到鎖、回 75（B-602）；反過來也一樣。
- 想經 daemon 跑一格：送 `node.wake`，以回應的值為起點，再用 `node.show` 等格次前進；怎樣算新的一格已完成、`registration_id` 換了怎麼辦，以 [B-607](daemon.md) 為正本。不另開「跑一格並等結果」的 IPC。CLI 入口見 [H-004](cli/commands.md)。

**驗收：**在 daemon 框外直接跑 `aos-tick` 照常做完一格，stderr 印 `cgroup=fallback`；daemon 正在跑同一 node 時直接跑回 75、不改檔；經 `node.wake` 跑的那一格照 B-607 判定為完成。

## 驗收與尚未定案

group、Q1／Q2、還原範圍、設定與空 commit 的故障驗收，統一見 [V-03](conformance.md)。

註冊表格式以協議篇為準；順序式 group／needs、兩個備援的做法都是工程預設。〔暫定〕`kind` 分段保留（計畫疑-8）、「有 tick 的資料夾」看 inst 檔（計畫疑-10）。
