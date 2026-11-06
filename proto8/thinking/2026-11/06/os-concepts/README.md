# 2026-11-06 OS／韌體概念對 aos 的 kernel 與「定義＝原始碼」能借什麼、板子很多核怎麼比、Linux 原生機制與可遷移性（os-concepts，fable 規劃＋三個 fable 子 agent；沒改程式、沒改條文）

← [2026-11-06](../README.md)｜[thinking](../../../README.md)｜接著挖：[daemon-board](../daemon-board/README.md)（板子比喻 37 列、六題已裁——本夾不重做那些列）｜相關：[kernel-daemon](../../05/kernel-daemon/README.md)、[feat-proto](../../05/feat-proto/README.md)、[no-pid 05](../../05/no-pid/05-監管樹.md)、[tick-time 03](../../05/tick-time/03-11-06-裁定與新設計.md)、[portable-flow 02](../../05/portable-flow/02-image-模型.md)、[apply-ideas 02](../apply-ideas/02-排程.md)（排程基線）｜規矩：[user/03](../../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)、09-01 通則（比喻貼不合處＝天然差異，不硬改 aos）

## 使用者原文（11-06，逐字）

> 然後可以再派一個fable去思考，既然我們有daemon作為板子，那麼RTOS，乃至於嵌入式linux，或是其他作業系統概念。對於我們的kernel來說，有哪些可借鑒、參照的地方？或是普通的韌體programming概念，對我們的"定義=原始碼"來說，又意味著啥。考慮到我們雖然用板子來類比，但我們的cpu核心很多(可以掛一堆proc)

稍後補的四段（比喻落地可直接用 Linux 原生特性、但要可遷移；「建議」經 daemon；上位原則＝可遷移性；root daemon＝矛盾集中點、使用者保底）逐字在 [09](09-Linux原生機制與可遷移性.md)、[10](10-可遷移性原則草稿與root例外.md)。同日使用者說 fable 規劃者可再派 fable 子 agent——三個子題各派一位，本夾是彙整；另一隊在寫 CONCEPTS／NORMS，本夾只標落點。

## 一句話結論（白話）

**板子比喻到「誰先跑」和「有幾顆核」兩處就斷了，其餘八成 aos 已經是那樣。** 補成三段式：**daemon＝板子＋BSP**（上電、起停、電源軌、看門狗）、**kernel 身體＝一顆很薄的 RTOS 核**（llm kernel 的級數＋aging＋deadline＋slots 就是教科書那幾招）、**`procs` 表＝s6-rc 那種服務目錄**（exec／loop／daemon 型＝oneshot／longrun／bundle）；「很多核」這一層 aos 是 **AMP 多核 SoC** 不是 SMP——daemon 是主核只管誰上電、每個 proc 是一顆跑自己韌體的遠端核、stack＝它的 SRAM、信箱＝RPMsg endpoint，Linux 的 SMP 分時在底下隱形，**核數不是矽定的**（`max_running` 是唯一的「幾核」）。「定義＝原始碼」在韌體語彙裡是 **XIP：原始碼就是 image、沒有編譯這一步**，所以「編譯期 vs 執行期」在 aos 變成「值住哪一層」：定義（ROM）→ `.env`／`AOS_*`（取樣腳）→ 覆蓋層（EEPROM，跟 image 走）→ ctl 窗（暫存器）。**比喻落地＝直接用 Linux 原生機制，判準是「會不會破壞可遷移性」**（上位原則，使用者確認）：設定寫在樹裡、到新機器由 daemon 重套＝好，行程身上的狀態不是真相；經 daemon 是建議手段；**root daemon 是矛盾集中點**——搬不走的全集中在它身上、由使用者保底、可以綁這台。帶得出來的新東西幾乎全是**零程式的句子**；唯一要動程式的是 **aging 改用 kernel 樹自己的鐘併進 T4**（+0.5 h）。不插大重構。

## 分檔目錄

| 分檔 | 涵蓋 |
|---|---|
| [01-OS與kernel-對照表](01-OS與kernel-對照表.md) | 子題 1：RTOS／init 系統／Linux 概念 ↔ kernel 與 proc 排程，28 列＋最有意思的三個＋比喻在 kernel 層哪裡失效 |
| [02-OS與kernel-能借鑒](02-OS與kernel-能借鑒.md) | 子題 1 能借的 7 處：判官不排隊、依賴順序、runlevel、優先序反轉、aging 單位、stack 大小、三型＝s6-rc |
| [03-韌體與定義-對照表](03-韌體與定義-對照表.md) | 子題 2：韌體概念 ↔「定義＝原始碼」，23 列＋最有意思的三個 |
| [04-韌體與定義-能借鑒](04-韌體與定義-能借鑒.md) | 子題 2 能借的 7 處：值住哪四層表、回滾食譜、斷電安全、HSM 四樣、靜態配置、校正參數、debug 開關 |
| [05-很多核-比喻失效與換比喻](05-很多核-比喻失效與換比喻.md) | 子題 3：板子比喻哪 9 列因多核失效、五個候選、推薦 AMP 多核 SoC 並重講七個名詞 |
| [06-很多核-對照表](06-很多核-對照表.md) | 子題 3：多核／叢集概念 ↔ aos，27 列（slots／priority／limits／max_running／budget 各對什麼）＋最有意思的三個 |
| [07-很多核-能借鑒](07-很多核-能借鑒.md) | 子題 3 能借的 7 處：核數＝max_running、不釘核、整樹總額用 systemd scope、共用 stack 的鎖、quiesce、不做負載平衡、一致性邊界 |
| [08-天然差異](08-天然差異.md) | fable 代定 9 條；三個子題的天然差異 27 條 |
| [09-Linux原生機制與可遷移性](09-Linux原生機制與可遷移性.md)、[09-續](09-續-偏離建議的地方與方向題.md) | 使用者補：原生機制怎麼用不破壞可遷移性——判準、兩軸表 17 列；續：現行偏離「建議經 daemon」8 處與代價、方向題 B（sandbox）、代定 |
| [10-可遷移性原則草稿與root例外](10-可遷移性原則草稿與root例外.md) | 可遷移性成為正式原則的草稿（C-76／N-65 暫稱、寫哪層）、root daemon 可放寬清單與邊界、重建 root 四步、方向題 C |

## 方向題（5 題；推薦放第一；全文在各分檔）

1. **通用 kernel 的判官永遠只做準入（白名單＋格數），排隊交給各 kernel 身體？**（[02 § 1](02-OS與kernel-能借鑒.md)）推薦：**是**——判官拒了寄件人自己重寄；要排隊＝照 llm kernel 寫一個 kernel 身體（N-42 兩隻不併）。替代：判官 `judge.json` 加 `queue: true`——通用 kernel 長成 llm kernel 的樣子、模式 1 在 daemon 圈內要存隊列、判官不再「快」。
2. **llm kernel 的 aging 從「等幾拍」改「等幾 tick」（兩鐘規則）、併進 T4？**（[02 § 5](02-OS與kernel-能借鑒.md)）推薦：**改**——11-06 已裁「kernel 內部計時用自己樹的鐘」，aging 正是內部計時；凍住再醒不會瞬間全升級；+0.5 h。翻的是 feat-proto 03 的 fable 代定，不是使用者裁定。替代：不動（排程速度綁 daemon 的 `interval_ms`）。
3. **整樹總額用 `systemd-run --user --scope -p MemoryMax= -p CPUQuota=` 包根 daemon 當官方做法寫進 P8 食譜，`limits` 的 cgroup key 等「一個 agent 一個帳號」那支 root 小程式一起做？**（[07 § 3](07-很多核-能借鑒.md)、[10 root 放寬](10-可遷移性原則草稿與root例外.md)）推薦：**是**——零程式、今天就有「整板 PSU」，而且正好落在 root（矛盾集中點）；WSL 沒 systemd 標「家機才有」。替代：現在加 `cgroup` key（要 root／委派，權限題提前、違 KISS）。
4. **可遷移性原則草稿（C-76／N-65 暫稱，含「root 例外、使用者保底」）要不要照 [10](10-可遷移性原則草稿與root例外.md) 的形狀交給 lift-to-norms 寫進條文？** 推薦：**要，概念一條＋規範一條檢查單六項**。替代：只寫概念不寫規範（檢查單散在 N-28／N-04／N-17 各處，P8 試驗場沒有一條可對）。
5. **no-pid 已落地的那批（N-17 判活只剩 daemon、別人不碰 pid、ctl 改寄信、aos-lock T2）要不要跟著「降成建議」放寬？**（[10 方向題 C](10-可遷移性原則草稿與root例外.md)）**本夾不判、兩邊後果列在那裡**；頂層傾向不放寬（沙箱一個信箱、判官能管權限、用可遷移性判準看 no-pid 每一條都通過，放寬只剩便利）。

另兩題候選不上榜、照 09 推薦代定（可翻）：sandbox 命名空間先不改成 daemon 認 `sandbox` key（[09-續 方向題 B](09-續-偏離建議的地方與方向題.md)）；改定義「什麼時候生效」不統一（[04](04-韌體與定義-能借鑒.md)）。代定全文在 [08](08-天然差異.md)。
