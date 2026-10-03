# 任務：調查報告（第二份）——Linux 以外的作業系統與學術概念，aos 能借什麼

你在一份 repo 副本裡（目前目錄）。**只讀，不要改任何檔**；唯一要寫的是 `report.md`（目前目錄根）。繁體中文（台灣用語），直白、不灌水。

## 背景

aos 是一個把「檔案系統當空間、tick-tock 回合當時間」的系統，daemon 是運行層，kernel 和 agent 都只是 tick 啟動的任務，一切狀態與控制都是 LLM 讀得懂的 JSON 檔。使用者認為 daemon／tick 基底已打好，接著想設計 kernel：管理的資源除了 CPU／空間，還有 token 數、易用性、人類可讀性；排程可以有很多種，甚至直接讓 agent（LLM）排程；被管的任務時間單位是 tick-tock，內容是 inst（目前多是 LLM agent）。

上一份報告已經比過 **Linux kernel**：`proto7-1/notes/research/2026-10-03-linux-kernel-borrow.md`（請先讀它，**不要重複**；可以引用它的結論與 D-01～D-20，說明新對象補了什麼、或推翻了什麼）。

使用者這次的原話：
> 可以讓他再去調查關於其他類型的作業系統，比如 rtos、微核心，乃至於一些僅存於學術論文中的概念。

## 先讀
1. `proto7/spec/core.md`（S-01～S-23）
2. `proto7-1/spec.md`（特別是第 2、4～7、9、10 節）
3. 上一份 Linux 報告
4. 按需：`proto7-1/lib/aos7_kernel*.py`、`proto7-1/notes/infra-needs.md`

## 調查對象（起點，自己增刪；重要的多寫，不相關的一句帶過）

- **RTOS**：FreeRTOS、Zephyr、VxWorks、QNX 的排程（固定優先序搶佔、優先序繼承／天花板協定、rate-monotonic、EDF、時間觸發 TTA／ARINC 653 分區排程、tickless、看門狗）。對照：aos 的回合就是時間，能不能做「時間觸發」「分區」「WCET 預算」（把 token 當 WCET？）。
- **微核心**：Mach、L4／seL4（capability、IPC、形式驗證、MCS 的 scheduling context 與預算傳遞）、QNX Neutrino、MINIX 3（驅動在使用者空間、reincarnation server 自動重啟）、Fuchsia／Zircon（handle、job／process 階層、job policy）。對照：aos 的 kernel 本來就是任務、溝通靠掛載與檔案。
- **Exokernel／library OS、unikernel**：Aegis/ExOS、Nemesis（自我分頁、QoS crosstalk）、MirageOS。對照：「kernel 只保護、不抽象」與 aos 的 daemon/kernel 分工。
- **Plan 9／Inferno**：一切皆檔案、per-process namespace、9P、union mount。對照 S-01、S-23 掛載（這是最接近 aos 的，深挖）。
- **capability 系統與 object-capability**：KeyKOS／EROS／CapROS（持久化單層儲存、checkpoint）、Capsicum、CHERI。對照：掛載當權限、委派 token 預算。
- **學術概念**（只存在論文或研究原型也要）：lottery／stride scheduling（Waldspurger）、resource containers（Banga）、Scheduler activations、Eclipse／Scout 的 path、Barrelfish multikernel（每核一 kernel、訊息傳遞、狀態複製）、Singularity（SIP、契約式通道）、Spring、Amoeba／Sprite（分散式、行程遷移）、Lottery 的 currency／ticket transfer、Hierarchical scheduling（CPU inheritance scheduling、HLS）、Borrowed Virtual Time、Coscheduling／gang scheduling、Feedback control scheduling、Market-based／auction resource allocation（Spawn、Tycoon）、Persistent OS、Actor 模型的 OS、"OS for AI agents" 類近年研究（例如 AIOS、MemGPT 的虛擬 context 管理，請查證確實存在再寫，不確定就標）。
- 其他你認為對「LLM agent 當任務、token 當資源、回合當時間、檔案當介面」最有啟發的。

## 每一項回答
1. 它是什麼、解決什麼（短，事實要準；不確定標「不確定」；有出處就附論文名／年份／連結）。
2. 在 aos 對應什麼（資源換成 token／錢／呼叫數／易用性／可讀性；時間換成回合）。
3. **值得借／要改／不要借**＋理由；和 Linux 報告比，是新東西還是同一件事換名字。
4. 值得借的寫具體草圖：kernel 讀哪些檔、寫哪些檔、JSON 長怎樣（S-01）；需要 daemon／tick 多提供什麼（標出來，使用者最在意這層）。

## 另外專門寫
- **與 Linux 報告的差異**：哪些結論被這次的對象強化、哪些被推翻或補充。
- **「讓 agent 當排程器」的學術支撐**：market／auction、feedback control、scheduler activations、hierarchical scheduling 哪個最適合 LLM 當排程器，為什麼。
- **token 當資源的最佳模型**：lottery ticket／currency、resource containers、seL4 MCS 的預算傳遞、WCET 預算——哪個最貼近「agent 之間委派 token、子任務花父任務的錢」。
- **對 daemon／tick 的新需求**：上一份已有 D-01～D-20，這次只列**新增**的（從 E-01 起編），標「必要／有更好」，以及跟哪條 D- 有關。
- **最值得做的三個實驗**：在 proto7-1 上用探針（kernel／agent 隨便寫、不改 daemon 或只改一點）就能試的，每個寫：要驗證什麼、怎麼做、看什麼結果算成功。

## 格式
- 開頭 10 行內摘要＋總表（對象｜aos 對應｜借／改／不借｜跟 Linux 報告比：新／同／推翻｜一句理由）。
- 之後逐項；JSON 草圖用程式碼區塊；引用 aos 寫路徑或 S- 條號。
