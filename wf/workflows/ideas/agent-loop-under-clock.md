# agent 在我們的時鐘下怎麼走

← [ideas](README.md)｜前篇 [daemon-clocks](daemon-clocks.md)｜[時間總覽](top-to-bottom/08-time.md)｜[CPU 腳位收束](top-to-bottom/09-cpu-socket.md)

日期：2026-09-04

這是 **agent 規劃的第一篇**。概念層基礎已完成：空間見
[top-to-bottom 01～07](top-to-bottom/README.md)，時間見 [08](top-to-bottom/08-time.md)，收束見
[09](top-to-bottom/09-cpu-socket.md)。09 的四個腳位是工程問題，本篇不重開。

## 使用者原話

> 好，我們來開始規劃agent。agent的本質就是一個連續循環的指令：把prompt丟LLM、取LLM結果並呼叫tool、取tool結果丟LLM...

> 想想看，這套循環在我們的時鐘下，會是怎麼樣

AI 走完下列逐 tick 之後，使用者回：

> 的確會是這樣

## AI 觀察（非裁決，可否決）——agent 是一種 `aos run`，逐 tick 走法

角色：父世界 P 有一個時鐘。agent A 是 P 裡的一塊地。A 每次要問 LLM，就生一塊脫節的小地 L
（自己的時鐘、登記在 daemon）；慢工具同樣生一塊 T。

- **第 0 tick**：P 動、A 跟著動。A 的 insts 看狀態是「有事要問」，把 prompt 寫進 L、請
  daemon 讓 L 走，標記自己「在等 L」。這 tick 結束，很快。
- **第 1～k tick**：A 只看 L 的 `out/` 固定路徑那個檔案在不在。不在就結束。對 A 幾乎免費，
  世界其他地照常動。
- **同時**：L 在 daemon 手上自己走那條很久的 curl，跑完把結果寫到固定路徑，工作結束。
- **第 k+1 tick**：A 看到檔案，讀進來。結果是一個 list，當場 exec：快工具這 tick 跑完、結果
  落 `out/`；慢工具再生一塊 T，狀態改「在等 T」。接著組下一份 prompt 寫進新的 L，回到第 0 tick。

所以「至少三次執行」在時鐘下真正的樣子是：**兩個有事做的 tick，中間夾 k 個空等 tick**。
k 由 LLM 多慢與 tick 多密決定。agent 沒有專屬行程，也沒有執行緒；agent＝一塊地＋一份每 tick
跑一次的 `insts.json`，內容是一台小狀態機（在等 LLM／在等 tool／該組 prompt）。

**使用者確認（傾向，非裁決）**：使用者對以上走法回「的確會是這樣」。

## AI 觀察（非裁決，可否決）——走完冒出的三件事

1. **agent 本身不需要自己的時鐘。** A 每 tick 做的都是有界的（寫檔、看檔在不在、跑快工具），
   所以 A 可以是同步子地、借 P 的時鐘。真正脫節的只有 L 和 T。A 只在「P 停了它也要繼續」時
   才需要自己登記時鐘（daemon 直接帶的獨立 agent）。兩種都合法，差別在誰讓它動。
2. **多了一種時鐘：一次性的。** P 的時鐘週期性；L 的時鐘只跳一下（跑一次、寫結果、結束）。
   daemon 登記簿兩種都要收。關機一次全停時 L 被殺、結果沒寫出，A 的狀態檔停在「在等 L」；
   重開時發現 L 死了又沒結果就重發。狀態都在檔案裡，重開就是接著走。
3. **世界會在等的時候變。** 第 0 tick 組 prompt 看到的地，和第 k+1 tick 執行結果時的地，中間
   可能進了新 inbox、別的 agent 改了東西。LLM 的 list 是對舊世界寫、在新世界跑。AI 認為正常
   （任何程式都這樣），工具結果下一圈會告訴 LLM；但組下一份 prompt 時要把等待期間到的 inbox
   一起放進去，否則永遠慢一圈。

## AI 觀察（非裁決，可否決）——順帶出的問題（未決）

A 的空等 tick 其實是在做「有沒有東西到」的檢查。tick 密則空轉多、疏則反應慢。第一層
inotify 門鈴（見 [fuse-host-extras](fuse-host-extras.md)）正是為此：檔案一到就標記，下一 tick
才處理，tick 仍是唯一單位。所以 `aos run` 除了「每隔多久」「直到什麼條件」，可能還有第三種：
「有變動才動」。是否收進 run 的定義，使用者未決。

## 使用者已答

三題的逐字回答、使用者定義與 AI 觀察已另記在
[agent-loop-answers](agent-loop-answers.md)，避免本檔超過 8 KB。

## 原先待使用者決定的三題

- **agent 住哪**：現在程式碼放 `.aos/agents/`；照「資料夾＝地」應是一個資料夾、有自己 `.aos/`，
  父地用 `aos run <child>` 帶。
- **「連續下去」到什麼時候**：`aos run` 的終止條件使用者說還沒想好，agent 是第一個真的需要
  它的客人。
- **每圈 prompt 從哪來**：整塊地全給，還是只給上一圈結果加一點。這是記憶體要不要每次全掃的
  問題，決定 agent 的地能長多大。

## 現有 aos 對照

以下只引用既有文件已查證的事實，沒有重查或修改 `core/`。

| 本篇模型 | 現有 aos | 對照 |
|---|---|---|
| LLM 是脫節小地 L | `core/agent/src/step.cpp` 的 `step()` → `complete_locally()` 同步等 curl | **不合法**：外部時間卡住同步 tick（見 [07-existing-aos](top-to-bottom/07-existing-aos.md)） |
| agent 是一塊地 | agent 住 `.aos/agents/` | **對不上**：今天住在 inst 層裡（見 [07-existing-aos](top-to-bottom/07-existing-aos.md)） |
| 一格內一起動、一起收 | `run_turn()` 的 `start_all()`／`wait_all()` | **已有**：整批會等最慢者才收格（見 [exec-run-async](exec-run-async.md)） |
| daemon 登記所有週期鐘與一次性鐘 | 各地只有分散的 `.aos/run.pid` | **沒有**：無全域時鐘登記簿（見 [daemon-clocks](daemon-clocks.md)） |

## 相關清單

- [exec-run-async](exec-run-async.md)、[exec-run-async-time](exec-run-async-time.md)——一圈至少三步、
  async 與脫節時間。
- [daemon-clocks](daemon-clocks.md)——誰推時鐘、集中登記與一次全停。
- [land-rules](land-rules.md)——地的可見範圍、生死與路徑身分；搬家另見
  [land-rules-move](land-rules-move.md)。
- [fuse-host-extras](fuse-host-extras.md)——inotify 門鈴只標記，仍在 tick 處理。
- [top-to-bottom/08-time](top-to-bottom/08-time.md)、[09-cpu-socket](top-to-bottom/09-cpu-socket.md)、
  [07-existing-aos](top-to-bottom/07-existing-aos.md)——概念時間、已收束的工程腳位、現況對照。
- [llm-cpu](llm-cpu.md)——LLM CPU；[agent-messaging](agent-messaging.md)——agent 間訊息失真與收斂。
