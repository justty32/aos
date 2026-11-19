線 aos-check-refs-1119（11-19）：`agent_def check` 補查「叫的東西在不在」——工具路徑、會被執行的程式、腦設定型別；`--compile` 不動。

← [11-19 日索引](README.md)｜出處：[aos-vs-c-1119 使用者已答](aos-vs-c-1119/README.md#使用者已答11-19-下午選項框)、缺口 [G1](aos-vs-c-1119/02-缺口清單.md)

## 先講結論

**寫錯的工具路徑、不在的格程式、型別錯的腦設定，現在 `agent_def check` 會報出來（DefBad、退 1）；`agent.py --compile` 跟以前一樣不查**——使用者 11-19 下午選項框選「只放進檢查指令」：「編譯不管，跑 agent_def check 才查。要記得跑。」

實際的檢查寫在 `defs` 工具（`agent_def check` 就是轉叫它），新檔 `proto8/py/tools/aos/defs/refs_check.py`；規則照執行時那幾支讀法，細則在它的檔頭與 [defs README](../../../py/tools/aos/defs/README.md)。

## 現在多查哪些（各一行實際輸出）

| 查什麼 | 照誰的規則 | 例（乾淨複本裡實跑） |
|---|---|---|
| 工具路徑解不開／不在 | 交給 `aos-tools ls -l`（agent 跑時拿清單的同一支，`$override` 照疊） | `tool ghost cannot be used (PathMissing: its path does not exist): path {"$env": "AOS_HOME", "$path": "/lib/tools/base/nonexist"} resolves to …/lib/tools/base/nonexist (tools.json#/tools/ghost); when the agent runs it is left out of the tool list` |
| 狀態格的程式不在 | 單子 cwd 照 aos-exec（沒寫＝fsm.json 的資料夾） | `fsm.json#/states/idle/exec/argv/1: script "nocell.py" does not exist (looked for nocell.py)` |
| loop 的 exec、on_start、on_stop，入口 argv | 入口 `aos-agent.entry` → `aos-loop` 設定檔 → exec 指到的狀態表 | `loop.json#/exec: target "table.json" does not exist (looked for table.json)` |
| hook 的 handler | 從 hooks 檔的資料夾算，補找 `.json` | `hooks.json#/hooks/gone/handler: handler "hooks/gone" does not exist (looked for hooks/gone)` |
| 腦設定型別 | `templates/agent-fsm/llm_settings.py` 的 `body_fields`（brain.py 用的同一份） | `temperature in llm.json must be a number, not "hot"` |
| 明顯無效的值 | 轉型之後加三條範圍 | `llm.json: max_tokens must be at least 1, not -5` |
| 不在 `llm_keys` 的鍵 | interfaces.json 的 `llm_keys` | warning：`llm.json: key "colour" is not one of llm_keys in interfaces.json (…), so the body does not read it` |

查不了的照實說，放進新的 `warnings`（跟 `problems` 同形狀、有才出現、不讓 check 失敗）：

- 指示詞的變數這裡沒設：`fsm.json#/states/idle/exec/argv/1: script {"$env": "AOS_CHECK_REFS_NOT_SET", "$path": "/cell.py"} not checked: environment variable AOS_CHECK_REFS_NOT_SET is not set here (it is read when the agent runs)`；工具表也一樣（`tool paths in tools.json not checked: …`）。以前疊 `$override` 的表碰到沒設的變數會報成 problem，現在改成 warning。
- 指令名不在這裡的 PATH：`command "…" is not on PATH here (it may be where the agent runs)`。
- `aos-tools` 不在 PATH（沒疊 `$override` 的表；疊了的照舊是 problem）。
- `AOS_STACK`、`AOS_CO` 只在執行時有，不查也不提；`AOS_CD`／`AOS_CF` 用寫它的檔的資料夾／檔本身（執行時 aos-loop、aos-fsm 給的就是這個）。`AOS_HOME` 沒設時用放這份 lib 的資料夾（跟原本 tool-packs 合併同一條）。

## 沒查的（與理由）

- **model 名對不對**：要問 kernel 的 endpoint 包才知道，check 不連 kernel。`"model": "no-such-brain"` 照樣過。
- **argv 其他位置的字串**：命令列是任意的，分不出哪個字是檔名。只查 argv[0]、`python3`／`bash` 等直譯器後第一個不是旗標的字（`-m`、`-c`、`-e` 之後不查）、`aos-loop`／`aos-fsm` 的設定檔、任何位置寫成 `{"$env": "AOS_HOME", "$path": …}` 的。
- **`$ref` 等只有 `$env`、`$path` 以外寫法的指示詞**：不解、不查。
- **stack 裡疊上去的那份**（self_tools、self_llm 改的）：check 只看定義。
- **`AOS_WS` 這類**照 check 當下的值解；`agent_def` 被 agent 叫時那是叫的人的工作區，跟被查的 agent 跑時的工作區不一定一樣（aos-vs-c G3 的搬家情形），結果可能不同。
- **定義夾自己帶的 `llm_settings.py`**（agent-fsm 抄出來、格寫成本夾的）：不執行定義夾裡的程式，一律用 std 那份規則。
- eca 身（`screen`）沒有 `entry`，只查工具、hook、腦設定。

## 修前修後

用 aos-vs-c 的 `repro/a/bodies/e2、e6、e7` 三份（e7 的庫路徑換成本線暫存夾）抄 `agent-python` 骨架、`--compile`、`agent_def check`：

| | 修前（HEAD 474fc4cf6） | 修後 |
|---|---|---|
| e2（`defs.home("/lib/tools/base/nonexist")` 的工具） | `{"problems": []}` 退 0 | 1 條（tool ghost PathMissing）退 1 |
| e6（`temperature: "hot"`、`max_tokens: -5`） | `{"problems": []}` 退 0 | 2 條 退 1 |
| e7（格 `["python3", "nocell.py"]`、相對路徑工具 `relative/not/there`） | `{"problems": []}` 退 0 | 2 條 退 1 |
| 骨架照抄 | `{"problems": []}` | `{"problems": []}`（沒有 warning） |

三份的 `--compile` 修前修後都退 0（沒動）。整棵 `templates/` 跑 `defs check`，新檢查沒有多報任何一條（原本就有的 7 條是 judge-llm、kernel 等不是 agent 的夾缺 README／interfaces，跟這次無關）。

## 測試

- `py/tools/aos/defs/tests`：27 個（新 8 個：工具路徑不在、變數沒設＝warning、沒有 aos-tools＝warning、格／loop／hook 的程式不在、跟著 loop 找狀態表與入口、變數沒設與 PATH 外的指令、腦設定型別與範圍、四份範本照抄沒有任何 finding）。舊的「抄到沒有 cmd/ 的樹」那個測試，假的 home 現在要多抄 `tools/agent/do_task` 與 `templates/agent-fsm/llm_settings.py`——因為 check 真的會查到 gadgets 包裡的 do_task 不在。
- `py/tools/agent/agent_def/tests`：30 個（新 1 個：抄 agent-fsm、加一支寫錯的工具、刪 wait.py、`temperature: "hot"` → 3 條 DefBad）。
- 另跑 `test_tool_spec`、`test_tool_io_metainfo`、`apps/tools/test_metainfo_tooldef`、`apps/agent/test_state_parts` 都過。
- 都在 `git archive HEAD` 抄出的乾淨複本（`~/.aos/scratch/aos-check-refs-1119/src`）疊改動、複本裡 `install.py` 後跑；所有指令先 unset `AOS_*`；只用假腦、沒起 stack。repo 裡沒跑 `install.py`。

## 文件（第二筆，等線 aos-bpfix-1119 交了骨架與教學才改）

- 骨架 `templates/agent-python/README.md`：開頭「Static and dynamic linking」那點與「Linking tool packs」兩處，「next start」「every time the agent starts」改成每次問腦前讀、不用重起（實測與 `--compile` 自己印的話一致，aos-vs-c G6）；兩處都補「靜態連結只固定名單，工具程式、`_tooldef.json`、格程式仍從 `$AOS_HOME`（或庫）讀，升級會影響已編譯的 agent」；「Then check the folder」那句補「只有 check 查叫的東西在不在」。
- 教學 `04-寫原始碼`「檢查這夾定義」補一段「check 才會查叫的東西存不存在」；`06-接著開發-2` 的 6.4 結論句「agent 每次起來才讀」改成每次問腦前讀，並加一點「靜態連結只固定工具名單」。
- C-87 的 11-19 加註只加字：在「要改名的包只能靜態連結」那個括號裡接一句「兩種連結都只固定有哪些工具、各在哪條路徑……靜態連結不等於之後庫怎麼改都不影響這隻」。原文一字未動。
- 交之前用本線的 check 跑過 bpfix 交後的骨架（帶新的 `hooks.json`）：`{"problems": []}`。

## 沒做到、沒驗到

- 沒掛起 agent 實跑對照「check 報的」與「執行時真的停／少工具」是同一件事；對照靠 aos-vs-c 報告的實跑結果與兩邊用同一支讀法（aos-tools、llm_settings）。
- eca 身的定義只跑了「範本照抄沒有 finding」。
