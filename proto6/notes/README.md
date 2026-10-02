# proto6 設計筆記與交接索引

← [proto6](../README.md)

這裡放 proto6 的設計筆記，分三塊：現在照什麼做、背景與實測、歷史紀錄。**要實作或查欄位，以 [spec](../spec/README.md) 加 [程式與測試](../src/py/README.md) 為準**（第二十七批，2026-10-02：程式就是正本）。

## 現行方向

- [spec 入口](../spec/README.md)：唯一事實；行為與格式的正本是 `proto6/src/py` 的程式、測試與 schema。
- [裁定紀錄](verdicts/README.md)：使用者逐批裁定，**後批優先**。最新的在 [verdicts 11 篇末 10-01、10-02 各批](verdicts/11-tick-as-unit.md)（到第二十七批）；09-29 那天的十七批見 [總表](2026-09-29-verdicts.md)。
- [10-01：最核心的 aos-daemon](2026-10-01-daemon-core-sketch.md)（已裁定）：現行 daemon「定期叫 `aos-exec`、其餘做成模組」的由來；細部 plan 見 [m3](../plan/m3-daemon-core.md)。
- [10-01：tick 系統級任務總整理](2026-10-01-tick-system-tasks.md)：系統級任務全暫緩後，留給使用者慢慢想怎麼改用 hooks 的清單（不是裁定）。
- [帳號模組真 root 操作手冊](2026-10-01-account-manual.md)：等使用者在可丟棄的機器上手動驗。

## 舊方向（歷史，已被取代，僅供對照）

- [第二十批方向](verdicts/11-tick-as-unit.md)（09-30）：tick 核心四件、系統級任務（`kind:"system"`）、tick–daemon 通道是唯一逃生口。系統級任務 10-01 起全搬暫緩區（`aos-as`、`aos-tick-check-task`、`aos-git`、範本、`aos-mq get`／`post`、`aos-clean`），通道被 daemon 控制模組取代。
- [第十九批方向](verdicts/10-tick-minimal-core.md)（09-30）：三層架構（核心、標準配備必須全掛、其他掛載），被第二十批取代。
- [第十八批方向](verdicts/09-special-computing-os.md)（09-30）：aos 是給特殊計算用的 OS、多層多 kernel；數條被第十九批推翻。
- [kernel 樹與註冊式 tick](2026-09-29-kernel-tree.md)（09-29）：node／kernel 樹的設計，舊 spec 依它寫，現已封存在 [archive/spec-2026-10-02/](archive/spec-2026-10-02/README.md)。
- LLM 排程（09-29 第十三、十五批）：LiteLLM 只當可選 endpoint、自己排程分三檔；見 [舊 spec S-301](archive/spec-2026-10-02/scheduling/llm.md)。現行 spec 與程式沒有 LLM 排程。
- systemd 與 cgroup（第十四、十五、十九批）：初版不用 systemd；cgroup 現行由 daemon 收屍模組（[B-644](../spec/daemon/cgroup.md)）處理。
- [09-30 待議：daemon 職責與多 daemon](2026-09-30-daemon-split-and-multi-daemon.md)：已裁定，後被 10-01 最核心 daemon 取代。
- 09-30 審稿（Fable 與 astra 兩輪、77 條）：批次已結束，封存在 [archive/reviews-2026-09-30/](archive/reviews-2026-09-30/README.md)。

軟性設計原則：[兩次 tick 之間的環境穩定性](between-ticks-configuration.md)。由原先硬保證改為設計指導，不屬於 spec，也不設強制驗收。

## 背景與探針

- 三大概念（09-28，歷史，現行以 spec 為準）：[三大概念：基底、agent、任務與排程](concepts.md)，逐塊見 [基底](base.md) → [agent](agent.md) → [任務與排程](scheduling.md)。是當時接受的責任分區，不代表三個程序或已完成實作；09-29 起改成 node／kernel 樹，用語以 spec 為準。
- 平台：使用者要求原生 Linux 與 WSL 都要能跑；公司 WSL 的對照查證見 [WSL 機器查證](2026-09-29-wsl-machine-check.md)。
- 探針：局部實測與重跑方式見[探針入口](probes/README.md)；09-29 另量了 `systemd-run` 開短命程序的延遲，見 [systemd-run 延遲](probes/systemd-run-latency.md)。

拍板用的比較材料（決定已下，見裁定紀錄；原檔已封存，這裡是縮短版）：

- [依賴盤點](2026-09-29-dependency-review.md)：導出第十四批裁定；留決定、必要依賴現況、暗中依賴與砍依賴的代價。
- [LLM 排程器選項](2026-09-29-llm-scheduler-options.md)：導出第十三批裁定；留三檔決定、估時與自製 vs LiteLLM 比較。
- systemd 拆分（daemon 與 root helper 逐條標哪些交給 systemd）已被第十四批「初版不用 systemd」取代，已封存。

09-28 的方向摘要（歷史，現行以 spec 為準）：先放下正式員工／工具的組織分類，以一 agent 一 Linux 使用者、cgroup v2 管執行資源、project quota 管自有容量（09-29 裁定：可選、只記帳）。工具沿用委託 agent 的權限與資源，不需要逐工具 bwrap；保護宿主的整套 aos 外牆仍保留，具體部署未定。CPU worker 取消是後續方向，尚未實作；前文的固定 worker 構想保留為演進脈絡，不能同時當成最新要求。

規模目標：一台家用機保存 10,000 個 agent，每小時活躍不到 100 個，共用十幾個雲端 LLM endpoint；這不是同時併發上限，也不是已完成的規模驗證。idle 不常駐、不頻繁 tick，事件或到期才喚醒。Docker／FUSE 不作基本前提，FUSE 延後。

## 歷史

過時或已被取代的筆記都在 [archive/](archive/README.md)，不刪、不維護，每檔第一行寫了為什麼封存、現行看哪：

- 09-28 從 proto5 收錄的快照（六份筆記、萬 agent 計畫、兩份外牆調查），連同 15 份來源對照表：import-2026-09-28（已封存檔 README.md，索引見 [archive/README.md](archive/README.md)）。探針沒搬，仍在 [probes/](probes/README.md)。
- 09-28 的三份審查（notes 審查、spec 遺漏、spec 冗餘，都針對重寫前的舊 spec）、spec 重寫處置表、systemd 拆分、兩份比較材料的完整原檔：見 [封存索引](archive/README.md)。
