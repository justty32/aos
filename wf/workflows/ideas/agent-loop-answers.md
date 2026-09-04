# agent 迴圈三題：使用者回答

← [ideas](README.md)｜前篇 [agent-loop-under-clock](agent-loop-under-clock.md)｜
[run 與 async](exec-run-async.md)｜[地的生死](land-rules.md)

日期：2026-09-04

本篇承接前篇「待使用者決定」的三題。這些是使用者定義與工程留題，不是
[verdicts](verdicts.md) 裡的正式裁決。

## 使用者原話

> 1. 對，一個agent就是一個資料夾。2.就跟claude code一樣，跑到LLM不再呼叫工具，因為agent循環就是這樣(?)。3. 這個就是後續的工程問題了，之後再說

## 第 1 題：agent 住哪

**使用者定義**：一個 agent 就是一個資料夾。

**AI 觀察（非裁決，可否決）**：生一個 agent＝`mkdir`＋登記；殺一個 agent＝刪資料夾。
daemon 的生死規則直接沿用 [land-rules](land-rules.md)，不另立一套。今天程式碼把 agent 放在
`.aos/agents/`，因此正式成為現況缺口，見 [07-existing-aos](top-to-bottom/07-existing-aos.md)。

## 第 2 題：跑到什麼時候

**使用者定義（語氣帶保留）**：跟 Claude Code 一樣，跑到 LLM 不再呼叫工具。原話帶有
「(?)」，表示使用者語氣帶保留。

**AI 觀察（非裁決，可否決）**：是，就是這樣；這就是 agent 迴圈的本質，沒有更多了。放進
時鐘模型，就是 LLM 吐出的 list 為空，A 沒有東西可 `exec`，狀態變成「閒著」。

**AI 觀察（非裁決，可否決）**：**停不是死。** 資料夾還在，只是睡了；下一次 inbox 進東西
就醒來再跑一圈。這跟 Claude Code 對得上：不打字它停著，打字就接著做。因此 agent 的 run
條件分兩段：**有事就跑到 list 空為止，然後等下一封信。**

**AI 觀察（非裁決，可否決）**：這個條件可以往上推給 `aos run`。使用者先前在
[exec-run-async](exec-run-async.md) 說 run 的終止條件還沒想好；agent 現在給出通用答案：
**這次 exec 沒產出新的 inst 就停。** 任何 run 都能使用，不只 agent。

使用者隨即回應：

> 太好了，若沒有新的inst那就停，這太對了。

**使用者定義**：`aos run` 的通用停法＝**這次 exec 沒產出新的 inst 就停**。這是 run 終止
條件的正式答案，不再是「還沒想好」；但仍不是 `verdicts.md` 的正式裁決，本篇只標使用者定義。

## 第 3 題：每圈 prompt 怎麼組

**使用者決定：留給工程**，之後再說。

**AI 觀察（非裁決，可否決）**：這題跟「記憶＝地」是同一題，實作時會回來。

## 使用者宣告：概念層收尾

> 大體哲學已經擬定，接下來也沒啥好說的了，就都是工程上的實作。你覺得呢？

使用者認為概念層已擬定，往後是工程實作；AI 的回應尚在對話中，之後另記。

提醒：2026-09-03「先玩現有系統、暫停設計」的裁決仍有效，見
[play-watchlist](play-watchlist.md)。所以「工程實作」之前先過「玩」這關，不是直接開工。
