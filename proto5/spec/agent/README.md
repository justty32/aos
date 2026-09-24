← [spec 總導航](../README.md)

# agent 資料夾規範

← [proto5 README](../../README.md)｜指示詞：[directives.md](../directives/README.md)｜用這個資料夾的程式：[aos-agent.md](../aos-agent/README.md)（走一格、登記）、[aos-llm.md](../aos-llm/README.md)（問模型，`aos-llm call`）｜排程：[kernel.md](../kernel/README.md)

> 第 2 版，2026-09-24 定稿，同日 fix-r4 改命令列、fix-r5 家裡多一個 `resumed`；已實作（`lib/aos_agent_info.py`／`aos_agent_home.py`）。輪次、審查與實作沿革在檔尾〈沿革〉（09-24 試玩 r3 搬）。

一句話：**agent 資料夾保存設定、對話記憶與跨次執行的進度，讓 aos-agent 每次被叫都能接著做。**
`info.json` 說它是誰、記憶在哪、有哪些工具、用哪個模型代號；`state.json` 記走到哪、輸入從哪來、
外人加的門，以及「手上這一批送出去的工作」（`batch`）。

## 7. 已拍板的前提（使用者定的，不重問）

1. **沒有同步工具**：問模型、跑工具都是往 kernel `add --once` 的普通工作，agent 只認識 kernel。
   取捨：最快也要等一格 tick 才跑得到；同一批的工具可能平行跑，有先後依賴的要合成一個工具或拆成兩輪讓模型分次叫。
2. **agent 先進現有的池**：登記＝`aos-kernel add` 一個反覆行程（aos-agent.md §11），池與間隔從 `info.tick` 拿；K 由 `AOS_KERNEL_HOME` 給（09-24 fix-r4 由 `AOS_K` 改名）。
3. **llm.json 放 llm cpu 那邊**（cpu 的環境＝工作的環境）：agent 的 `info.llm` 只剩 `model`、`params`、`pool`、`timeout_ms`。

## 6. 這份沒管的

程式做什麼：走一格、登記＝[aos-agent.md](../aos-agent/README.md)；問模型＝[aos-llm.md](../aos-llm/README.md)。
（09-24 試玩 r2 補）`init`（單一內建預設）、`say`、`status`、`continue` 已有（[aos-agent.md §1.1～§1.4](../aos-agent/cli.md)）；（09-24 fix-r4 補）`listen`、`pause` 也有了（§1.5、§1.6）；（09-24 tools-base 補）`tools add` 也有了（§1.8）；（09-24 access-impl 補）`tools ls／rm／alias／unalias` 也有了；`init --template`、`tools enable／disable` 與 `llms`、一個 agent 一顆專屬 cpu：這輪不做，
使用者的構想在 [thinking/aos-agent.md](../../../thinking/aos-agent.md)、[thinking/2026-09-23.md](../../../thinking/2026-09-23.md)。
記憶太長（（09-24 第 4 隊補）機械版有了：[compact.md](compact.md)；叫模型濃縮摘要的 `--summarize`（第三波 W3-2）：[compact-summarize.md](compact-summarize.md)）；明確的 `fail` 狀態（等使用者拍板，見 [WAIT_USER A.14(d)](../../../wf/WAIT_USER.md)）。
**日常 CLI 是最小版**：家用 `aos-agent init` 建或手動建，話用 `say` 投、`listen`／`say --wait` 看回話（09-24 試玩 r2 補；fix-r4 `last` 改 `listen`）（aos-agent.md §1、§13）。

## 各節

原文裡「檔尾〈沿革〉」「檔尾〈實作補記〉」「見下」這類方位詞是拆檔前的位置，拆後照下表找對應檔（`history.md`、`impl-notes.md`、`rulings.md` 等）。

| 檔 | 內容 |
|---|---|
| [essentials.md](essentials.md) | 使用者只需要懂的：家裡人會碰的東西、常改哪裡 |
| [terms.md](terms.md) | §0 名詞（白話） |
| [layout.md](layout.md) | §1 資料夾長什麼樣：每個檔是誰寫的、做什麼 |
| [directives.md](directives.md) | §2 指示詞：`info.json`／`state.json` 解，被指到的檔不解 |
| [info.md](info.md) | §3 `info.json`：§3.1 人格、§3.2 記憶與 message 驗證、§3.3 工具檔 |
| [tools-opt.md](tools-opt.md) | §3.4 `tools` 元素的 `$opt`：`as` 改名、`only` 挑幾支、`_source`、`_jail`（09-24 access-impl） |
| [access.md](access.md) | §3.5 `access.json`：工具關進牢裡看得到哪些資料夾、信任資料與重疊、生效時機、擋不住的（09-24 access-impl） |
| [events.md](events.md) | （09-24 第 4 隊補）事件紀錄 `log/events.jsonl`（每批起訖與成敗、收件、壓縮）與 `log/usage.jsonl`（token 用量） |
| [compact.md](compact.md) | （09-24 第 4 隊補）記憶的機械壓縮：什麼時候能縮、怎麼縮（封存＝8 KB 機械摘要）、每步可重跑、tick 自動（預設開、32000） |
| [compact-summarize.md](compact-summarize.md) | （第三波 W3-2）`compact --summarize`：人跑時請模型濃縮封存摘要，每段機械檢查（比原本短、關鍵詞還在），不過或模型壞了退回機械版；自動與申請不叫模型 |
| [compact-more.md](compact-more.md) | （09-24 第 4 隊補）壓縮續：compact 申請（欄位、郵差投檔、tick 收據）與保證外 |
| [persona.md](persona.md) | （09-24 第二波 C 隊）人格是信任資料：`aos-agent persona show／set／append`；模型只能 `persona_propose` 提案，走團隊的 T-ask 待辦 |
| [state.md](state.md) | §4 `state.json`：§4.1 `input`、§4.2 `waits`、§4.3 `batch`、§4.4 `intake`／`consuming`／`sweep` |
| [errors.md](errors.md) | §5 錯誤代號 |
| [rulings.md](rulings.md) | 調度者裁決（第 2～3 輪，實作層級） |
| [history.md](history.md) | 沿革 |
