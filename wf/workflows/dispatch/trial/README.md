# trial — 大量試用：驗證＋找不順手（2026-08-30）

← [dispatch](../README.md)｜判準 [usability-target](../../ideas/usability-target.md)

**目的**：照使用者定的兩級劇本，用「使用者的方式」大量操作 aos，記**多餘的動作／看不見的狀態／錯誤不指路**，
每條附「用 pi／Claude Code 做同一件事的對照」。這階段**只找、不修**（修 bug 隊與改進隊之後另開）。

| 隊 | 劇本 | 發現檔 | 交接書 |
|---|---|---|---|
| L1 單人 coding agent | 在一個真的程式碼資料夾裡全程只用 `aos …`，lmstudio 與 pi 各跑一遍 | [findings-L1.csv](findings-L1.csv) | [proto-L1](../proto/proto-L1-solo.md) |
| L2 指揮 agent 團隊 | 主 agent 派生子 agent（各住一個資料夾）、通訊錄投遞、收回報 | [findings-L2.csv](findings-L2.csv) | [proto-L2](../proto/proto-L2-team.md) |

**發現檔格式**（`wf-table/1`，一行一條）：`id,lane,kind(bug|awkward|spec-gap|cannot),severity(1-3),step,expected,actual,compare,repro`。
`repro` 指向 `trial/repro/<id>.sh`（可重跑的最小重現，之後修 bug 隊直接當回歸）。

## L2 摘要（2026-08-30）

**結論：投遞的管子通了，團隊的語意還沒有。** `aos say --to`／`aos deliver`／`every/` 推子世界三條路都實測可用，
但「一隻主 agent 指揮兩隻子 agent」整條劇本走不完——不是哪裡壞掉，是**缺件**。

**缺的原語**（依痛感排序）：

1. **訊息信封**——`say()` 只寫純文字，沒有 `from`／來源世界／message-id。boss 分不出 w1 的回報、w2 的回報與使用者的新指令（`L2-05`）。沒有寄件人＝沒有回信地址。
2. **agent 看得到通訊錄**——只有頂層 CLI 讀 `contacts.json`；system prompt 只列工具、從不列聯絡人，agent 不知道隊上有誰（`L2-03`）。pi 引擎更徹底：完全不讀登記表，還明講「不要去動 `.aos/`」——通訊錄正好住在那裡（`L2-04`）。
3. **未讀信要看得見**——狀態只反映上一次跑完的 step，堆了 3 封未讀仍報 `idle`；`listen` 讀的是 log，未讀信在任何 `aos` 指令下都是隱形的（`L2-07`、`L2-12`）。使用者要讀信得先燒一次 LLM。
4. **隊層級的名冊與彙總**——沒有 `aos contact status`；`state.json.agents` 只涵蓋本世界。實測答「誰在忙」用掉 9 個指令，最少也要 3 個，而且答案還是錯的（`L2-25`、`L2-07`）。
5. **開箱即用的投遞能力**——新世界預設只裝 `cat`／`ls`／`sh`，沒有 `aos`／`deliver`／`contact`，boss 要派工得先由人幫它 `aos tool add`（`L2-02`）。
6. **雙向登記**——通訊錄單向，worker 要回報得有人先進 worker 世界補 `contact add boss`（`L2-06`）。
7. **「只有信箱、沒有 CPU」的端點**——使用者當收件人（住 `~`）必須先被 `agent init` 成一隻完整 LLM agent；`--to` 又吃名字不吃路徑、shell 還會先展開 `~`（`L2-11`）。
8. **建子世界這件事本身**——`agent init` 會往上找最近的 `.aos/`，在既有世界的子資料夾裡跑會把 agent 靜默建到祖先世界（`L2-01`）。

**可用的**：`every/` 放 `{"argv":["aos","run","sub","--step","1"]}` 推子世界正常（每回合 3 insts、子世界 turn 跟著走、exit 0），
`find_folder` 也正確選最近的 `.aos/`（`L2-16`）。三隻同時打一顆 lmstudio 不會壞，只是排隊完全不可見（`L2-17`）。

**對照 Claude Code**：那邊 spawn／派任務／回報／全隊狀態由宿主承擔，操作者不碰地址；aos 目前把這四件事全留給使用者用資料夾和相對路徑手工維持。
