# repo 的 wf/ 走入 aos 的規劃（線遷 11-13 晚，家機；只規劃、未施工）：規矩改成 json 節點、只寫跟通用版不同的地方；歷史原地凍結；活狀態留 repo 的 md；每個 session 開場用 CLI hook 印使用者偏好；分十段、一段一段進 main，段 3 以後用到才換

← [11-13 日索引](README.md)｜前情：[12/wf-to-aos](../12/wf-to-aos.md)（D1～D5）、[main-session-in-aos](main-session-in-aos.md)、[workflows-into-aos](workflows-into-aos.md)（通用版併入）、[agents-feedback-1113-題目](agents-feedback-1113-題目.md)（public／tools／temp 的位置）｜寄信給人那塊：[user-zone-plan](user-zone-plan.md)（線人）

> 流程照使用者 11-13 晚定的：opus 帶隊（線遷）→ 五隻 sonnet 唯讀盤點 → opus 匯總成備料 → fable 只讀備料做規劃（一次，原樣收）→ opus 細化對到檔案 → **到此停**。沒改 `wf/` 任何檔、沒起 aos 行程、沒碰 `~/aos-home`、沒寄信。

## 使用者原話（今晚，逐字）

- 「對了，我們這個~/repo/aos，你可以開始規劃從wf/走入aos了，還是說已經好了？」（頂層答：還沒好，開始規劃。）
- 「先派opus帶隊，指揮sonnet搜集訊息，然後opus整理匯總，交給fable規劃與設計架構，然後opus深化細化架構，最後再來實作。」

11-12 起的原話、D1～D5、W11、裁-2／4／5 的相關句收在 [01 § 使用者原話](wf-into-aos-plan/01-原話與備料.md#使用者原話逐字)。

## 一句話規劃

- **規矩與知識**：一個工作流一個 json 節點，放 repo 的 `wf/workflows/`、`wf/knowledge/`；通用版（`proto8/knowledge/wf/`）已有的，本地只寫 `base`（指通用節點）＋`local`（這裡不一樣的幾條），不抄第二份。
- **歷史紀錄**（佔 `wf/workflows/` 77%）原地凍結，不轉、不搬、不刪。
- **活狀態**：SESSION-LOG、HANDOFF 留 repo 的 md（要跨兩台、進 git；goal／todo 不給 eca）；WAIT_USER 照 user-zone-plan 切到使用者專區；樹內的信走 aos 信箱，`wf/inbox` 只收樹外專案（arcagi）。
- **always-on**：推薦 CLI 的 SessionStart hook 每個 session 開場印 `user.md` 入口（Q3 待裁），AGENTS.md 維持薄路由。
- **不搬去** `~/aos-home/ws/public`、`ws/tools`、`ws/temp`：那三處是單機、不進 git。

## 分段施工（每段可獨立進 main、可 revert；細節與驗收見 [04](wf-into-aos-plan/04-施工分段與驗收.md)）

| 段 | 一行 |
|---|---|
| 0 | 不改檔：在 `repo-aos` 畫面 compact 一次、開一次新 session，驗 repo 的 hook 在 eca 身裡跑不跑 |
| 1 | always-on 補洞：SessionStart matcher 加 `startup\|resume`、`compact_reload.sh` 開場只印 `user.md` 入口（或 Q3 選 A：偏好進 AGENTS.md） |
| 2 | HANDOFF 改覆寫式、只留最新一條 |
| 3 | 第一個工作流 decisions 轉 `decisions.json`（base＋local），刪舊 md、改 3 個連入、WORKFLOWS 那列改指 json；請使用者看一次 json 好不好讀 |
| 4 | planning、investigation、feature-dev、testing、tidy、refactor 依連入少到多，用到才換 |
| 5 | 知識類 conventions、gotchas、dev-env、data-files、team-model 轉 `wf/knowledge/*.json`，user 最後（同 commit 改 `compact_reload.sh`） |
| 6 | dispatch、aos-teams（留 repo）、CLAIMS 轉 json，下次開隊時做 |
| 7 | inbox 規矩縮成 `inbox.json`（樹內 aos 信箱、樹外 `wf/inbox`），腳本照 Q13 |
| 8 | WAIT_USER 照 user-zone-plan 接上 |
| 9 | 收尾：手寫 `wf/_index.json`、WORKFLOWS／INDEX／STRUCTURE 退場、AGENTS.md 改成目標輪廓、丟棄清單給使用者點頭 |

## 要使用者裁的（14 題，詳 [05](wf-into-aos-plan/05-待裁與衝突.md)）

Q1 歷史紀錄→凍結；Q2「檢查工具不留」→指模板那套；Q3 偏好怎麼每輪都在→CLI hook（B）；Q4 WAIT_USER 舊條目→照 user-zone-plan；Q5 SESSION-LOG 長條目→改一行＋連結；Q6 節奏→段 0～3 先做、之後用到才換；Q7 看板與決策頁→凍結；Q8 tabledb／鐵律 6→先不改；Q9 aos-teams→留 repo；Q10 久沒用的工作流→不轉、段 9 問；Q11 丟棄清單→段 9 一次給；Q12 HANDOFF 覆寫式→是；Q13 inbox 腳本→留 send／read、其餘刪；Q14 code map→不搬。

## 分檔目錄

| 分檔 | 內容 |
|---|---|
| [01-原話與備料](wf-into-aos-plan/01-原話與備料.md) | 使用者原話與已定前提；五隻 sonnet 的盤點匯總（總量、工作流逐項對通用版、三軸＋HANDOFF＋CLAIMS、信件、wf/tools、入口與 always-on）；fable 唯一的輸入 |
| [02-fable規劃](wf-into-aos-plan/02-fable規劃.md) | fable 交稿原樣：目標形狀、三層分法、去向表、三軸、always-on、AGENTS.md 輪廓、丟棄候選、搬遷十段、十題待裁、十六條 aos 問題 |
| [03-opus細化](wf-into-aos-plan/03-opus細化.md) | fable 待驗 15 項的結果；跟 fable 不同的七處；目標形狀落到檔名；十四條邊緣狀況 |
| [04-施工分段與驗收](wf-into-aos-plan/04-施工分段與驗收.md) | 總規則、共同驗收、段 0～9（觸發、動哪些檔、驗收、退回）、工單模板 |
| [05-待裁與衝突](wf-into-aos-plan/05-待裁與衝突.md) | 14 題（選項＋後果＋推薦）；跟現行規矩的衝突 12 條 |
| [06-試驗紀錄](wf-into-aos-plan/06-試驗紀錄.md) | 撞到的 aos 問題 24 條（只記不改） |

## 還沒做的

- 全部施工（段 0～9）；14 題待裁。
- 段 0 的兩項實測（compact 後 hook、新 session 的 SessionStart）要在 `repo-aos` 畫面上做，本線做不到。
- fable 只派一次；細化跟它不同的七處沒再送回給 fable 看。
