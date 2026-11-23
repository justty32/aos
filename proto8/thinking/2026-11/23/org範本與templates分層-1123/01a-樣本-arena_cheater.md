樣本一 `arena_cheater` 的組織怎麼寫的：一隻 eca 加五個 agent-fsm 部門，四個樣本裡最大、最完整的一個（11-23 唯讀讀它的文件與定義，沒碰它的樹）。

# 樣本一：arena_cheater（多部門生產線）

← [入口](README.md)｜[總結與對照](01-四個樣本的總結.md)

路徑都在 `/mnt/c/code/mine/arena_cheater/` 底下。

## 規模與身體

- **一隻協調加五個部門**：`main`（eca，Claude Code，沒有部門資料夾）、策劃 `design`、開發 `dev`、測試 `qa`、審查 `review`、整合 `integration`（`wf/org/README.md`「部門表」）。
- **只有 `main` 是 eca，部門全是 agent-fsm**，使用者 2026-11-23 定的（同檔「agent 的形態」）。腦：design 用 `astra`，dev、qa、integration 用 `sol`，review 用 `sol` 加 `reasoning_effort: high`（各定義的 `llm.json`）。模型在部門表上標「僅供參考」。
- **常駐**：五個部門都掛在子 daemon `mine_arena` 上、`auto_restart` 開著（`wf/aos/README.md`「目前狀態」）；子 daemon 掛在根 `~/aos-home/.stack` 底下，照範本 `daemon-sub` 做的（`wf/aos/defs/daemon/README.md`）。
- **下屬**：部門可以自己開下屬（使用者 11-23 同意）。現有兩份下屬定義：`qa-triage`（只有 read、glob、grep，用完就收）、`dev-items`（常駐、沒有 shell）。

## 怎麼切

照生產線切：`使用者 → main → design → main → dev → review → qa → integration → main`（`wf/org/README.md`「標準流程」）。三條旁路：小修正省掉 design；只改文件的批次免 review、qa；aos 工具批次要 review 加作者實跑、不經 qa。

每個部門獨佔一樣東西：design 是產品文件唯一的寫手，qa 獨佔試玩與瀏覽器測試，integration 是唯一的 git 提交口，review 只提意見不改程式。

## 角色卡

`wf/org/<部門>/README.md`，1.5～3.5 KB，固定四段：

1. **職責**：負責、不負責、Done when。
2. **讀寫範圍**：可以寫、唯讀、資產庫、暫存。
3. **交接**：一張表「收到誰的什麼信｜要做什麼｜做完回給誰、信裡要有什麼」。
4. **模型**：參考設定、同時可以開幾個（附理由，例「提交口只能有一個」）。

入口的 Done when 就是「新部門四段都要填、部門表加一列」。

## 信件與交接

- 用 aos 信箱。接了請求一定回 `DONE`、`BLOCKED`、`NEEDS-USER`、`FAILED` 其中一種（`wf/org/README.md`）。
- `wf/org/letters.md`（2.2 KB）：開工信六欄（範圍和排他權、基準、驗收分工、資源規矩、預期的並行變動、Done when）；做工具時多一張故障矩陣；回信要短、細節存檔附路徑、`in_reply_to` 一次填對、環境擋住回 `BLOCKED` 不回 `FAILED`、沒跑的／不能跑的／不適用的分開寫；長工作每個階段交界讀一次信。
- 部門的進度與待決事項寫在信裡給 `main`；`SESSION-LOG`、`WAIT_USER` 只有 `main` 寫。

## 定義、地盤、資產

- **定義跟分工分開放**：定義在 `wf/aos/defs/<部門>/`，分工在 `wf/org/`（`wf/aos/README.md`）。定義是用 `agent_def` 從 `start-api/agents/ann` 複製的精簡型，`fsm.json` 動態連結 `$AOS_HOME/templates/agent-fsm/` 的四支程式（`wf/aos/defs/dev/README.md`、`fsm.json`）。
- **定義指向角色卡、不重抄**：`system.txt` 約 2 KB，寫「開工先讀 AGENTS.md、wf/org/README.md、你的角色卡；衝突時照角色卡」，加信件、git、語言的規矩（`wf/aos/defs/dev/system.txt`）。五份幾乎一樣，只差部門名與一兩條禁令。
- **暫存在 repo 外**：`/tmp/aos/arena_cheater/<部門>/`；要留的搬回 `wf/`。
- **資產**：`wf/org/<部門>/assets/`。design 有規格、計畫、需求清單（json）、可調預設索引；dev 有模組責任制提案 `ownership.md`；integration 有 `release-checklist.md`；review 有 `review-checklist.md`（同一類問題出現第二次就收進清單）。
- **改進紀錄**：`wf/org/<部門>/improvements.md`，一行一項「觀察 → 提案 → 狀態」；只從做過兩次以上的事裡找題目、每次空閒最多做一項（`wf/org/README.md`「空閒時改進自己」）。design、integration、qa、review 四個有，dev 沒有。
- **留言板 v0**：`/tmp/aos/arena_cheater/board/`，`notice.md` 只有 main 寫、`wall.md` 大家寫，試用中。
- **工具**：固定流程做成 aos 工具（`wf/aos/tools/arena_verify`、`arena_e2e`），要判斷才開 agent。

## 踩到的坑

出處：`wf/notes/investigations/org-retro-1/README.md`、`org-retro-2/README.md`、`org-retro-2/review.md`、`aos-feedback.md`。

1. **限制都只靠文字**：寫入範圍、不能 commit、只有 qa 能試玩，shell、`run_python`、`self_tools` 都繞得過；只拿掉某支工具沒用。
2. **開工信漏寫規矩就卡住**，回信太長重點被埋掉；所以才有 `letters.md`。
3. **做工具時 review 審了三次**：第一版沒涵蓋取消、啟動、清理失敗；所以開工信加故障矩陣。
4. **取消信晚到**：qa 中途沒讀信，整件做完才看到。
5. **規則沒寫到就停下**：integration 因此卡了四次；加了「低風險就照判斷做、回信附理由」之後沒再卡。
6. **`limits.mem_mb` 讓 Node 壞掉**（限的是位址空間）；改用工具裡的 systemd scope。
7. **資源要分兩層**：一次幾件（flock，只是約定）與一件用多少（scope，硬的）。
8. **agent-fsm 看不到圖**：視覺驗收只能交回 main。
9. **使用者要它們別一直寄信給 eca-aos**：意見先累積在 `aos-feedback.md`，等使用者說有空再寄。
