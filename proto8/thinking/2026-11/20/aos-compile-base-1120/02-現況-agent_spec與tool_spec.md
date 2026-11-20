現況盤點之二：兩支編譯程式 agent_spec（agent.py 用）與 tool_spec（tool.py 用）內部哪些是同一件事、共用了多少程式、哪些是各自專屬。

← [README](README.md)｜上一份：[01](01-現況-定義夾有哪幾種.md)｜下一份：[03 kernel 與 loop、fsm](03-A-kernel與loop-fsm.md)

## 先講結論

- **共用的程式是 0 行**：`agent_spec` 四支（`agent_spec.py`、`_parts`、`_lib`、`_load`，共 1264 行）跟 `tool_spec.py`（300 行）互不 import。
- **同一件事寫了兩份**的大約六件，粗估 50 行上下：報錯的例外類別、從檔名推名字、`--compile`／`--dry-run` 的旗標殼、暫存檔＋改名的寫檔、說明字串的檢查、「寫錯先記著、最後才報」的做法。
- 兩支最大的差別不在編譯，在**執行期**：`tool.py` 編譯完自己就是那支工具（沒給旗標＝照宣告驗參數、叫 `run`）；`agent.py` 只在編譯時跑，執行期沒人叫它。

## 流程逐步對照

| 步驟 | agent_spec | tool_spec | 共用？ |
|---|---|---|---|
| 找 aos 套件（骨架開頭幾行） | `$AOS_HOME/lib` 放最前 | `$AOS_HOME/lib` 放最後（自己旁邊優先） | 各一段，順序還不同 |
| 收宣告 | 大寫常數＋最後一行 `defs.main(...)` | 大寫常數＋最後一行 `ts.main(run, ...)` | 同一個寫法，各寫各的 |
| 寫錯怎麼記 | 小函式回 `{"kind": "bad"}` | `param()` 回 `{"bad": ...}` | 同一個點子、兩種形狀 |
| 報錯 | `agent_spec_parts.SpecBad`，經 `flags.die` 印一行 | `tool_spec.SpecBad`（另一個類別），經 `tool_io.die` | 兩個同名不同類別 |
| 推名字 | `agent.py`＝夾名，否則檔名 | `tool.py`＝夾名，否則檔名 | 一模一樣，各寫一次 |
| 檢查 | 工具格照 `aos-tools` 的規矩；hook 格**直接叫執行期那支** `hook_run.validate_entry` | 參數 schema 自己檢查；`metainfo_problems` | agent 這邊已經跟執行期共用驗法 |
| 展開 | `std.pack`／`defs.lib` 展開包、`defs.load` 衍生、`defs.fsm(base.FSM, ...)` 換格 | 沒有 | agent 專屬 |
| 連結選項 | `--static`（預設）／`--dynamic`、`link=` | 沒有 | agent 專屬 |
| 算產物 | `compile()` 回 `{檔名: 內容}` | `tooldef()`、`metainfo()` 各回一個 dict | 都是「先算、不寫」 |
| 寫檔 | `write(夾, 檔們)`：多份全寫成暫存檔、照順序改名、`_metainfo.json` 只合自己的鍵、README 不在才寫 | `write(位置, td, mi)`：資料夾＝兩份暫存檔＋改名；`檔.json#/指標`＝叫 `aos-json set` | 兩份寫法 |
| 旗標 | `--compile [夾]`、`--dry-run`、`--help`、`--static`／`--dynamic` | `--compile [位置]`、`--dry-run`、`--tooldef`、`--metainfo`；沒旗標＝執行 | 前兩個 11-19 才對齊名字，程式仍各一份 |
| 執行期 | 沒有 | 驗參數、補預設、叫 `run`、例外轉 `RunFailed`（帶行號） | tool 專屬 |

## agent 專屬的（要搬到 kernel 也不一定合用）

- 骨架四份（`_entry`、`body.json`、`loop.json`、`interfaces.json`）寫死在 `compile()` 裡。
- 參數表固定：`compile(description, system, tools, llm, fsm=None, meta=None, interfaces=None, hooks=None, files=None, …)`。
- 保留檔名表（`RESERVED`、`RUNTIME_FILES`）是 agent 的檔名。
- 不宣告 FSM 的 eca 版：照現有 `interfaces.json` 的 `aos-agent` 找檔名。

## 工具專屬的

- 參數 schema（`param()`）、N-68 的 metainfo 預設值。
- 掃原始碼裡的 `fail("代號", …)` 收錯誤代號。
- 「同一支檔又是原始碼又是程式」：`tool.py` 編譯只寫說明書（tooldef／metainfo），程式就是它自己。

## 這張表看得出的一件事

`agent_spec` 已經在兩處「跟執行期共用一份規矩」：hook 格直接叫 `hook_run` 驗，工具名用 `aos-tools` 的同一個正規式。如果要有通用底座，「驗法跟執行期共用、不另抄一份」這條在 agent 這邊是現成的先例；`tool_spec` 的 schema 檢查則跟 `aos-tools` 讀 tooldef 的檢查是兩份。
