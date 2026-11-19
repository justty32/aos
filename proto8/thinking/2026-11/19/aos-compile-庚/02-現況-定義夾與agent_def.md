# 現況二：一個 agent 定義夾今天有哪些檔、`agent_def` 的 new 與 check 各查什麼、還有誰會改定義

← [README](README.md)｜上一份：[01-現況-工具版tool_spec](01-現況-工具版tool_spec.md)｜下一份：[03-agent-py-長相](03-agent-py-長相.md)

讀 HEAD `2f7e94d5a`；`agent_def check` 對三個範本各實跑一次（唯讀），都回 `{"problems": []}`。

## 先講結論

1. 定義夾的檔分三種：**骨架**（幾份很短的 json，把東西接起來）、**內容**（system、工具、腦設定）、**肉**（格的 Python、畫面程式）。庚要生的是前兩種，肉不生。
2. `agent_def check` **只查五樣**：夾名、README 第一行、`_metainfo.json` 的 summary、`interfaces.json`、它指到的工具檔與腦設定檔。**`fsm.json`、`loop.json`、`body.json`、`_entry`、`hooks.json` 它完全不看**——狀態機寫錯要到跑起來才知道。
3. **kit 不改定義**（寫進 stack），所以 `ctl set-def --kit` 不會碰到生成物。會改定義本身的正規指令只有 `agent_def` 的 `tools`／`llm`／`system` 與 `new`（抄完會改寫兩份檔）。

## 定義夾有哪些檔

檔數不含 `README.md`；`screen/` 整夾算一個。

| 檔 | agent-fsm（19 檔） | reviewer（10 檔） | eca-claude（11 檔） | eca-pi（9 檔） | 種類 |
|---|---|---|---|---|---|
| `_entry` | 掛上 daemon 的單子 | 同 | `["aos-loop","loop.json"]` | 同 | 骨架 |
| `body.json` | `aos-loop loop.json` | 同 | 無 | 無 | 骨架 |
| `loop.json` | 每拍跑 `fsm.json` | 同（沒有 on_start） | 每拍跑 `aos-eca-turn` | 同 | 骨架 |
| `fsm.json` | 四格，格寫相對路徑 | 四格，**借** agent-fsm 的格 | 無 | 無 | 骨架 |
| `interfaces.json` | 其他檔叫什麼 | 同（沒有 hooks、history） | 多 `screen`、沒有 `entry` | 同 | 骨架 |
| `tools.json` | 疊 11 個工具包 | 11 個單獨的工具 | 疊 8 包、拿掉 1 個 | 同 | 內容 |
| `llm.json` | `{}` | 只有說明 | `{"model":"sonnet"}` | `{}` | 內容 |
| `system.txt` | 1.3 KB | 2.4 KB | 沒有檔（＝空） | 沒有檔 | 內容 |
| `hooks.json` | 4 個 hook | 無 | 6 個 | 4 個 | 內容 |
| `subagents.json` | 有 | 無 | 無 | 無 | 內容 |
| `_metainfo.json`、`README.md` | 有 | 有 | 有 | 有 | 給人與檢查看 |
| 格的程式 `idle.py` 等 7 支 | 有（105 KB） | 無 | 無 | 無 | 肉 |
| `cli.json`、`screen/`、`compact_hook`、`tools_sub.json` | 無 | 無 | 有 | 部分 | eca 專用 |
| `ladder.json` | 無 | 有 | 無 | 無 | 這隻自己的設定 |
| `.env` | 範本都沒有，選用，agent 起來時讀 | | | | 機器上的私事 |

執行中才長出來的東西（歷史、佇列、`stage.txt`、kit 與 `self_*` 寫的「自己那份」）都在 stack，不在定義夾。

## `agent_def` 在哪、各做什麼

原始碼：`proto8/py/tools/agent/agent_def/_entry`（主體）、同夾 `def_edit.py`（tools／llm／system 三個細動作）；`check` 轉叫 `proto8/py/tools/aos/defs/`（`_entry` 與 `catalog.py`）。

### new（把範本整夾抄成新定義）

做的事：整夾複製（略過 `__pycache__`）→ 把工具檔裡的相對路徑換算成從新位置算（`rebase_tools`）→ 在 `_metainfo.json` 寫 `lineage`（從哪抄來）→ 改名到位。先寫暫存夾，失敗就清掉。

| 錯誤代號 | 什麼時候 |
|---|---|
| `ArgumentsBad` | `template` 與 `from` 兩個都給或都沒給；範本名含 `/` |
| `DirectiveBad` | `AOS_HOME` 沒設；`from` 的指示詞解不出路徑 |
| `DefMissing` | 沒有這個範本（訊息列出有哪些：`templates/` 下**有 `interfaces.json` 的夾**）；`from` 不是資料夾 |
| `DefExists` | 目的地已經在 |
| `DefBad` | 抄來的 `interfaces.json`、工具檔、`_metainfo.json` 讀不懂 |
| `MkdirFailed`、`WriteFailed` | 建夾、複製、改寫、改名失敗 |

### check（查一份定義）

`agent_def check` 自己只做轉叫：路徑不是資料夾＝`DefMissing`；起不來＝`LaunchFailed`；超過 60 秒＝`CommandFailed`；其餘把下層的錯誤行接成自己的。真正的檢查在 `defs/catalog.py` 的 `check()`，**每條問題沒有自己的代號**，只是 `problems` 清單裡的一句英文，整體代號一律 `DefBad`：

| 查什麼 | 不過時的那句（開頭） |
|---|---|
| 夾名 | `definition folder name … must match [a-z0-9_-]+` |
| `README.md` | `README.md first line must be nonempty`（或讀不到的系統原因） |
| `_metainfo.json` | `_metainfo.json must contain a nonempty summary` |
| `interfaces.json` | 讀不到／不是物件；`aos-agent must be an object` |
| 工具檔 | `aos-agent.tools must name a file`；`tools must contain an object`；`each tool must declare a path`；`tool env must be an object`；有 `$override` 時交給 `aos-tools ls -l` 合併，合不起來＝`cannot merge …` |
| system 檔 | `aos-agent.system must name a text file by a relative path inside the definition`（檔可以不在） |
| 腦設定檔 | `aos-agent.llm must name a file`；`model in llm.json must be a string` |

另一個代號 `RootMissing`（根不是資料夾）到不了 `agent_def check`（它先擋成 `DefMissing`）。**`defs` 這支所有動作都是唯讀**（它的 README：「所有 op 只讀」），也拿來查整棵定義樹。

### tools／llm／system（直接改定義）

`def_edit.py`：照 `interfaces.json` 找到那份檔，`tools` 轉叫 `aos-tools --file`、`llm` 轉叫 `aos-json set`／`del`、`system` 整份重寫。代號：`ToolsMissing`／`LlmMissing`／`SystemMissing`（沒宣告那份檔）、`DefBad`、`ArgumentsBad`、`OpUnknown`，加上下層的 `ToolExists`、`ToolMissing`、`KeyMissing`。改完印一句「agents that use it see this from their next brain call」。

## 還有誰會改定義夾裡的檔

| 誰 | 改哪裡 | 會不會碰到生成物 |
|---|---|---|
| `agent_def tools`／`llm`／`system` | 定義的工具檔、腦設定檔、system 檔 | **會** |
| `agent_def new` | 新抄出來那份的工具檔（換算路徑）與 `_metainfo.json`（lineage） | **會** |
| 人用編輯器、agent 用 `write`／`json_set` | 任何檔 | **會** |
| `ctl add --kit`、`ctl set-def --kit` | **stack** 裡「自己那份」；說明寫明「the definition is not changed」 | 不會 |
| `self_tools`、`self_llm`、`self_system`、`self_hook` | stack | 不會 |
| `ctl set-def NAME DEF` | daemon 表上那一列的 def 欄 | 不會（只是換指到哪一夾） |

## 定義是什麼時候被讀的

- 工具檔、腦設定檔、system 檔：每次問腦之前讀（`def_edit` 的說明這樣寫）。
- `fsm.json`：每一拍 `aos-fsm` 重新讀整張表並查一遍；表不合＝`CfgBad`；`stage.txt` 記的狀態不在表上＝`StateUnknown`。
- `loop.json`：照 aos-loop 的說明是起跑時解一次。**這條與上一條的「停掉」行為我只讀了說明，沒有實測。**
