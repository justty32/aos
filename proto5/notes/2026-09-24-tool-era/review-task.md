← [工具大開發時代](README.md)

# 審查任務書：工具大開發時代規劃（唯讀）

你是唯讀審查者。**不要改任何檔、不要跑模型、不要開 daemon／kernel。** 用繁體中文、白話回答。

## 要審的

`proto5/notes/2026-09-24-tool-era/` 的 `README.md`、`axes.md`、`workflows-as-team.md`、`catalog.md`、`plan.md`。
這是「工具大開發時代」的規劃：把 `~/repo/workflows`（唯讀；一套給 AI agent 照做的 Markdown 工作流模板）化成 aos 的 agent 團隊，並列出要做的工具、分三波開發。
使用者給的評判標準：LLM 參與越少越好、工具越穩越好、資源越少越好、越快越好、人越容易懂越好（出自 `~/repo/ai_core`，唯讀）。

## 對照來源（請實際去讀）

- aos 現況：`proto5/README.md`、`proto5/tools/README.md`＋`proto5/tools/base/`、`proto5/spec/agent/`（info.md §3.3 工具檔、state.md、layout.md）、`proto5/spec/aos-agent/`（cli-talk.md 的 say、cli-listen.md、tools.md、tick.md、send.md）、`proto5/tutorials/02-kernel-jobs.md`、`05-many-agents.md`、`proto5/notes/2026-09-24-agent-access/README.md`（權限牆提案）。
- workflows：`~/repo/workflows/README.md`、`IMPORT.md`、`template/`、`flavors/multi-agent/workflows/`（inbox、team-model、dispatch、resources）、`flavors/heartbeat/workflows/`、`tools/`。
- ai_core：`~/repo/ai_core/workflows/spec/execution_forms/s0-axes.md`、`workflows/common/conventions.md`、`workflows/roadmap/s3-endgame-governance.md`。
- proto2 遺產（舊原型的工具包教訓）：`proto2/notes/2026-09-07-lessons.md`、`proto2/notes/play/README.md`、`proto4/notes/agent/legacy-harvest.md`。

## 請回答

1. **對 workflows 的理解對不對**：`workflows-as-team.md` §1 的描述、§2 的機械／判斷劃分、§2.4 驗收例子（導入 heartbeat 包）的 Done when 是否跟 `IMPORT.md` 一致、例子是否真的夠小又能跑。
2. **團隊設計**：三個 agent＋四個機械員合不合理；交流（outbox＋郵差、不給等回信工具、書記替沒回終局狀態的人報 BLOCKED）有沒有漏洞（重複投遞、順序、agent 在 act 中途收到信、郵差崩潰、人跟郵差同時投同一個 `input/`）。對照 aos 的 `input` 收法（agent state.md §4.1）與 `say` 投檔規則。
3. **清單漏了什麼**：使用者點名的（記憶管理、prompt history `/context`／`/compact`、agent 交流、特定檔案修改 json／指示詞／access.json、團隊與管理、agent 創造與修改、造工具的工具、讀 python 檔納入工具）有沒有沒涵蓋到的；workflows 團隊要跑起來還缺哪支工具。
4. **哪些工具其實不該有 LLM**（或反過來：標「不叫模型」但實際做不到）。特別看 T-route（門房）、T-compact、T-wrap-py、T-verify 的 `judge`、T-crystal。
5. **邊界**：標「第一波沒牆也安全」的是否真的安全（例如 `team_say`、`handoff`、`json_edit`、`wf_init`、`verify` 的 `cmd_ok`、`compact` 碰記憶與 tick 鎖）；有沒有該放第二波的。
6. **分波順序與並行**：第一波 4 隊的領地會不會撞（`aos_agent_cli.py`、`aos_agent_init.py`、talk 分支）、合併順序、前提（talk 合進 main、牆那隊合進 main）對不對；驗收過關線合不合理、量得到嗎（`aos-team score` 的資料來源真的存在嗎）。
7. **六軸**：`axes.md` 對九軸原文的引用是否正確；「找不到六軸」的說法是否站得住；評分門檻有沒有明顯不合理或量不到的。

## 格式

分三段：**必修**（不改會做錯或做不出來的，每條：哪個檔哪一段、問題、建議改法）、**建議**、**確認沒問題的**（簡短）。必修按嚴重程度排，編號 M1、M2…；建議 S1、S2…。
