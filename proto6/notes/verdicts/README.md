# 2026-09-29 使用者裁定：索引

← [筆記索引](../README.md)

09-29 使用者一整天分十七批裁定，另有一段軟性標準、一段「下班前的方向」與 B1／B2，依時段分成八份；09-30 的第十八批是第九份、第十九批是第十份、第二十批是第十一份。

讀法：

- **以裁定紀錄為準，後批優先**：後面的批次常推翻或細化前面的（例如第五批拿掉帳本、第十四批改成初版不用 systemd、第十五批把 B1 換成一條 cgroup 通用規則），同一件事以最後一次裁定為準。
- 被取代的舊說法多半留在原處，用刪除線或括號註明「已作廢」「已被第幾批取代」。
- 落進 spec 的條文，各條後面有連結指到 spec 條號。第十三～十七批與 B1／B2 已整批落進 spec（B1 已被第十五批取代）。
- 舊連結指到 [2026-09-29-verdicts.md](../2026-09-29-verdicts.md) 的，那裡留了批次對照表。

| 份 | 批次 | 一句話 |
|---|---|---|
| [01](01-notes-review-1-10.md) | 第一批、第二批 | notes 審查待裁定 1～10（極小 root helper、額度只記帳、重啟全殺、中央代發 LLM 等）；設定下一次 tick 生效、待處理資料夾、結果隨 tick 清理 |
| [02](02-kernel-tree-and-tick.md) | 第三～五批 | tick 改註冊式；改回 kernel 樹；拿掉帳本改用 git，資源做成可插拔 module |
| [03](03-node-and-protocol.md) | 第六～十二批、軟性標準 | root helper 與 sudo 啟動、kernel 與 agent 合併成 node、協議篇的 method／收件／attention／清理等細節、一步一步走完整套 agent 循環 |
| [04](04-late-day-directions.md) | 下班前的方向、第十三批 | systemd 方向（後被第十四批取代）、LiteLLM 只當可選 endpoint；LLM 排程三檔、預設自己排、串流、池就是一個 node |
| [05](05-dependencies.md) | 第十四批、追加、B1／B2 | 只用標準庫（jsonschema 例外）、quota 可選、cgroup v2 必要、初版不用 systemd；cgroup 子樹來源（B1，已被第十五批取代）、daemon 當掉後清程序 |
| [06](06-cgroup-direct-delivery.md) | 第十五批 | cgroup 一律要事先準備好、另有開關讓 daemon 自建；「不管」改名「直連」；投件只查目標是不是 node、可設鬧鐘；交給 endpoint 只轉發不重試；git 2.35；token 預算先不做 |
| [07](07-review-fixes-and-proto-gaps.md) | 第十六批 | spec 審稿修正：check 不擋收結果、回應沒權限也丟、LLM 池權限投件時才報、LLM 結果照一般收件叫醒、回話只記錄不再觸發、attempt 目錄加發件者前綴、鬧鐘檔分 req／resp；原型缺口：cgroup 框命名、省略 root 時原層只當分支、once 登記時帳號要存在 |
| [08](08-cancel-task-cgroup-and-gaps.md) | 第十七批 | 取消工作 work.cancel、每任務一層 cgroup、自開 once 不叫醒、kernel 收回話、任務表宣告 methods；原型缺口逐條定狀態（SourceChanged 等）；設定檢查跑完回 0、有寫 cgroup_root 也搬程序 |
| [09](09-special-computing-os.md) | 第十八批（09-30） | 特殊計算的 OS：分配單位是一次計算；多層多 kernel，各 kernel 自訂抽象、資源、隔離，以 Linux 為底；上下層不必對齊；管理目標之一是降低隨機性（尚未落 spec） |
| [10](10-tick-minimal-core.md) | 第十九批（09-30） | tick 是定期執行的程式，cwd 就是管轄區，管轄區可包含不可重疊、被包含者從屬；任務隨意掛載；三層架構：tick 核心（互斥鎖、照表跑、上下層）、標準配備（git 提交、needs、收件、切換使用者、cgroup 框、once 等，跟核心同一支 aos-tick、必須全掛）、其他掛載；tick 與 daemon 之間有通道傳訊；人手跑 tick 風險自負（spec 已依它改寫；其中標準配備、全掛、兩級等已被第二十批改寫，見 11） |
| [11](11-tick-as-unit.md) | 第二十批（09-30） | tick 是 aos 的衡量基準：排程以 tick 為單位、排程行為在任務表上做、整個體系基於 tick，daemon IPC 是唯一逃生口；核心四樣、系統級任務、普通程式（spec 正依它改寫中，後批優先，推翻第十九批標準配備結構） |
