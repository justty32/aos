# 09 · 把 LLM 當 CPU：主機板夠了，四個腳位留給實作

← [top-to-bottom](README.md)｜上一節 [08-time](08-time.md)｜[ideas](../README.md)

這一篇回答「概念基礎夠不夠承載 LLM 這顆虛假 CPU」。它只把已有材料收攏，**沒有新增裁決或
主張**。

## 使用者原話（2026-09-04）

> OK，到目前為止，我們的基礎都打好了吧？已經足夠承載agent了嗎？啊，應該說，足夠承載LLM作為一個虛假cpu的用途了嗎

AI 當時把還沒接上的地方列成四個「CPU 與主機板接觸的腳位」。使用者看完後回覆：

> 那四個腳位都是工程問題，實作的時候自然會有答案。

## AI 觀察（非裁決，可否決）：主機板已經夠了

這裡的「夠」不是說程式已做好，而是**概念上已經有地方安放 CPU 需要的東西**：

| 主機板上的東西 | aos 的大白話版本 | 來源 |
|---|---|---|
| 記憶體／位址空間 | **一塊地看得到的全部**；預設只看自己，掛載或 symlink 才開洞 | [land-rules](../land-rules.md) |
| 時鐘 | 一次 `exec` 是一格，一個 `run` 是一個時鐘，同步借鐘、async 脫節 | [08-time](08-time.md) |
| 行程 | 出生要登記；**死＝刪資料夾，身分＝路徑**；daemon 管所有鐘 | [daemon-clocks](../daemon-clocks.md)、[land-rules](../land-rules.md) |
| 中斷／I/O | inbox 收外面的輸入；tool 呼叫投出去，下一回合再收結果，今天程式已有這個形狀 | [exec-run-async](../exec-run-async.md)、[07-existing-aos](07-existing-aos.md) |
| 時間邊界 | 同步世界只放時間有上限的原子，慢工作去脫節子世界，timeout 當保險絲 | [exec-run-async-time](../exec-run-async-time.md) |
| CPU 週期的輪廓 | agent 一圈至少是**取指 → 執行 → 寫回**三步，再繼續下一圈 | [exec-run-async §c](../exec-run-async.md#c-agent-是一個-run一圈至少三步) |

因此，空間那條線（01～07）與時間那條線（08）合起來，已經是一張能插上 LLM 的主機板。

## 四個腳位：動手時的對照表

以下全是 **AI 觀察（非裁決，可否決）**。依使用者上面的決定，它們是**工程問題**，不是概念層
待議題；實作時拿出來逐項對照即可。

### 1. 取指令的格式（fetch）

每個 tick 到底餵 LLM 什麼：整個 list、某個指定檔，還是整理過的 context？LLM 要輸出什麼
形狀才算可執行指令（tool call）？**今天 `core/agent` 有自己一套，新模型沒有指定。**
（來源：[exec-run-async](../exec-run-async.md)、[07-existing-aos](07-existing-aos.md)；載入與可命名
對照 `G14`。）

### 2. 結果落在哪（writeback）

同步呼叫子世界時，回傳值是否就是**固定路徑的一個檔**？這只有 AI 提議，使用者未裁。
（來源：[play-watchlist 第 1 條](../play-watchlist.md#1-父層怎麼拿到子資料夾的結果)、
[exec-run-async §d](../exec-run-async.md#d-asynctrueai-反對開執行緒贊成開子資料夾)）

### 3. 出錯怎麼辦（fault）

LLM 逾時、回垃圾，或 tool 失敗時，要重試、留下錯誤標記，還是讓這塊地直接死？這個模型沒有
exception；`G19` 已把「LLM 不可靠、不確定」升成主軸，但處置仍未定義。
（來源：[play-watchlist 第 3 條](../play-watchlist.md#3-失敗)、
[cpu-to-os-gaps G19](../cpu-to-os-gaps.json)）

### 4. 停機（halt）

`run` 的停止條件還沒定；放到 agent 身上，就是「LLM 說自己做完」算不算停。
（來源：[exec-run-async §b](../exec-run-async.md#b-run-就是反覆-exec直到跑到定點)、
[08-time](08-time.md)）

## 兩處只是程式與模型對不上

這兩處不是概念缺口：

1. 今天的 agent 住在 `.aos/agents/`，新模型裡應是獨立資料夾。（來源：
   [play-watchlist](../play-watchlist.md)、[07-existing-aos](07-existing-aos.md)）
2. 今天 agent 的 LLM 步會**同步等 curl**，不符合「外部時間去脫節子世界」。（來源：
   [07-existing-aos](07-existing-aos.md)、[exec-run-async-time](../exec-run-async-time.md)）

## 使用者決定：概念層到此收工

**使用者決定（2026-09-04）**：四個腳位都是工程問題，實作時自然會有答案；不在概念層繼續
討論。這四條因此只是**動手時的對照表**，不是新的待議題。

AI 原本建議「先講第 1 與第 4」，依這個決定**撤回**；留這一句作紀錄，不再往下設計。

## 結論

**概念層的基礎到此算打完**：空間是 01～07，時間是 08；這張主機板已足夠承載 LLM 作為
虛假 CPU。這不代表四腳已有統一規格，也不代表現有程式完全符合，只代表剩下的答案會在實作中
長出來。

下一步沿用 2026-09-03 的裁決：**先去用現有的東西玩**，從真的阻礙回來決定要做哪一塊，不再
留在概念層繼續設計。（來源：[06-open](06-open.md)、
[os-metrics-and-resources §九](../os-metrics-and-resources.md#九停下腳步先去用現有的東西玩使用者裁決2026-09-03)）

## 相關清單

- `G01`：tick 卡住時，控制權怎麼回來。
- `G04`：每格之間可保存、可接續的狀態。
- `G06`：行程的出生、身分、登記與死亡。
- `G10`：daemon 統管時鐘與跨資料夾排程。
- `G14`：取指時，程式如何被命名、載入。
- `G19`：LLM／外部資源不可靠、不確定，fault 怎麼收。

清單本體與狀態見 [cpu-to-os-gaps.json](../cpu-to-os-gaps.json)；本篇不修改它。

---

**這節從哪來**：[land-rules](../land-rules.md)、[daemon-clocks](../daemon-clocks.md)、
[exec-run-async](../exec-run-async.md)、[exec-run-async-time](../exec-run-async-time.md)、
[play-watchlist](../play-watchlist.md)、[07-existing-aos](07-existing-aos.md)。

續篇／下一階段：[agent-loop-under-clock](../agent-loop-under-clock.md)——agent 規劃第一篇，記它在
上述時鐘模型下逐 tick 怎麼走；不重開本篇四個工程腳位。
