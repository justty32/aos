把 `agent-fsm` 執行期用的檔搬出 `templates/`、放進 `lib/` 的設計：現在誰回範本拿什麼（逐檔）、新家放哪（三種放法與推薦）、範本與兩種定義之後長怎樣、程式改哪幾行。

# 06b 執行期的東西搬進 `lib/`

← [06 入口](06-三分的施工設計.md)｜使用者 11-23 第 3 件選 a：趁這次搬，讓範本只是給人抄的來源

## 結論

1. **真的被別的定義回來拿的只有 `agent-fsm` 的九個檔**：四支格、四支共用模組、一份 hook 點的宣告。`eca-claude` 沒有這種檔。
2. **推薦新家：原始碼 `py/aos/apps/agent_fsm/`，`install.py` 照舊整個 `py/` 抄成 `lib/`，裝好在 `lib/aos/apps/agent_fsm/`**。`install.py` 不用改。
3. **範本 `agent-fsm` 自己也改成動態連結**（夾裡不再有 `.py`）。格程式全 repo 只剩一份。
4. 不新增任何機制：動態連結的寫法（`fsm.json` 的 `argv` 寫 `$AOS_HOME` 指示詞）reviewer 從 11-10 就在用。

## 現在誰回範本拿什麼

| `templates/agent-fsm/` 的檔 | 誰在用 | 怎麼指的 |
|---|---|---|
| `idle.py`、`brain.py`、`wait.py`、`act.py`（四格） | 每一隻動態連結的 agent，每一格都跑 | `fsm.json` 的 `argv`：`["python3", {"$env": "AOS_HOME", "$path": "/templates/agent-fsm/idle.py"}]`。來源：`std.fsm()` 編譯出來的（`agent-python` 範本、任何 `agent.py`）、`reviewer/fsm.json`、`start-api/agents/ann/fsm.json`；別的專案有 arena_cheater 五份、ops-notes 的 `patrol` 一份 |
| `cell_common.py`、`atomic_file.py`、`compact.py`、`llm_settings.py` | 四格 import | 格把自己所在的夾放在 `sys.path` 最前面，再放 `$AOS_HOME/lib` |
| `llm_settings.py` | 另被 `py/tools/aos/defs/refs_check.py` 第 292 行按路徑載入 | 寫死 `templates/agent-fsm/llm_settings.py` |
| `hooks.json`（這幾格會發哪些 hook 點） | `interfaces.json` 的 `hooks` 第二項 | 編譯出來的寫 `/templates/agent-fsm/hooks.json`（`agent_spec_parts.py` 第 23 行）。宣告只是參考：`py/aos/hook_point.py` 檔頭寫明 `aos-hook fire` 與引擎不讀它，檔不在 agent 照跑，但檢查工具與測試會報 |
| `hookeds.json`（出廠掛的那組 hook） | 只在**編譯時**：`std.hooks("agent-fsm")` 讀一次、靜態連結進新定義 | `agent_spec_lib.py` 第 178～195 行 |
| 其餘（`system.txt`、`tools.json`、`llm.json`…） | 沒有人回來拿 | 定義自己帶 |

**`eca-claude` 有沒有同樣情形：沒有。**

- `compact_hook`：`cli.json` 寫的是 `python3 "$AOS_CLI_DEF/compact_hook"`，指的是「這隻的定義夾」，不是範本。抄走的定義帶自己那份。
- eca 的 hook 點宣告早就在 `lib/aos/apps/eca/hooks.json`；畫面入口叫的是 `bin/` 的 `aos-eca-screen`。
- 它跟範本位置有關的只有三件，都不是「別的定義回來拿」：活樹有 11 列**把範本夾直接當定義掛**；`std.hooks("eca-claude")` 編譯時讀它的 `hookeds.json`；agent 在 stack 裡自己那份 `tools.json` 的 `$override` 記著 `…/templates/eca-claude/tools.json`（這棵樹的 `eca-aos` 就有一份）。這三件靠改路徑解決（[06e](06e-切換步驟.md)），不搬檔。

## 新家放哪：三種放法

| | 放法 | 好處 | 代價 |
|---|---|---|---|
| **甲（推薦）** | `py/aos/apps/agent_fsm/` → `lib/aos/apps/agent_fsm/` | 有先例：eca 的 hook 宣告在 `lib/aos/apps/eca/hooks.json`、loop 的在 `lib/aos/apps/hook/loop_hooks.json`，「一種身體的程式放 `aos/apps/<身體>/`」是現成的慣例；`install.py`、code map 的生成設定都不用加規則 | 夾名用底線（`agent_fsm`），跟範本名 `agent-fsm` 差一個字元；這八支是「當腳本跑」的，放在套件夾裡風格不完全一樣 |
| 乙 | `py/cells/agent-fsm/` → `lib/cells/agent-fsm/` | `lib/` 底下跟 `packs/`、`tools/` 並排，std 的三種東西都在 `lib/` 第一層，路徑短 | `lib/` 多一種頂層夾：code map、`_index.json` 的生成設定要加規則，知識庫要多解釋一個詞 |
| 丙 | 原始碼留在範本，`install.py` 抄一份進 `lib/` | 改的檔最少 | 跟「搬出 `templates/`」相反；`install.py` 得認得範本位置 |

甲裡替使用者做的小選擇：夾名叫 `agent_fsm`；要不要放 `__init__.py` 由核心程式位子照 `py/tests` 的版面檢查決定（格是按路徑跑的腳本，不需要）。

## 八支 `.py` 自己要不要改

**原樣搬，只改字**（四支格的 usage 與註解裡的 `a cell of templates/agent-fsm`）。它們找共用模組的方式是「自己所在的夾」，搬到哪都成立；錯誤行開頭的 `agent-fsm:` 是身體的名字，不改。使用者 11-20：「反正程式能跑就別動他」。

## 範本與兩種定義之後長怎樣

**動態連結**（指回 lib；範本 `agents/agent-fsm`、`std.fsm()` 編出來的、`reviewer`、`start-api` 的 ann、arena_cheater 與 ops-notes 那六份都是這種）：

```json
fsm.json        "idle": {"exec": {"argv": ["python3", {"$env": "AOS_HOME", "$path": "/lib/aos/apps/agent_fsm/idle.py"}]}, "next": {"0": "think", "10": "idle"}}
interfaces.json "hooks": [{"$env": "AOS_HOME", "$path": "/lib/aos/apps/hook/loop_hooks.json"},
                          {"$env": "AOS_HOME", "$path": "/lib/aos/apps/agent_fsm/hooks.json"}]
```

**靜態連結**（整份抄走；paper_readings 的 `drafter`、`checker` 現在就是這樣，**這次不用動**）：夾裡自己有八支 `.py` 與 `hooks.json`，

```json
fsm.json        "idle": {"exec": {"argv": ["python3", "idle.py"]}, "next": {"0": "think", "10": "idle"}}
interfaces.json "hooks": [{"$env": "AOS_HOME", "$path": "/lib/aos/apps/hook/loop_hooks.json"}, "hooks.json"]
```

要做一份靜態的：抄範本，再從 `$AOS_HOME/lib/aos/apps/agent_fsm/` 抄那九個檔進去，把上面兩處改成相對檔名。只想改一格也一樣（那支加它 import 的共用檔）。寫進範本的 README，不做新工具。現況提醒：靜態的格還是 import `$AOS_HOME/lib` 的 `aos.*`，lib 的介面變了它會壞。

**範本 `agent-fsm` 為什麼不留一份 `.py`**：留了就是兩份 2,100 行要盯著一樣。使用者 11-20 看 ann 時也說：「這些範本的.py，感覺都是一些基礎的東西，感覺沒有要覆蓋的話，就應該可以從env:AOS_HOME裏面直接取，這樣ann底下會很乾淨。」這仍是替他做的選擇（另一條路：範本留副本、加一條測試盯兩份一字不差）。

**`hookeds.json` 留在範本**：`std.hooks(名)` 是「編譯時把那個範本出廠的 hook 抄進來」，本來就是抄範本；改成去 `templates/agents/<名>/hookeds.json` 讀。編譯好的定義自己帶一份，範本以後再搬也不影響活樹，只要改這一行程式。

## 程式改哪幾行（核心程式位子）

| 檔 | 改成 |
|---|---|
| `py/aos/agent_spec_lib.py` `Std.fsm()`（第 202 行） | `_join(self.root, "lib/aos/apps/agent_fsm/%s.py" % prog)` |
| 同檔 `Std.hooks()`（第 178～195 行） | `self._where("templates/agents", call)`；三句錯誤訊息與來源標記改成 `templates/agents/%s/hookeds.json` |
| 同檔檔頭、`Std` 的說明、第 17 行註解 | std 的固定位置：包 `lib/packs`、工具 `lib/tools`、格 `lib/aos/apps/agent_fsm`；出廠 hook 編譯時從 `templates/agents/<名>/` 抄 |
| `py/aos/agent_spec_parts.py` 第 23 行 | `{"$env": "AOS_HOME", "$path": "/lib/aos/apps/agent_fsm/hooks.json"}`（第 15 行註解跟著改） |
| `py/tools/aos/defs/refs_check.py` 第 292 行 | `os.path.join(home, 'lib', 'aos', 'apps', 'agent_fsm', 'llm_settings.py')`（第 16、289 行說明跟著改） |
| `py/tools/agent/agent_def/_entry` 第 98 行 | `os.path.join(home, "templates", "agents", name)`；第 122 行列出的就變成 `agents/` 底下有 `interfaces.json` 的夾（`kits` 沒有，不會被列） |

其餘寫死的位置（`tools_def`、`kit.py`、前端、工具說明）只是換路徑，列在 [06c](06c-要改的每一處與分工.md)。
