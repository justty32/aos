# proto6 設計筆記與交接索引

← [proto6](../README.md)

這裡放 proto6 的設計筆記，分三塊：現在照什麼做、背景與實測、歷史紀錄。要實作或查欄位，以 spec 為準。

## 現行方向

- [spec 規格草案](../spec/README.md)：欄位、合法狀態、提交與失敗恢復、驗收，現行以它為準。
- [裁定紀錄](2026-09-29-verdicts.md)：09-29 使用者分十四批逐條裁定，**以它為準、後批優先**；分冊與每批摘要見 [verdicts/](verdicts/README.md)。
- [kernel 樹與註冊式 tick](2026-09-29-kernel-tree.md)：09-29 架構方向改回 kernel 樹＋註冊式 tick；spec 已依此重寫，原先「單一控制寫入者、總帳本」的寫法已拿掉。
- LLM 排程：09-29 晚使用者裁定 LiteLLM 不進標準、只當可選 endpoint；aos 自己的排程分三檔（不管／交給 endpoint／自己排，預設自己排），見裁定第十三批與 [spec S-301](../spec/scheduling/llm.md)。
- systemd：第十四批裁定**初版不用 systemd**；cgroup v2 是必要依賴，quota 可選。

軟性設計原則：[兩次 tick 之間的環境穩定性](between-ticks-configuration.md)。由原先硬保證改為設計指導，不屬於 spec，也不設強制驗收。

## 背景與探針

- 三大概念（09-28）：[三大概念：基底、agent、任務與排程](concepts.md)，逐塊見 [基底](base.md) → [agent](agent.md) → [任務與排程](scheduling.md)。是當時接受的責任分區，不代表三個程序或已完成實作；09-29 起改成 node／kernel 樹，用語以 spec 為準。
- 平台：使用者要求原生 Linux 與 WSL 都要能跑；公司 WSL 的對照查證見 [WSL 機器查證](2026-09-29-wsl-machine-check.md)。
- 探針：局部實測與重跑方式見[探針入口](probes/README.md)；09-29 另量了 `systemd-run` 開短命程序的延遲，見 [systemd-run 延遲](probes/systemd-run-latency.md)。

拍板用的比較材料（決定已下，見裁定紀錄）：

- [依賴盤點](2026-09-29-dependency-review.md)：導出第十四批裁定。
- [LLM 排程器選項](2026-09-29-llm-scheduler-options.md)：自製排程器要做哪些事、估時與利弊，導出第十三批裁定。
- [systemd 拆分](2026-09-29-systemd-split.md)：daemon 與 root helper 逐條標哪些交給 systemd，附部署形態安全比較；已被第十四批「初版不用 systemd」取代，留作以後可選增強的參考。

09-28 的方向摘要：先放下正式員工／工具的組織分類，以一 agent 一 Linux 使用者、cgroup v2 管執行資源、project quota 管自有容量（09-29 裁定：可選、只記帳）。工具沿用委託 agent 的權限與資源，不需要逐工具 bwrap；保護宿主的整套 aos 外牆仍保留，具體部署未定。CPU worker 取消是後續方向，尚未實作；前文的固定 worker 構想保留為演進脈絡，不能同時當成最新要求。

規模目標：一台家用機保存 10,000 個 agent，每小時活躍不到 100 個，共用十幾個雲端 LLM endpoint；這不是同時併發上限，也不是已完成的規模驗證。idle 不常駐、不頻繁 tick，事件或到期才喚醒。Docker／FUSE 不作基本前提，FUSE 延後。

## 歷史

- 審查紀錄（09-28，針對重寫前的舊 spec，不代表建議已採納）：[冗餘審查](spec-redundancy-review.md)與[遺漏審查](spec-gaps-review.md)區分編輯修正、可選精簡與尚需裁定的政策；四隊獨立審查 notes 全部內容與收錄忠實度的結果見 [notes 審查](notes-review.md)，其「待裁定」由裁定紀錄第一批回答。
- spec 重寫處置表：[依 kernel 樹重寫 spec 的逐條處置](plan/spec-rewrite-kernel-tree.md)，一次性用完。
- 09-28 從 proto5 收錄的快照：依使用者要求，完整收錄本輪 proto5 討論、兩份外牆調查及探針，作為 proto6 的起點。原位置保留歷史，不刪除；這裡是標示來源的交接快照，不代表現行 proto5 已變成新架構。閱讀順序是[最新討論紀錄](2026-09-28-linux-resources-and-task-scheduling.md) → [萬 agent 改動計畫](plan/README.md)；背景見[人的架構閱讀筆記](2026-09-28-human-architecture.md)，隔離選型在[調查入口](investigations/README.md)。

### 完整來源對照

以下 15 份來源完整收錄。Markdown 僅增加快照說明、重算連結與更新探針執行路徑；兩支探針程式保持位元組相同。已收錄資料互連 proto6，現行程式、spec、舊 benchmark 仍指向 proto5；外部來源與當時的行號、實測數字均保留。後續演進以 proto6 為入口，不把歷史提案自動升格成規格。

| proto6 收錄 | 歷史來源 |
|---|---|
| [架構背景](2026-09-28-human-architecture.md) | [proto5 human-architecture](../../proto5/notes/2026-09-28-human-architecture.md) |
| [員工身分與方向演進](2026-09-28-employee-identity.md) | [proto5 employee-identity](../../proto5/notes/2026-09-28-employee-identity.md) |
| [root daemon 草案](2026-09-28-host-root-design.md) | [proto5 host-root-design](../../proto5/notes/2026-09-28-host-root-design.md) |
| [Linux 實作成本](2026-09-28-linux-employee-implementation.md) | [proto5 linux-employee-implementation](../../proto5/notes/2026-09-28-linux-employee-implementation.md) |
| [隔離實測報告](2026-09-28-linux-isolation-probes.md) | [proto5 linux-isolation-probes](../../proto5/notes/2026-09-28-linux-isolation-probes.md) |
| [資源與任務排程](2026-09-28-linux-resources-and-task-scheduling.md) | [proto5 linux-resources-and-task-scheduling](../../proto5/notes/2026-09-28-linux-resources-and-task-scheduling.md) |
| [萬 agent 計畫入口](plan/README.md) | [proto5 計畫 README](../../proto5/notes/2026-09-28-ten-thousand-agents/README.md) |
| [執行與排程](plan/runtime.md) | [proto5 runtime](../../proto5/notes/2026-09-28-ten-thousand-agents/runtime.md) |
| [Linux 與儲存](plan/linux-and-storage.md) | [proto5 linux-and-storage](../../proto5/notes/2026-09-28-ten-thousand-agents/linux-and-storage.md) |
| [LLM 與驗收](plan/llm-and-validation.md) | [proto5 llm-and-validation](../../proto5/notes/2026-09-28-ten-thousand-agents/llm-and-validation.md) |
| [探針重跑入口](probes/README.md) | [proto5 探針 README](../../proto5/notes/2026-09-28-linux-probes/README.md) |
| [探針 runner](probes/run.py) | [proto5 run.py](../../proto5/notes/2026-09-28-linux-probes/run.py) |
| [Landlock canary](probes/landlock-canary.c) | [proto5 landlock-canary.c](../../proto5/notes/2026-09-28-linux-probes/landlock-canary.c) |
| [宿主 root 第二道牆](investigations/proto5-host-root-second-wall.md) | [wf 第二道牆調查](../../wf/workflows/investigations/proto5-host-root-second-wall.md) |
| [Linux 外牆可行性](investigations/proto5-linux-wall-feasibility.md) | [wf Linux 外牆調查](../../wf/workflows/investigations/proto5-linux-wall-feasibility.md) |
