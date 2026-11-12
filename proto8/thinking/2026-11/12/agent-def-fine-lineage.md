# agent-def-fine-lineage：agent_def 加「細的」定義動作與血統（Q09，11-12）

← [2026-11-12](README.md)｜[thinking](../../README.md)｜前情 [agents-split § 之後可加](../10/agents-split/README.md#之後可加)

## 使用者原文

- 11-12：「Q09:b-都做，除了移除子(兩者不要耦合)」
- Q09 的三項＝agents-split「之後可加」：(1)「細的」定義動作（設 system prompt、設腦、加減工具寫進定義）；(2) `agents_children`（現名 `subagent`）對 rm 後留下的 stack 直接清掉；(3) 血統。
- 前情（11-10 晚，agents-split）：「第二塊：同樣拆兩塊，一個創造或修改定義，一個改自身。啥定義都可改，只要有權限，包括改自身定義。粗細的話，先做粗的，細的之後慢慢添加，也可以分開做。血統記錄...可以先不做。」

## 決定

- 做 (1) 與 (3)，不做 (2)；兩項都跟 rm 不耦合：rm 子時不碰血統、不順手清別的。

## 結論（已施工）

**1. 細的定義動作：`agent_def` 多三個 op——`tools`、`llm`、`system`。**

```json
{"op": "tools",  "path": "defs/helper", "args": {"op": "add", "path": "tools/math"}}
{"op": "llm",    "path": "defs/helper", "args": {"op": "set", "settings": {"model": "fake"}}}
{"op": "system", "path": "defs/helper", "args": {"op": "set", "text": "You are ..."}}
```

- `args` 就是 self_tools／self_llm／self_system 收的那份，目標換成 `path` 那份**定義**（不是正在跑的 stack）；寫法跟 `subagent` 的 `tools`／`llm`／`system`（`{name, args}`）同一個樣子，腦學一次三處通用。
- 能做的：tools＝ls（`long`）／get／add（`path`｜`path_json`、`name`、`replace`、`envs`、`env_file`、`no_cache`）／rm；llm＝ls／set（`settings`）／rm（`keys`）；system＝get／set（`text`）。
- 重用底層，不另寫一套：`aos-agent` 沒有改定義的子指令（它的 tools／llm／system 都只對 stack），它自己的提醒就說「改定義用 aos-tools／aos-json」——所以 tools 轉 `aos-tools --file <定義宣告的 tools 檔>`（疊法、null、相對路徑的存法全歸 aos-tools）、llm 改值與刪鍵轉 `aos-json set --str`／`del`、system 整份寫宣告的檔（同 `aos-agent system set` 的寫法：同層暫存檔再改名）。宣告的檔位置照 `lib/agent/agent_files.py`（跟 aos-agent、brain 同一份）。
- 下層在 `$AOS_WS` 跑（相對路徑從工作區算）、stderr 原樣透出、最後一行錯誤行接成自己的（C-52 例外 ⑤ 本來就列了 agent_def）。
- 檔：`lib/agent/agent_def/_entry`（入口、分派、`call` 叫下層）、新檔 `lib/agent/agent_def/def_edit.py`（三個 op 的本體）、`_tooldef.json`、`_metainfo.json`、`tests/test_def_edit.py`（新，11 支）、`lib/docs/03`、`lib/README`。

**2. 血統：`agent_def new` 在新定義的 `_metainfo.json` 寫 `lineage`。**

```json
{"summary": "...", "lineage": {"from": "defs/helper"}}
{"summary": "...", "lineage": {"template": "agent-fsm"}}
{"summary": "...", "lineage": {"from": {"$env": "AOS_HOME", "$path": "/templates/agent-fsm"}}}
```

- 照舊 `agents new` 的寫法與 11-07 agent-diversity 的定案：出生時寫一次、`from` 照參數原樣存（字串或指示詞物件）、記在定義的 `_metainfo.json`、`lib/aos/defs ls` 照印、`defs check` 不要求親代還在。
- 蓋掉複製來的舊 lineage（只記上一代；往上追＝順著 from 找）、其他鍵照留；沒有 `_metainfo.json`＝新建只含 lineage；不是物件＝`DefBad`（整份不留，同 new 其他失敗）；`_metainfo.json` 是捷徑＝換成一般檔、捷徑指的那份不動。
- `tools`／`llm`／`system` 不碰 lineage；`subagent rm` 也不碰。
- 測試：`tests/test_agent_def.py` 多 3 支、改 2 支。

**要重建什麼**：沒有。舊定義沒有 lineage 照舊能用（`defs ls` 只是不印）。

## 代定（可翻案）

| # | 代定 | 翻案的話要改哪 |
|---|---|---|
| F1 | 細的動作放進 `agent_def`（多三個 op），不另開工具 | 另開 `def_tools`／`def_llm`／`def_system` 一家：拆 `def_edit.py` 成三支 |
| F2 | `args` 包一層、形狀＝self_*（跟 `subagent` 轉手一樣）；不攤平成 `tools_add` 這種 op | 攤平：`check_args` 改收頂層鍵，tooldef 例子重寫 |
| F3 | 沒有 reset（定義沒有疊在上面的那份可刪）；llm、system 沒有 `long`（沒有來源可分）；給 reset＝`OpUnknown` 並說明 | 要「回到範本那份」＝另加 op，從 lineage.from 抄回來 |
| F4 | 不檢查「這份定義正被哪幾隻用」、不印那幾隻的名字；改完只印一句「用這份定義的 agent 下一拍看到，除非它自己改過同一處」 | 要列名字＝查 daemon 表（同 aos-agent 的 `warn_shared`），多一層依賴 |
| F5 | 不設門：哪份定義都能改（含自己的定義），成不成看 Linux 權限（使用者 11-10「啥定義都可改，只要有權限」） | — |
| F6 | lineage 只記 `from`／`template`；舊的 `reason`（specialize／split／fix／manual）與 `review` 不回來——現在沒有人寫、review_round 也不讀 | 要回來＝`new` 多收兩個選填鍵，併進 lineage |
| F7 | lineage 不記時間、不記是哪隻 agent 做的（時間看 git；「誰」見下面方向題） | — |
| F8 | llm 的鍵照字面（含 `/`、`~`，經指標跳脫）；值只收字串（同 self_llm）；不認得的鍵照存，提醒印進 stdout | — |

## 留給使用者的題

1. **「誰生的誰」要不要也記執行時那一層？** 這次做的血統是**定義的出處**（這份定義從哪份複製來，像 git 的 fork 紀錄），寫在定義裡。另一種讀法是**執行時的親子**（哪隻 agent 用 `subagent add` 生了哪隻）：父那邊其實已經有帳（`subagents.json`，只記名字與 stack，子 rm 掉就從帳上拿掉）；要讓子自己也知道「我是誰生的」，就得在子的 stack 寫一格父的名字——這跟 [C-46](../../../docs/CONCEPTS/05-agent/01-腦-工具-可預測性與agent函數binding.md)「子 agent 只看自己的 stack、看不到呼叫方的（沒有 `parent` 鏈）」正面衝突。兩種後果差很多：(a) 只要定義出處（現況）＝什麼都不用再做；(b) 也要執行時親子、但不給子看＝在父的帳以外另留一份不隨 rm 消失的紀錄（例：父 stack 裡一份只增不刪的出生記錄）；(c) 也要給子看＝要改 C-46。原則推不出選哪個，所以沒做、等你說。
2. 知識庫節點 `knowledge/aos/agents.json#/agent_def` 還寫著只有 new／check（這次不准碰 knowledge，留給拆 knowledge 那條線或之後補）。
