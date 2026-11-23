樣本二 `paper_readings` 的組織怎麼寫的：一隻常駐的 main 加按需才開的撰稿與查核，今天下午剛規劃、正在試第一篇（11-23 唯讀讀它的文件與定義，沒碰它的樹）。

# 樣本二：paper_readings（按需角色）

← [入口](README.md)｜[總結與對照](01-四個樣本的總結.md)

路徑都在 `/mnt/c/code/mine/paper_readings/` 底下。今天下午那隻 fable 的產物在 `wf/planning/specs/mine-paper-org.md`（20.7 KB，方案）與 `wf/planning/plans/mine-paper-org-pilot.md`（10.5 KB，試行計畫）；`wf/org/` 是 main 從方案摘出來的最小版。

## 規模與身體

- **一隻常駐、其餘按需**：`main` 常駐；`drafter`（撰稿）、`checker`（查核）有工作才開、一批做完就收；`synth`（綜述）有主題才開（`wf/org/roles.md`、方案第 3 節）。
- **main 是 agent-fsm**，腦 `astra`、`reasoning_effort` high（方案第 1 節，註明是 main 自查、規劃者沒重查）；方案明寫「不預設改成 eca」（第 8 節）。
- drafter 用 `sol` high、checker 用 `astra` high（`wf/org/defs/*/llm.json`）；查核刻意用不同的 instance，不看撰稿者的自述。
- 方案比過三種：按需角色、常駐部門、混合（現在按需、達門檻才升常駐），建議混合。理由：開新批次每次都要使用者授權，工作是一陣一陣的；主要風險是事實寫錯，不是協調不過來（方案第 2 節）。

## 怎麼切

照「一條逐篇閉環的管線」切，但角色只有三個：main 管授權、抓文、驗收、整合、提交；drafter 只寫指定的檔；checker 只寫一份查核報告。**共享檔只有 main 一個寫手**（索引、候選池、日誌、HTML、git 提交；方案第 4 節）。

## 角色卡

全部在一個檔 `wf/org/roles.md`（2 KB），每個角色兩段散文：負責什麼與交付什麼、不做什麼。沒有分四段，但內容對得上（職責、不負責、可寫範圍、交付）。開頭寫明「這是派工參考，不是現役名冊或模型配置；每次任務的可寫檔案以交接書為準」。

## 信件與交接

- aos 成員走 aos 信箱，舊的 codex 線走檔案信箱 `wf/inbox/`；**一件工作只走一個通道**，交接書寫明走哪個（`wf/org/README.md`「派工前後」、方案第 10 節）。
- **每件工作一份交接書**：`wf/org/pilot-agar/drafter.md`、`checker.md`，各約 1.2 KB：唯一可寫的檔（逐檔列名，不給整個目錄）、來源與雜湊（`source.json`）、模型、網路與下屬權限為零、固定四條驗收、回 `DONE` 要附什麼。
- 開工信欄位改寫自 arena 的 `letters.md`（方案第 5 節）；**信不是授權來源**。
- **六道閘門** G0 授權、G1 來源、G2 機械、G3 事實、G4 整合、G5 提交（G6 發布另外授權），每道寫誰把關、證據是什麼；G3 至多兩輪，還有未決就停下回報使用者（方案第 6 節）。
- **擴編門檻**寫成可調的數字（方案第 9 節）。

## 定義、地盤、資產

- **定義放在 org 裡**：`wf/org/defs/checker/`、`defs/drafter/`，是 agent-fsm 範本的**整份抄本**（連 `wait.py` 40 KB 這些格程式都抄進來，`fsm.json` 跑夾裡自己那份），不動態連結。
- 工具砍到只剩看的、信箱、`write`、`edit`（`defs/checker/tools.json`）；沒有 shell、網路、刪除、改自己的工具、下屬。`wf/org/deployment.md` 寫明「這是工具縮減及行為契約，不是 OS 級檔案沙箱」。
- `system.txt` 約 1.2 KB 一整段：只做 main 信件指定的事、沒收到逐檔領地不得寫檔、先讀 `wf/org/roles.md`、回信規矩、不直接聯絡 eca-aos。
- **沒有地盤、沒有暫存夾**：工作筆記留在回信裡（`pilot-agar/drafter.md`）。
- **資產**：沒有 `assets/`；產物就是 repo 的內容（摘要、譯文、查核報告 `wf/qa/reports/`）。`wf/org/deployment.md` 是部署與試行紀錄。
- **改進紀錄**：沒有 `improvements.md`；對 aos 的意見累積在 `wf/notes/aos-feedback.md`，使用者說對方有空才寄。

## 現況（我讀的時候，11-23 16 點前後）

`wf/org/` 整夾還沒 commit（`git status` 是 `??`）。試行篇目的摘要與譯文已經在工作樹裡；查核報告 `wf/qa/reports/2026-11-23-agar-audit.md` 還沒看到。

## 踩到的坑與特別小心的地方

1. **跟舊編制並存**：舊名冊還列著 `dispatcher` 是現役；「不能以空信箱推論所有舊線已停止」（`wf/org/README.md`「與舊編制並存」）。
2. **模型沒定就不啟動**：`llm.json` 先留空，「避免默默採用環境預設」（`wf/org/deployment.md`）。
3. **已知的品質風險**：撰稿生出原文沒有的數字、下屬回報不實完成、抓到錯的版本（方案第 1 節）。所以任何角色的完成自述都不算證據。
4. **明說不學 arena 的幾條**：dev／review／瀏覽器 QA 的分工、Node 鎖、「main 必為 eca」、部門自開下屬、空閒自我改進（方案第 1 節）；還有「別人範圍內的變動不必問」那條例外（第 4 節：開工信沒列到的變動一律停下問 main）。
5. 文件裡每一項都標「觀察／建議／待決」，待決有十題 D1～D10（試行計畫「待決事項」）。
