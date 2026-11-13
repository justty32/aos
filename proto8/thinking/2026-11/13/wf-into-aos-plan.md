# repo 的 wf/ 走入 aos 的規劃與施工（線遷 11-13 晚，家機；使用者已裁，段 1～3 已進 main）：規矩改成 json 節點、只寫跟通用版不同的地方；歷史原地凍結；AGENTS.md 開場導向 aos 知識庫與 wf 公共知識庫；SESSION-LOG 單條化成 json；code map 搬進 aos json；分段進 main，段 3 以後用到才換

← [11-13 日索引](README.md)｜前情：[12/wf-to-aos](../12/wf-to-aos.md)（D1～D5）、[main-session-in-aos](main-session-in-aos.md)、[workflows-into-aos](workflows-into-aos.md)（通用版併入）、[agents-feedback-1113-題目](agents-feedback-1113-題目.md)（public／tools／temp 的位置）｜寄信給人那塊：[user-zone-plan](user-zone-plan.md)（線人）

> 流程照使用者 11-13 晚定的：opus 帶隊（線遷）→ 五隻 sonnet 唯讀盤點 → opus 匯總成備料 → fable 只讀備料做規劃（一次，原樣收）→ opus 細化對到檔案 → 使用者裁 14 題 → 施工。Q14（code map）另派 fable 規劃一次（[07 備料](wf-into-aos-plan/07-codemap備料.md)→[08](wf-into-aos-plan/08-fable-codemap規劃.md)）。沒起 aos 行程、沒碰 `~/aos-home`、沒寄信。

## 使用者原話（今晚，逐字）

- 「對了，我們這個~/repo/aos，你可以開始規劃從wf/走入aos了，還是說已經好了？」（頂層答：還沒好，開始規劃。）
- 「先派opus帶隊，指揮sonnet搜集訊息，然後opus整理匯總，交給fable規劃與設計架構，然後opus深化細化架構，最後再來實作。」

11-12 起的原話、D1～D5、W11、裁-2／4／5 的相關句收在 [01 § 使用者原話](wf-into-aos-plan/01-原話與備料.md#使用者原話逐字)。

## 一句話規劃

- **規矩與知識**：一個工作流一個 json 節點，放 repo 的 `wf/workflows/`、`wf/knowledge/`；通用版（`proto8/knowledge/wf/`）已有的，本地只寫 `base`（指通用節點）＋`local`（這裡不一樣的幾條），不抄第二份。
- **歷史紀錄**（佔 `wf/workflows/` 77%）原地凍結，不轉、不搬、不刪。
- **活狀態**：留 repo、進 git（要跨兩台；goal／todo 不給 eca）；SESSION-LOG 單條化成 `wf/session-log.json`（Q5），HANDOFF 只留最新一條（Q12）；WAIT_USER 照 user-zone-plan 切到使用者專區；樹內的信走 aos 信箱，inbox 腳本全刪（Q13），`wf/inbox` 夾只收樹外專案（arcagi）。
- **always-on**：AGENTS.md 開場兩條導引——先讀 aos 知識庫入口，再用 `index_view` 把 `wf/` 當公共知識庫走到 `common/user.md`（Q3）。
- **code map**：手寫地圖成 `wf/knowledge/code-map.json`、逐檔表成 `wf/knowledge/code-map/proto8/<頂層夾>.json`、生成器合成 `index_gen.py` 一支（Q14，[08](wf-into-aos-plan/08-fable-codemap規劃.md)）；鐵律 6 改走 aos json、不用 `.csv`（Q8）。
- **不搬去** `~/aos-home/ws/public`、`ws/tools`、`ws/temp`：那三處是單機、不進 git。

## 分段施工（每段可獨立進 main、可 revert；細節與驗收見 [04](wf-into-aos-plan/04-施工分段與驗收.md)）

| 段 | 一行 |
|---|---|
| 0 | 不改檔：在 `repo-aos` 畫面 compact 一次、開一次新 session，驗 repo 的 hook 在 eca 身裡跑不跑 |
| 1 | AGENTS.md 開場兩條導引：aos 知識庫入口＋`index_view` 把 wf 當公共知識庫走到 `common/user.md`（Q3）——**已做** |
| 2 | HANDOFF 改覆寫式、只留最新一條——**已做** |
| 2b | SESSION-LOG 單條化成 `wf/session-log.json`（Q5），跟頂層約時間 |
| 3 | 第一個工作流 decisions 轉 `decisions.json`（base＋local），刪舊 md、改 3 個連入、WORKFLOWS 那列改指 json；請使用者看一次 json 好不好讀——**已做（待使用者看 json）** |
| 4 | planning、investigation、feature-dev、testing、tidy、refactor 依連入少到多，用到才換 |
| 5 | 知識類 conventions、gotchas、dev-env、data-files、team-model 轉 `wf/knowledge/*.json`，user 最後（同 commit 改 `compact_reload.sh`） |
| 6 | dispatch、CLAIMS 轉 json；aos-teams 進共用知識庫 `proto8/knowledge/aos/`（Q9）；下次開隊時做 |
| 7 | inbox 規矩縮成 `inbox.json`（樹內 aos 信箱、樹外 `wf/inbox` 夾），inbox 腳本全刪（Q13） |
| 8 | WAIT_USER 照 user-zone-plan 接上 |
| 9 | 收尾：手寫 `wf/_index.json`、WORKFLOWS／INDEX／STRUCTURE 退場、AGENTS.md 改成目標輪廓、丟棄清單給使用者點頭 |

## 使用者裁定（14 題，原話與逐題表見 [05](wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）

跟推薦不同的六題：Q3 寫進 AGENTS.md、走 aos index；Q5 SESSION-LOG 單條化成 json；Q8 鐵律 6 納入 aos json、`.csv` 不用；Q9 aos-teams 進共用知識庫；Q13 inbox 腳本全刪；Q14 code map 要搬（fable 規劃見 08）。其餘照推薦。

**還要使用者裁的**：08 的 C1～C5（逐檔表放哪、切不切檔、生成器合一、通用版加不加、轉址檔留多久），fable 推薦全甲、隊長同意；以及看一次 `wf/workflows/decisions.json` 好不好讀。

## 分檔目錄

| 分檔 | 內容 |
|---|---|
| [01-原話與備料](wf-into-aos-plan/01-原話與備料.md) | 使用者原話與已定前提；五隻 sonnet 的盤點匯總（總量、工作流逐項對通用版、三軸＋HANDOFF＋CLAIMS、信件、wf/tools、入口與 always-on）；fable 唯一的輸入 |
| [02-fable規劃](wf-into-aos-plan/02-fable規劃.md) | fable 交稿原樣：目標形狀、三層分法、去向表、三軸、always-on、AGENTS.md 輪廓、丟棄候選、搬遷十段、十題待裁、十六條 aos 問題 |
| [03-opus細化](wf-into-aos-plan/03-opus細化.md) | fable 待驗 15 項的結果；跟 fable 不同的七處；目標形狀落到檔名；十四條邊緣狀況 |
| [04-施工分段與驗收](wf-into-aos-plan/04-施工分段與驗收.md) | 總規則、共同驗收、段 0～9（觸發、動哪些檔、驗收、退回）、工單模板 |
| [05-待裁與衝突](wf-into-aos-plan/05-待裁與衝突.md) | 14 題（選項＋後果＋推薦）；跟現行規矩的衝突 12 條 |
| [06-試驗紀錄](wf-into-aos-plan/06-試驗紀錄.md) | 撞到的 aos 問題 24 條（只記不改） |
| [07-codemap備料](wf-into-aos-plan/07-codemap備料.md) | Q14 給 fable 的唯一輸入：code map 現況、兩支生成器、index 慣例 |
| [08-fable-codemap規劃](wf-into-aos-plan/08-fable-codemap規劃.md) | fable 交稿原樣（目標形狀、生成器合一、鐵律 3 改字、搬遷六步、C1～C5）＋隊長細化（待驗結果、impls／extras 13 個連入要另約） |

## 還沒做的

- 已進 main：段 1（AGENTS.md 開場導引）、段 2（HANDOFF 只留一條）、段 3（decisions 轉 json），紀錄見 [04 施工紀錄](wf-into-aos-plan/04-施工分段與驗收.md#施工紀錄)。
- 段 0 的兩項實測（compact 後 hook、新 session 的 SessionStart）要在 `repo-aos` 畫面上做，本線做不到。
- 段 2b、4～9 沒做（2b 要跟頂層約、其餘用到才換）；inbox 腳本還沒刪（段 7）；code map 搬遷（08）等 C1～C5 裁。
- fable 主規劃只派一次；細化跟它不同的七處沒再送回給 fable 看。
