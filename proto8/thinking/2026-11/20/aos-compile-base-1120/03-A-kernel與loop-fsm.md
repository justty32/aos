A 題之一：kernel 的定義夾跟 agent 差在哪、直接套現在的 agent_spec 會卡在哪；loop 與 fsm 能不能當成單獨的「可編譯單位」。

← [README](README.md)｜上一份：[02](02-現況-agent_spec與tool_spec.md)｜下一份：[04 形狀甲乙丙](04-A-形狀甲乙丙.md)

## 先講結論

- **kernel 跟 agent 只有「外殼」像**：都是一夾 json＋`_entry`、都可能有 loop、都有 hook（同一個引擎）。裡面幾乎全不同：kernel 沒有 system、tools、腦設定，所有東西擠在一份 `kernel.json`；有些 kernel 還帶自己的程式（`endpoints/litellm`）。
- **直接拿 `agent_spec` 編 kernel 會卡六處**（下表），其中四處是 `compile()` 把 agent 的形狀寫死了。
- **fsm 在編譯期已經八成是獨立單位**：`defs.fsm(...)` 回的是驗好的整張表，只差一個「單獨寫成一份 `fsm.json`」的出口。**loop 不是**：連宣告的函式都沒有。

## kernel 與 agent 並排

| | agent（agent-fsm） | kernel（框架站／llm kernel） |
|---|---|---|
| `_entry` | `aos-agent ctl add`：掛到 daemon 表上當一列 | `aos-daemon daemon.json`（自己一台）或 `aos-loop loop.json`（一列） |
| 身體 | `aos-loop` → `aos-fsm` → 四格程式 | `aos-daemon` 或 `aos-loop` → 框架站程式（`kernel`／`kernel_llm`） |
| 設定 | 拆成 `tools.json`、`llm.json`、`system.txt`、`hooks.json` | 一份 `kernel.json`：旋鈕、`hooks`、`endpoints` 全在裡面，每輪重讀 |
| hook | 9 個事件（`before_tool`…`on_clock`） | 3 個事件（`before_verdict`、`after_verdict`、`before_reply`） |
| 介面宣告 | `interfaces.json` 的 `aos-agent` | 只有 llm kernel 有 `interfaces.json`（`aos-ledger`） |
| 帶自己的程式 | 格程式（範本裡，`agent.py` 不管） | `endpoints/litellm`、`fake_slow`（llm kernel） |

## 直接套 `agent_spec` 卡在哪

| # | 卡點 | 在程式哪裡 |
|---|---|---|
| 1 | `_entry` 一律寫成 `aos-agent ctl add`、一律出 `body.json` | `agent_spec.compile()` 有 FSM 那段 |
| 2 | `loop.json` 一律指到 `fsm.json`、帶 `ctl`／`state`／`state_flux`；kernel 的 loop 要跑框架站程式 | 同上，寫死的 dict |
| 3 | `description, system, tools, llm` 是必填位置參數；kernel 沒有後三樣 | `compile()` 與 `main()` 的簽名 |
| 4 | `interfaces.json` 一律有 `aos-agent` | `agent_spec_parts.interfaces_json` |
| 5 | hook 格用 agent 的事件表驗，`before_verdict` 會被當成錯 | `agent_spec_parts.hooks_json` 叫 `agentlib.hooks` |
| 6 | `kernel.json` 一份裝很多種東西（旋鈕＋hooks＋endpoints）；`FILES` 只能整份照寫、不驗 | `agent_spec_parts.extra_files` |

**能直接借的**：`write()`（多份暫存檔＋照順序改名）、`main()` 的旗標殼、`defs.home`／`defs.env` 指示詞、`std`／`defs.lib` 的「庫根」、`defs.load` 跑另一支拿欄位的機制。

順帶：不宣告 FSM 的「eca 版」只填內容檔，這條路對 kernel 也走不通，因為它照 `interfaces.json` 的 `aos-agent` 找檔名。

## loop 與 fsm：執行期 vs 編譯期

```
執行期（今天）                          編譯期（今天）
aos-loop  吃任何 loop.json  ── 獨立      loop：沒有宣告函式，compile() 裡寫死
aos-fsm   吃任何 fsm.json   ── 獨立      fsm：defs.fsm / defs.state 驗好整張表，
                                              但只能交給 defs.main 才變成 fsm.json
```

- 執行期它們本來就是積木：procs-kernel 就是「loop＋kernel 程式」；11-18 的玩具手打五次 `aos-exec counter.json` 推一張 fsm 走五步（[aos-compile-1118](../../18/aos-compile-1118/README.md)）。C-74 也把 fsm、tasks 歸在「標準庫」層、loop 歸在「基礎層」。
- 編譯期要讓它們變成單獨單位，最少要：fsm 多一個「寫成一份 `fsm.json`」的出口；loop 多一個宣告（`exec`、`interval_ms`、`on_start`／`on_stop`）。
- 有一件要先想的：單獨編出來的 fsm、loop 寫在哪一夾、叫什麼名字——今天它們跟 agent 同一夾、名字固定。這碰到「資料夾即命名空間」，是新題。

## kernel 要編譯時，還有一件跟 B 題綁在一起

llm kernel 的 endpoint、kernel 的 hook handler 都是**程式**。如果 kernel 也想「直接寫 Python 函數當 endpoint 或 hook」，答案跟 B 題（[06](06-B-現況與差幾步.md)～[08](08-B-原型.md)）同一套。
