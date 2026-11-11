# subagent 改名：工具 agents_children 改叫 subagent，舊名不留

← [2026-11-11](README.md)｜[thinking](../../README.md)

## 使用者原話

11-11 早上：「對了，昨天開發的那個agents_children工具，幫我改名為subagent。」

## 決定

- 工具 `lib/agent/agents_children` 改名 `lib/agent/subagent`：夾名、登記名（`lib/packs/children.json` 裡的鍵與路徑）、錯誤行開頭（程式從夾名取）、`_tooldef.json` 的 Details 指標、knowledge 節點 `aos/agents.json#/agents_children` → `#/subagent`、kernel 假腦 `fake-demo-spawn` 劇本裡叫的工具名、`aos-agent ctl state` 讀的記帳檔位置、`review_round` 認子帳的夾名。proto8 不留舊名、不做相容（舊名＝不認得）。
- 條文（CONCEPTS、NORMS）裡 11-10 的註只加「（11-11 改名 `subagent`）」，現行表與現在式的句子直接改新名；NORMS 附錄 3 舊名對照加一列、附錄 4 持久檔改新位置。thinking 11-10 的紀錄照當時的名字，不改。
- 範圍只到這支工具的名字。沒動、留給使用者裁：包名 `children`（`lib/packs/children.json`）、配額設定檔 `children.json`、`max_children`、`Child*` 錯誤代號、`ls` 末行 `children N/MAX` 與 `json` 輸出的 `children` 鍵、`agents_ctl`、`agent_def`；tooldef 裡講「child agents」的說明句（是在講概念，不是工具名）。（11-11 稍後使用者裁：一起改，見[下一節](#11-11-稍後周邊一起改成-subagent-系)）

## 要重建什麼

- 舊 stack 的記帳檔 `$AOS_STACK/tools/agents_children/children.json` 新工具不讀（新位置 `$AOS_STACK/tools/subagent/children.json`）：帳上的子不再算是誰的——要嘛手動 `aos-agent ctl rm`，要嘛把那份搬到新位置，要嘛整份 stack 重建。
- stack 覆蓋層或 repo 外登記檔裡寫死 `agents_children` 名字或 `lib/agent/agents_children` 路徑的格：重登記成 `subagent`。照範本走 `lib/packs/children.json` 的不用動。
- 腦的 history 裡還有叫 `agents_children` 的舊對話：再叫會得到 `ToolMissing agents_children is not registered`（後面列出現有工具），清掉 history 或讓它自己看新的工具列。

## 11-11 稍後：周邊一起改成 subagent 系

### 使用者原話

隊長把上面「留給使用者裁」那串攤出來，使用者：「隊長那串...一起改吧」。選項框兩題：

- 「工具已經叫 subagent 了，周邊還叫 children 的那一串…要改成什麼？」→ 選「全改成 subagent 系」，說明原文：「包名 subagent、配額檔 subagents.json、max_subagents、錯誤代號 Subagent 開頭、輸出寫 subagents N/MAX。工具說明裡的 child agents 也順成 subagents。」
- 「另外兩支 agents_ctl…和 agent_def…要不要改名？」→「兩支都不動」。

proto8 不留舊名、不做相容（舊名＝不認得）。

### 對照表

| 舊 | 新 |
|---|---|
| 工具包 `lib/packs/children.json`（包名 children）；兩範本 `tools.json` 的 `$override` 那一項 | `lib/packs/subagent.json`（包名 subagent） |
| knowledge 節點 `aos/packs.json#/children`；`aos/_index.json` 列包名的那句 | `aos/packs.json#/subagent` |
| 配額設定 `<定義>/children.json`、`<agent 的 stack>/children.json`（範本 agent-fsm、eca-claude 各一份） | `subagents.json` |
| 鍵 `max_children` | `max_subagents` |
| 記帳檔 `<agent 的 stack>/tools/subagent/children.json`（工具自己的小格，`$AOS_STACK` 指那裡） | `tools/subagent/subagents.json`（跟配額檔照舊同名不同處） |
| `ChildSlotMissing`、`ChildUnknown`、`ChildMissing`、`ChildQueued` | `SubagentSlotMissing`、`SubagentUnknown`、`SubagentMissing`、`SubagentQueued` |
| `subagent` 的輸出：add 尾巴 `; children N/MAX`、ls 末行 `children N/MAX`、`json` 鍵 `children`／`max_children`、滿額訊息 `of max N children` | `; subagents N/MAX`、`subagents N/MAX`、`subagents`／`max_subagents`、`of max N subagents` |
| `aos-agent ctl state`／`self_state` 的類別 `children`（總覽 `N/MAX children (…)`、細節空的 `(no children)`、json `{count, max_children, children}`） | 類別 `subagents`（`N/MAX subagents (…)`、`(no subagents)`、`{count, max_subagents, subagents}`） |
| 工具說明、HELP、knowledge 裡講 subagent 那層的 child agents／your children／a child | subagents／a subagent |
| 測試檔 `lib/agent/subagent/tests/test_children.py`（類 `Children`） | `test_subagent.py`（類 `Subagent`） |

代號只換主詞、結尾照舊（C-54 的結尾表是條文題，這次不碰）：`…SlotMissing`、`…Unknown`、`…Missing` 照舊；`ChildQueued` 的結尾 `Queued` 本來就不在 C-54 那六種裡，照原樣改成 `SubagentQueued`，合不合 C-54 留給條文。主詞用單數 `Subagent`：四個代號講的都是「一隻」（滿額＝沒格給下一隻、那隻不認得／不在／還在排隊），不是 `Subagents`。

程式內部名字：`_entry` 的 `max_children()`／`MAX_CHILDREN_DEFAULT`／`write_children`／`children_path`／`my_child` 改成 `max_subagents()`／`MAX_SUBAGENTS_DEFAULT`／`write_book`／`book_path`／`my_subagent`；ctl state 的 `part_children` → `part_subagents`（類別名從函數名取，一定要改）。

### 沒改的（逐類）

- 跟 subagent 無關的 children：`ls`／`stat` 的資料夾子項數 `counter_children` 與 long 的 `children N`、`view` 的 `children`（JSON 子項）；knowledge_read／knowledge_fs 的 `children:` 段與 knowledge_write 的 `ChildrenExist`（知識樹的資料夾不空，不是子 agent）；`lib/aos/measure`、`review_round`、`metainfo_check`、`shell_report` 的呼叫樹 `children`；aos-json help 的 large children；daemon 舊名 `children`→`loops`→`procs`（C-54、abbr、附錄 3/02）；s6-runit notes、extras 檢查腳本、aos-daemon 的子 proc；各工具 `child = subprocess.Popen` 這類行程的 child。
- 共用模組 `lib/observed_children.py`（`copy_child`／`take_child`／`clear_child`、`.observed_child.json`、tool 行的 `child` 欄）與 thought 測試 `test_observed_children.py`：管「叫的人抄子 stack 的公開帳」，thought 與 subagent 都用，是 N-68 的機制名，不是 subagent 的名字。
- `thought` 的子：工具小格 `children/<子名>/` 與說明裡的 throw-away child agent——thought 生的是用完即走的子，不是 subagent 那層的「我的 subagent」，不改（施工員代定，可翻案）。
- 歷史：`thinking/`（含上一節與 11-10 的紀錄）、`wf/session_logs`、`wf/workflows/*/reports`、`proto8/feedback/*.jsonl`；條文講 11-06／11-10 舊事的句子只加「（11-11 改名 …）」註（C-42 兩道關那句、N-67 ⑦ 的 children.json）；NORMS 附錄 3 上一列原話照留、加一列；附錄 4 兩列改新名、note 記舊名。
- 生成冊 `wf/workflows/common/code-map/` 還寫舊檔名：commit 前跑 `codemap_gen.py --apply` 重生。

### 要重建什麼

- **定義**：舊定義（從範本抄出去的）裡的 `children.json` 改名 `subagents.json`，裡面的鍵 `max_children` 改 `max_subagents`。不改＝當沒設，配額退回 4（舊鍵不認、不報錯）。
- **stack 的配額覆蓋**：`<agent 的 stack>/children.json`（只放改過的鍵那份）同上改名改鍵。
- **stack 的記帳檔**：`<agent 的 stack>/tools/subagent/children.json` 新程式不讀（新位置同夾的 `subagents.json`）。帳上的子不再算是誰的：把那份改名成 `subagents.json`，或手動 `aos-agent ctl rm` 舊的子，或整份 stack 重建。更早的 `tools/agents_children/children.json` 照上一節。
- **覆蓋層與 repo 外的登記檔**：`$override` 串裡寫 `/lib/packs/children.json` 的（舊定義的 `tools.json`、stack 覆蓋層、repo 外自己寫的）改成 `/lib/packs/subagent.json`；不改＝那一項指到不存在的檔。
- **腦的 history**：舊對話裡看過 `ChildSlotMissing` 之類的舊代號、`children N/MAX` 的，照新說明讀；self_state 叫 `{"parts": ["children"]}` 會得到 ArgumentsBad（不認得的類別），改叫 `subagents`。
- **試驗場**：這次改名後，試驗場的定義（配額檔 `children.json`、`tools.json` 的 `$override` 包名）與 stack（記帳檔 `tools/subagent/children.json`、stack 那份配額覆蓋）都要重刷；刷新腳本在 [playground/01](playground/01-公司刷新與驗收.md)（腳本本身照範本整份重抄定義，沒寫死包名與配額檔名，驗收表那列 `children 1/4` 改看 `subagents 1/4`）。
