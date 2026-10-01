# proto6 設計筆記與交接索引

← [proto6](../README.md)

這裡放 proto6 的設計筆記，分三塊：現在照什麼做、背景與實測、歷史紀錄。要實作或查欄位，以 spec 為準。

## 現行方向

- [spec 規格草案](../spec/README.md)：欄位、合法狀態、提交與失敗恢復、驗收，現行以它為準。
- [裁定紀錄](2026-09-29-verdicts.md)：09-29 使用者分十七批逐條裁定，**以它為準、後批優先**；分冊與每批摘要見 [verdicts/](verdicts/README.md)。
- [第十八批方向](verdicts/09-special-computing-os.md)（09-30，後批優先，數條已被第十九批推翻；spec 已依它改寫）：aos 是給特殊計算用的 OS，多層多 kernel，各 kernel 自訂抽象、資源、隔離，以 Linux 為底。
- [第二十批方向](verdicts/11-tick-as-unit.md)（09-30，**最新方向、後批優先，推翻第十九批標準配備結構**；**spec 正在依它改寫中**）：tick 是 aos 的衡量基準（排程以 tick 為單位、整個體系基於 tick）；tick 核心只有四樣（鎖、照表跑、上下層、每項結束碼紀錄）；git 開格／收尾、收件、投件、發摘要、清理等是掛在任務表上的系統級任務（`kind:"system"`），`aos-cg`、`aos-as`、`aos-needs` 是普通程式；tick–daemon 通道是唯一逃生口；不再有標準配備、全掛、兩級。
- [第十九批方向](verdicts/10-tick-minimal-core.md)（09-30，**標準配備、全掛、兩級等已被第二十批取代**、推翻第十八批數條；spec 已依它改寫，落點見該份文末）：三層架構——tick 核心只有互斥鎖、照任務表跑、上下層（預設看資料夾包含、可登記覆蓋）；標準配備（git 提交、needs、收件、切換使用者、cgroup 框、once 等，跟核心同一支 aos-tick、必須全掛；cgroup v2 與 git 是完整保證的條件，沒有時走內建備援、仍算全掛）；其他掛載（kernel、agent、clock、自訂任務）；tick 與 daemon 之間有通道傳訊；spec 的保證以標準配備全掛為前提。
- [09-30 審稿](reviews/2026-09-30/README.md)：Fable 與 astra 兩輪審 notes／spec，77 條待處理，要依第十八批重新分類。
- [09-30 待議：daemon 職責與多 daemon](2026-09-30-daemon-split-and-multi-daemon.md)：多 daemon 範圍已答（a 多帳號、c 巢狀、e 備援，互不轉送，備援交外部重開）；已裁定：daemon 拆成開格核心＋可掛部件（同程式設定開關），spec 改寫中。
- [10-01 草稿：最核心的 aos-daemon](2026-10-01-daemon-core-sketch.md)（**草稿，未裁定**）：在 10-01 極簡 aos-tick 的前提下，daemon 砍到只剩「讀 node 清單、照週期叫 `aos-exec <node>`、看 0／1／2 印一行」；列出 A 組留／砍／默認不會發生、跟 tick 對不上的地方、跟 cron 比多了什麼與待裁定點。
- [kernel 樹與註冊式 tick](2026-09-29-kernel-tree.md)：09-29 架構方向改回 kernel 樹＋註冊式 tick；spec 已依此重寫，原先「單一控制寫入者、總帳本」的寫法已拿掉。
- LLM 排程：09-29 晚使用者裁定 LiteLLM 不進標準、只當可選 endpoint；aos 自己的排程分三檔（直連／交給 endpoint／自己排，預設自己排；直連原叫「不管」），見裁定第十三、十五批與 [spec S-301](../spec/scheduling/llm.md)。
- systemd：第十四批裁定**初版不用 systemd**；cgroup v2 是完整資源保證的條件（第十九批起屬標準配備，不屬 tick 核心；沒有 cgroup 時標準配備內建備援、仍算全掛，見[第十九批](verdicts/10-tick-minimal-core.md)第 8 條），quota 可選。第十五批：cgroup 一律要事先準備好，另有開關讓 daemon 自建。

軟性設計原則：[兩次 tick 之間的環境穩定性](between-ticks-configuration.md)。由原先硬保證改為設計指導，不屬於 spec，也不設強制驗收。

## 背景與探針

- 三大概念（09-28，歷史，現行以 spec 為準）：[三大概念：基底、agent、任務與排程](concepts.md)，逐塊見 [基底](base.md) → [agent](agent.md) → [任務與排程](scheduling.md)。是當時接受的責任分區，不代表三個程序或已完成實作；09-29 起改成 node／kernel 樹，用語以 spec 為準。
- 平台：使用者要求原生 Linux 與 WSL 都要能跑；公司 WSL 的對照查證見 [WSL 機器查證](2026-09-29-wsl-machine-check.md)。
- 探針：局部實測與重跑方式見[探針入口](probes/README.md)；09-29 另量了 `systemd-run` 開短命程序的延遲，見 [systemd-run 延遲](probes/systemd-run-latency.md)。

拍板用的比較材料（決定已下，見裁定紀錄；原檔已封存，這裡是縮短版）：

- [依賴盤點](2026-09-29-dependency-review.md)：導出第十四批裁定；留決定、必要依賴現況、暗中依賴與砍依賴的代價。
- [LLM 排程器選項](2026-09-29-llm-scheduler-options.md)：導出第十三批裁定；留三檔決定、估時與自製 vs LiteLLM 比較。
- systemd 拆分（daemon 與 root helper 逐條標哪些交給 systemd）已被第十四批「初版不用 systemd」取代，已封存。

09-28 的方向摘要：先放下正式員工／工具的組織分類，以一 agent 一 Linux 使用者、cgroup v2 管執行資源、project quota 管自有容量（09-29 裁定：可選、只記帳）。工具沿用委託 agent 的權限與資源，不需要逐工具 bwrap；保護宿主的整套 aos 外牆仍保留，具體部署未定。CPU worker 取消是後續方向，尚未實作；前文的固定 worker 構想保留為演進脈絡，不能同時當成最新要求。

規模目標：一台家用機保存 10,000 個 agent，每小時活躍不到 100 個，共用十幾個雲端 LLM endpoint；這不是同時併發上限，也不是已完成的規模驗證。idle 不常駐、不頻繁 tick，事件或到期才喚醒。Docker／FUSE 不作基本前提，FUSE 延後。

## 歷史

過時或已被取代的筆記都在 [archive/](archive/README.md)，不刪、不維護，每檔第一行寫了為什麼封存、現行看哪：

- 09-28 從 proto5 收錄的快照（六份筆記、萬 agent 計畫、兩份外牆調查），連同 15 份來源對照表：import-2026-09-28（已封存檔 README.md，索引見 [archive/README.md](archive/README.md)）。探針沒搬，仍在 [probes/](probes/README.md)。
- 09-28 的三份審查（notes 審查、spec 遺漏、spec 冗餘，都針對重寫前的舊 spec）、spec 重寫處置表、systemd 拆分、兩份比較材料的完整原檔：見 [封存索引](archive/README.md)。
