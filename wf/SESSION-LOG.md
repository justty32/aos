# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡——過程細節交給 git log（若有「已落地功能目錄」則濃縮一句進去）。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> **膨脹就拆**：本檔若過大，就在 repo 頂層新立 **`session_logs/`** 資料夾，按工作流／類別**拆檔 + 一個 index 導航**（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

本檔同時 ① 連到各工作流自己的 session-log（若該工作流已長出自己的），② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態 + 指向細節的連結**（設計決策/修了什麼落到該工作流的文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即整條刪除。

## 最新進度

- 10-01（公司）：proto6 POC 依「默認一切正常」大幅簡化，裁定全在 [verdicts 11 篇末 10-01 各批](../proto6/notes/verdicts/11-tick-as-unit.md)。**做完**：tick 核心（`aos-tick [<資料夾>]`、tasks.json 頂層預設／modules 整個展開／_metainfo 可省；頂層鍵 `hooks.after_all`（B-635）與 `AOS_HOOK_POINT/INDEX/ID`；紀錄只記非 0、拆成 `tick/current/{record,ran,task-exits,hook-exits}.json` 用 $ref）；daemon 核心＋控制模組（aos-ctl）＋重讀設定（B-642，SIGHUP，頂層改了 stdout 警告）＋記住狀態（B-643，`modules.state` 用 $ref）；aos-needs→`aos-tick-check-task`（只改 spec）；aos-publish、aos-config-add 搬暫緩區；daemon 收屍 cgroup 模組也做完（B-644，C1～C4 照建議；順帶 exec_out/err_path 改了不套用＋警告；10-01 晚在家收完 spec，[第十二批](../proto6/notes/verdicts/11-tick-as-unit.md#2026-10-01-第十二批cgroup-與帳號)）；daemon 訊息模組也做完：`aos-mq send`／`take`（B-645，M1～M4 照建議，10-01 晚在家做；第十四批改成 `take` 只取自己的信箱、`--from` 篩寄件人；第十五批：daemon 不核對取信的人、加 `peek`、`--from` 收多個／不接＝null、跨 daemon 不管）；daemon 帳號模組也做完：`modules.account`（B-646，第十三批 A1～A7 照建議、白名單／黑名單；10-01 晚在家用 unshare 假 root 驗，真 root 待手動驗，見 [plan m3m 模組五](../proto6/plan/m3m-daemon-modules.md#做完了沒)）。五個 daemon 模組都做完了。擋板檔第十六批改成只看存不存在、直接結束、stderr 不印、hooks 不跑；停格檔改名 `tick/tasks-blocked`（每項之前看、只看存不存在、stderr 不印、after_all 照跑、整格最後 tick 刪，紀錄 `blocked_before`）；`aos-tick-check-task` 搬暫緩區。**擱置待使用者想**：git（[第二段 plan](../proto6/plan/m2-system-tasks.md) 待問 1～12）、停格檔（只記未來方向）、node（使用者預感 node 概念會消失；tick 與 daemon 都不做 node 模組）、系統級任務怎麼搬到 hooks（[清單](../proto6/notes/2026-10-01-tick-system-tasks.md)）。daemon 模組 plan：[m3m](../proto6/plan/m3m-daemon-modules.md)。
- 09-30（晚）：proto6 開始實作，分工改成「Python POC 由 AI 團隊寫、C++11 放最後」（[roadmap 現況](workflows/roadmap.md)）；成熟元件從 proto5 原樣複製進 `proto6/src/py`。下一件：`proto6/plan/` 依新分工改（另一隊在 worktree 做 src 與 plan）。
- 09-25（晚上，整理鏈收尾）：**main**（WAIT_USER 拆檔→wf 六區拆檔→sandbox 封存→brief 補篇→wf／proto5 兩輪 tidy→proto5/lib 19 支拆母模組＋子模組共 145 支）；astra 唯讀審 lib 拆檔必修 0、建議 4 全採納；lint 前後：wf oversize 61→39、proto5 broken 299→0；全套測試 **2874 條全綠**；研發部接著做第 74、75 題（經理人裁決：品質×成功率×審查係數、快只比成功張數相同的；重算五家三輪名次與撥款不變），astra 唯讀審查必修 3、建議 5 已修（重疊單一對一配、審查紀錄照時間排、0 秒不當沒秒數；重跑三輪數字不變），全套 **2891 條綠**。待董事：評分 [brief/2026-09-25.md](../brief/2026-09-25.md)、WAIT_USER 40～73（74、75 已由經理人裁決）。下一輪：`lessons.md`／`catalog.md` 先改 lib 再拆、`agent_access`／`agent_talk`／`kernel_check`／`kernel_ledger` 沒拆、wf 還有超標檔、09-24 notes 三份一組的收攏。[→](session_logs/2026-09/2026-09-25.md#2026-09-25)
- 09-24：**已推 main**：重架構收線→tool-era 三波（第一波 T1/T3/L2/S/T4/T2/K2、P 隊 one-boot、T5 收尾、第二波 A/B/C 造工具＋牆接線＋申請類）全落地，試玩多輪過；A.21～A.39 逐條裁決／代裁。測試 94 檔 2605 條全綠。[→](session_logs/2026-09/2026-09-24.md#2026-09-24)
- 09-22：09-21 ④⑤ 仍在（① backlog 已於 09-24 清光） [→](session_logs/2026-09/2026-09-22.md#2026-09-22)
- 09-21：④ aos-inst 兩題 ⑤ thinking/ 草案 ④ WSL 沒 lms／jq [→](session_logs/2026-09/2026-09-21.md#2026-09-21)
- 09-13：① 試玩 r1 修 ② LLM cpu 下一段 ③ 提醒 compact [→](session_logs/2026-09/2026-09-13.md#2026-09-13)
- 09-09：① kernel v1 缺項等使用者 [→](session_logs/2026-09/2026-09-09.md#2026-09-09)
- 09-06～08：預算、dev 模型、qa、push、proto4-2 等 [→](session_logs/2026-09/2026-09-06.md#2026-09-06)
- 09-05：① 裁決單 ③ 升格裁決 ⑨⑪ 互動台 [→](session_logs/2026-09/2026-09-05.md#2026-09-05)
- 08-28：批 header、decode 層 [→](session_logs/2026-08.md#2026-08-28-拷問)

其餘（open 已解／無）與全文索引 → [session_logs/](session_logs/README.md)

## 各工作流 session-log

> 某工作流長出自己的 `session-log.md` 後，在這裡加一列。一開始是空表很正常。

| 工作流 | session-log | open 摘要 |
|--------|-------------|----------|

## 不屬任何工作流的進度

- （無）
