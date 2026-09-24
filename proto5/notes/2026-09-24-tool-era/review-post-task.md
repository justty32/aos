← [工具大開發時代](README.md)

# 審查任務書：第一波隊 2「郵差」的實作（唯讀）

你是唯讀審查者。**不要改任何檔、不要跑模型、不要開 daemon／kernel、不要碰 LM Studio／ollama。** 可以讀檔、可以跑單元測試（`cd proto5/lib && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s test -p 'test_team_*.py'`；`test_team_post_live.py` 會開真 daemon，可略過）。用繁體中文、白話回答。

## 要審的（這一隊新增或改的）

- `proto5/tools/team/`：`team_say` 工具（模型寄信，只寫自己的 `team/outbox/<名>/`）；`_common.py` 是 base 的逐位元組副本。
- `proto5/lib/aos_team_post.py`：郵差兼書記（kernel 反覆工作）：投遞、退件、任務單後續動作、驗收工作提交與收回、看停滯與期限、書記改 `SESSION-LOG.md`／`WAIT_USER.md`、`aos-team mail`／`post`、kernel 登記。
- `proto5/lib/aos_team_verify.py`：固定檢查器驗收員（`aos-team verify`）。
- `proto5/lib/aos_team_beat.py`：心跳、`routine` 申請處理函式、`aos-team routine`／`beat`。
- `proto5/lib/aos_team_requests.py`：只加了一行 `'routine'`。
- 規範：`proto5/spec/team/post.md`、`verify.md`、`beat.md`。
- 測試：`proto5/lib/test/test_team_{post,post_crash,post_live,beat,say,verify}.py`、`_team_util.py`。

## 對照（請實際去讀）

- 共用契約（第 1 隊，已在 main）：`proto5/spec/team/`（README、layout、mail、tasks、ask、roster、templates、cli）、`proto5/lib/aos_team_format.py`、`aos_team_task.py`（狀態機，郵差不自己寫狀態機）、`aos_team_ask.py`、`aos_team_cli.py`。
- 工具規格與驗收：`proto5/notes/2026-09-24-tool-era/catalog.md` 的 T-say、T-post、T-verify、T-beat 與〈共同規則〉；`plan.md`〈各隊驗收〉隊 2 那 8 條。
- agent 收件規則：`proto5/spec/agent/state.md` §4.1、§4.4；`proto5/spec/aos-agent/idle.md`；`proto5/lib/aos_agent_say.py` 的 `drop_new`。
- kernel：`proto5/spec/kernel/syscall.md`（`add --once`、ack）、`proto5/tutorials/02-kernel-jobs.md`。
- 權限牆：`proto5/spec/agent/access.md`、`proto5/spec/aos-exec/aos-jail.md`、`proto5/tools/README.md`。

## 請回答

1. **重複投遞與漏動作**：郵差「驗 → on_letter → 投 → 紀錄 → 搬 → 做動作」這一串，崩在任何一步（尤其投進 input 之後、寫紀錄之前，且收件人在重跑前已把信收走或停在 intake）重跑會不會重投、漏投、漏做或多做一件後續動作？郵差自己生的信（id＝`<紀錄>.e<k>`）、動作清單長出新動作（`open_review`／`step` 回的）時 id 會不會對不上？`open/` 標記與紀錄的先後有沒有洞？
2. **驗收工作**：`verify` 動作提交一次性工作（kernel `add --once` 或另開行程），之後收 `result.json`、ack 回音；會不會重交、漏收、卡住（回音先到／結果先到、kernel 拒收、行程死掉、逾時）？舊 rev／attempt 的結果會不會套到新的一次？
3. **任務單**：郵差有沒有繞過 `aos_team_task` 自己改單子？`letter_delivered`／`letter_picked_up` 叫的時機對不對（收件人收走的判斷：`input/mail-<id>.json` 不在）？審查子單、ask／answer、cancel、reassign 經郵差走得通嗎？
4. **看停滯**：「只報一次」「在等別人的不報」「健康不是 ok」「收單後沒進展」的判斷有沒有會誤報或永遠不報的情況？最後進展的來源夠不夠？
5. **書記**：改 `SESSION-LOG.md`／`WAIT_USER.md` 的方式會不會吃掉人寫的東西、在 workflows 導入的檔上寫壞格式、或跟 wf-lint 衝突？
6. **心跳**：到期計算（every／daily／once、時區、漏跑只補一次）、在途不重派、DONE 才更新、失敗重派、模型提的列要人批准，有沒有算錯或能繞過的？心跳用 human 名義寄 handoff 申請合不合理？`routines.json` 只有郵差寫、`beat.json` 只有心跳寫，有沒有第二個寫的人？
7. **team_say 與邊界**：名冊外收件人、非白名單 STATUS 是否都擋；寫檔是否原子、不覆蓋；關牢後（`/opt/tool/config.json`、`/work/outbox`）能不能跑；有沒有讓模型選寫檔路徑的地方？郵差身分認定（看檔在哪個 outbox）有沒有能冒名的洞（例如在自己的 outbox 放別人 id 的檔）？
8. **驗收員**：路徑關在專案裡的檢查（`..`、絕對路徑、符號連結）夠不夠；`table_filled` 的 md／csv／json 解析有沒有明顯錯；檢查器不執行專案裡的檔這條有沒有破。
9. **資源與順序**：郵差每秒一輪的成本（實測閒著一輪約 0.037 cpu 秒）、每輪讀哪些檔；outbox 很多檔、紀錄很多時會不會變慢到不能用？
10. **跟共用格式不合的地方**：有沒有違反 `spec/team/` 的地方（格式、誰寫哪個檔、退出碼、`aos-team` 慣例）？

## 格式

分三段：**必修**（不改會做錯、會重投／漏做、會卡死、或違反共用契約的；每條：哪個檔哪個函式、怎麼觸發、建議改法）、**建議**、**確認沒問題的**（簡短）。必修按嚴重程度排，編號 M1、M2…；建議 S1、S2…。
