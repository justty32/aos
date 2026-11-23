樣本三 `mecha-srpg` 的組織寫在哪：沒有 `wf/org`、也沒有用 aos，它的組織是上一代的寫法（三層角色、線、交接書、檔案信箱），散在四個檔（11-23 唯讀）。

# 樣本三：mecha-srpg（沒有 org，上一代的「線」）

← [入口](README.md)｜[總結與對照](01-四個樣本的總結.md)

使用者打的是 `mecha_srpg`，實際資料夾是 `/mnt/c/code/mine/mecha-srpg/`，下面的路徑都在它底下。

## 先講結論

- **沒有 `wf/org`**，`wf/` 底下也沒有 `aos/` 夾；在 `wf/`、`AGENTS.md` 裡找「aos」只中兩個不相干的檔。最後一個 commit 是 11-18（`git log`）。
- 它的「誰負責什麼、怎麼交接」寫在四個地方：`wf/workflows/team-model.md`（誰來做）、`wf/workflows/dispatch/`（派線、領地、收線）、`wf/workflows/inbox/`（檔案信箱與名冊）、`wf/workflows/TEMPLATE.handoff.md`（交接書範本）。
- 所以它不是 org 的樣本，是 **org 之前的那一代**：單位是「線」（一件工作一條、做完就收），不是「位子」。但另外三個樣本用到的零件，這裡大半有原型。

## 規模與身體

三層（`wf/workflows/team-model.md` 第一節，使用者 2026-10-27 裁示）：頂層（主 session，只跟使用者溝通、不實作、不逐則讀信）、領導（拆工、派工、驗收、收線）、工人（照交接書做一件事）；另有規劃與美術兩種專門角色。模型按層配。11-05 補了 Claude session 的對照。身體是 Claude Code 或 codex 的原生子 agent 與 `codex exec` 外部線，不是 aos 的 agent。

## 怎麼切

「按明列的目錄／檔案清單切，不按功能切」；同一時間一個路徑只能有一條線持有寫入權（`wf/workflows/dispatch/README.md` 流程第 1 步）。

## 相當於角色卡的東西

- **名冊的一格** `wf/workflows/inbox/ROSTER.md`：狀態、我是誰、團隊、上游、領地、答得出什麼、答不出什麼、怎麼找我。只列現役，收線就刪格。現在只剩 `dispatcher` 一格，裡面的路徑是家機的。
- **領地表** `wf/workflows/dispatch/CLAIMS.md`：現役線各自可寫哪些路徑，加一張「保留給調度者、任何線都不得寫」的表。

## 信件與交接

- **交接書是唯一契約**（`wf/workflows/TEMPLATE.handoff.md`）：先讀什麼、唯一目標、範圍用排除法寫死、件數與容量的上限、必用工具、資源與禁區、交付物寫絕對路徑、固定 N 條驗收、兩種失敗分開處置（測出來是壞的回 `FAILED` 並回滾；測不出來回 `BLOCKED`、保持現狀）、終局回報。
- **狀態**：`REQUEST`、`DONE`、`BLOCKED`、`NEEDS-USER`、`FAILED`、`PROGRESS`；卡住超過 10 分鐘先發 `BLOCKED`（同檔）。信的格式是 `wf/workflows/inbox/TEMPLATE.letter.md`：做了什麼、產出、沒做到或證據不足的、需要決定的事。
- **往上報要重寫標題、帶自己的判斷**；收線「對證據，不對自報」（`dispatch/README.md` 收線 checklist）。
- 原生子 agent 用工具回傳，外部線走檔案信箱 `wf/inbox/`。

## 定義、地盤、資產、改進

- 沒有 agent 定義（不是 aos）。
- 每條線的東西放 `wf/workflows/dispatch/handoffs/<線名>/`，收線就刪、證據寫進收線的 commit 訊息。
- 資產與改進：`dispatch/lessons.md`、`lessons-leading.md`、`lessons-evidence.md`（教訓）、`team-model/grades.md`（模型評等）。
- 獨佔資源：`wf/workflows/resources.md`（鎖用 `mkdir`；這個專案鍵盤、滑鼠、螢幕一律是禁區）。

## 它教的幾件事（教訓檔裡的）

1. 交接書的範圍詞會被線一路放大，所以用排除法寫死。
2. 開了卻沒人盯的線比不開更糟；領導不要開太多。
3. 工人寫不到名冊，由領導代登記。
4. 交付物的路徑要寫絕對路徑，寫相對的會寫到別處。
