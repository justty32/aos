# HANDOFF — compact 交接

← [AGENTS.md](../AGENTS.md)｜規矩見 [common/user § compact 前先寫交接](workflows/common/user.md#compact-前先寫交接2026-10-15-定)

使用者說要 compact 前，頂層把交接寫在這裡；compact 後 Claude Code 的 SessionStart hook（[`wf/tools/compact_reload.sh`](tools/compact_reload.sh)，設定在 repo 根 `.claude/settings.json`）會把**第一個二級標題那一條**連同 [user.md](workflows/common/user.md) 一起讀回上下文。

**寫法**：本檔**只留一條**（使用者 11-13 晚裁「HANDOFF 只留最新一條」，[wf-into-aos-plan Q12](../proto8/thinking/2026-11/13/wf-into-aos-plan/05-待裁與衝突.md#使用者裁定11-13-晚頂層轉逐字)）：寫新的就把舊的整條換掉，標題用二級標題加日期時間，舊的看 git 歷史。每條寫：

1. **session 內授權**：push（是否「隨便 push」）、在家／出門、子 agent 模型分配、其他當場給的許可。
2. **正在討論的設計**：題目、已定的、未定的（附 thinking／NORMS 位置）。
3. **當晚新定的規範條目編號**（C-幾、N-幾）與還在跑的子 agent。

本檔沒有條目時，hook 改印 [progress.json](progress.json) 的 open 條目。

## 2026-11-27 早（家機）——pi 進沙箱：目標三句、標準佈局、`.aos`；最小方案 fable 在想

**寫這條的是家機 repo-aos 樹的 `main`**（Claude Code，模型 Opus 5.5）。上一條是家機 11-25 23:0x（中間夾了公司 eca-aos 11-26 的進度），全文在 git 歷史 `4e6baf17c`。細節在 [`wf/ws/main/notes.md`](ws/main/notes.md)「2026-11-27 早（家機）」、思考紀錄 [pi沙箱-1127](../proto8/thinking/2026-11/27/pi沙箱-1127.md)，原話 [9p-proc-1125](../proto8/thinking/2026-11/25/9p-proc-1125.md) 第 145～160 段。

**授權**：沒有 push 授權（本地比遠端多 4 個 commit＋這次收尾那個，等使用者說）。子 agent：照往例用 Agent 工具，普通工作 opus、想事情 fable，不 commit，回來 main 驗再交；fable 寫不進 `.md` 報告，全文從回覆存進 `~/.aos/scratch/<名>/report.md`。

**今天做了的**
- 開場 pull、同步 11-26 公司的進度給使用者。家機重跑：sky-1125 10 PASS；aos-daemon 起初 619／623（seccomp 名字表缺新 Linux 的 12 個、測試沒收前一組的 daemon），opus 修好：名字表改 make 時從標頭產生，642／642×3（`8d4fa83fc`）；README「要使用者定的」第 7 條（名單寫了不認得的名字怎麼辦，推 a）。
- 封路實驗 `proto9/experiments/channels-1127/`（`81776b63f`）：預設下 SysV IPC／mqueue 三方向全通（沒開 IPC namespace）、`/proc/1/net`、照 PID 改兄弟與 daemon 的 nice／上限；封路建議五條。
- **pi 原型 `proto9/experiments/pi-sandbox-1127/`**（`a815a05a8`）：pi 整隻在 aos-daemon 的 proc（預設的鎖、`net none`），腦只經 `/llm`（unix socket＋宣告，proxy 數次數、上游家機 LiteLLM、不握金鑰），四個工具通、三件不該做到的做不到；`--fake` 不花錢。宣告還寫舊的 `__meta`。
- fable 三份報告（`~/.aos/scratch/proto9-onlykernel-1127/`、`proto9-exec-1127/`、`proto9-pisandbox-1127/`）：約 18 題，**使用者都沒答**，改要一個最小方案。

**使用者今天定的**（細節在 pi沙箱-1127「定了的」「天空的佈局」）
- 目標三句：讓 pi coding agent（read／write／edit／shell）安全行動的沙箱，基底之上層層疊 kernel（最輕＝純檔案遮蔽器）；基於 Plan 9／aoslua、只取概念用 Linux 輪子；**選配與介面是核心**，懶得管的漏給 Linux。自述 Linux 新手，問他要用「pi 在裡面會怎樣」講。
- 原型照甲（pi 整隻在沙箱、經 `/llm` 連腦）；`__call` 之後另外規劃；執行不攔（傾向）。
- **元表夾 `__meta` 改 `.aos`**，裡面名字不再加 `__`（`.aos/index`、`.aos/interfaces/aos/llm`）。
- **預設 Unix 標準佈局**（第 159 段）：`/` 是管它的那一方的地方（唯讀），`/.aos` 是管它的那一方的宣告（取代 `/aos`、`/daemon`）；proc 家目錄 `/home/<名字>/` 可寫、`~/.aos` 是它自己的；由起 proc 的人選。普通程式什麼都不用知道；daemon 寫的事實留在 daemon 目錄（外面看），proc 預設看不到。

**在跑**：fable「最小方案」（第 160 段：「我要最小方案，也就是讓pi進沙箱，然後我們可以層層疊疊。剩下的都漏進linux沒關係」）。回來後：全文存 `~/.aos/scratch/proto9-minplan-1127/report.md`（夾已建）→ 摘要給使用者（方案一段＋圖、做什麼、漏給 Linux 的、【擬】預設、最多 3 題）→ 他說照擬就派 opus 做。

**還開著**：中文版知識庫落後 36 頁（11-26 收工就說要派，還沒派）；公司那台：sky-1125／channels 的 abi3 欄要在 WSL 跑一次對照、aos-daemon 名字表改產生後要在 Ubuntu 編一次；11-26 子 agent 的【擬】18 條、決策審查停在第 3 題（`aos/ctl` 形狀，`/aos`→`/.aos` 後可能要重看）。
