# proto8/lib — aos agent 的函式庫（腦可以叫的工具，收成一份、被引用）

**lib - agent 跑的時候會呼叫的外部函數，收成一份標準版，掛捷徑引用、不複製**

← [proto8](../README.md)｜設計、盤點、代定與遷移清單：[thinking 2026-10-24 工具＝函式庫](../thinking/2026-10-24-tool-lib.md)｜慣例：[P-41、P-25](../CONVENTION/02-題目stack停錯腦.md)、[P-33](../CONVENTION/06-巢狀.md)｜特性：[`_metainfo`](../thinking/2026-10-24-metainfo.md)｜範例 agent：[demo/agent-liv](../demo/README.md)｜測試：`proto8/tests/test_lib.py`

使用者 10-24：「我們在做工具集，這其實挺像是在做函式庫。因爲agent是函數，我們給他的工具就是他在內部自己跑的時候會呼叫的外部函數。既然是這樣，那我們就要把抽象做好，把函數庫做好」——agent 是函數（一個資料夾，C-46、C-68），它 `tools/<名>/` 裡的東西是它內部呼叫的外部函數（C-42、C-61）。這裡把那些外部函數收成一份。

## 分層（每層只依賴下層）

```
demo/agent-*/              最上層：agent 本身（也是函數）
  tools/<名> ─捷徑─▶ lib/<層>/<名>/        引用，不複製（見下「怎麼引用」）
lib/agent/                 高層：裡面是一整隻 agent（或外部 agent CLI）的工具（pyfix、claude、codex）＋共用模組 agent_tool.py、cli_session.py（10-24 收了 3 個）
lib/aos/                   中層：動 aos 自己東西的工具（記憶 heap、寄信、spawn／ask／status、try_run）＋共用模組 aos_ws.py（10-24 收了 10 個）
lib/base/                  底層原語：檔案、資料夾、JSON、行程（bash）、小工具——Linux＋Python 標準庫（json_edit 另叫 aos-json）、只碰 $AOS_WS（10-24 收了 15 個）
impls/                     基礎層與標準庫（C-74）：aos-exec 把工具叫起來，loop／fsm 跑 agent
```

層名只是資料夾名，不進工具名；還沒有工具的層不先建空資料夾（STRUCTURE：不預先建空檔）。

## 一個工具長什麼樣（契約）

一個工具＝一個資料夾程式（C-61、N-50），裡面固定三個檔：

| 檔 | 給誰看 | 內容 |
|---|---|---|
| `_entry` | aos-exec | 可執行檔（python3 純標準庫，或 sh）；第一行 shebang，第二行 `# <名> - 一句話`（C-54 R1） |
| `tool.json` | 模型 | `{"description", "parameters"}`（P-41，OpenAI function 物件去掉 name；工具名＝資料夾名） |
| `_metainfo` | kernel 與人 | JSON，通用 key 照 [`_metainfo` 規劃](../thinking/2026-10-24-metainfo/01-位置與格式.md)：`summary`、`time_ms`、`resource`、`side_effect`、`idempotent`、`deterministic`、`interrupt`、`parallel`；模型看不到（M10） |

規則（`tests/test_lib.py` 檢查形狀、每條都有案例）：

1. **參數**：stdin 一份 JSON 物件（模型的 `arguments` 原樣，P-41）；空 stdin 當 `{}`。key 全小寫底線、單位放字尾（`timeout_s`、`max_bytes`，C-54）；選填的寫預設值在 `tool.json` 的說明裡。
2. **結果**：stdout 整段就是結果（P-41）。文字工具印文字；結構工具（`ls`、`json_*`）印一行 JSON。工具不讀、不轉述自己起的程式的 stderr 以外的東西（C-52）。
3. **錯**：一律 stderr 一行 `工具名: 代號 原因`、退 1（P-21），**同一行也印在 stdout**——stdout 是給腦看的，腦才知道錯在哪。代號照 C-54 四種結尾（`ArgumentsBad`、`WsMissing`、`PathBad`、`FileMissing`、`FileBad`、`ReadFailed`、`WriteFailed`、`MkdirFailed`、`TextMissing`、`TextBad`、`PointerBad`、`PointerMissing`、`CommandFailed`、`LaunchFailed`）。**參數給錯對工具來說也是錯、照樣退 1**；停下等人還是把那行回給腦，是叫它的 agent 自己的決定（agent-dan 範本與抄它的 10-24 晚起都回給腦，[thinking](../thinking/2026-10-23-tool-calls.md#10-24-定叫工具與小念頭的失敗回給腦)），工具不替它決定（C-52、C-53 入口檢查）。被跑的指令自己退非 0 **不是**工具的錯（那是結果，尾巴寫結束碼）。
4. **沙盒＝`$AOS_WS`**：路徑一律從工作區算，解開 `..` 與捷徑後必須還在裡面（`PathBad`）；沒設或不是資料夾＝`WsMissing`。要動別的資料夾，是叫它的人 `aos-exec --ws 那裡 tools/<名>`（C-66 指標＝`AOS_WS`），工具不另收根的參數或環境變數。`bash` 擋不住指令本身跑出去，說明裡寫明。
5. **逾時**：會跑東西的工具一定有逾時（`timeout_s`，預設與上限寫在 `tool.json`），到時整群先 TERM 再 KILL、算 `CommandFailed`；工具自己被外面 TERM（act 格逾時）時先收掉自己起的那一群再走，不留孤兒（P-36）。
6. **寫檔**：先寫 `.` 開頭的暫存檔再改名（N-05）、留住原檔權限；幾處一起改的全有或全無。
7. **上限與漸進展開**：讀最多 2000 行或 50KB、列最多 500 項、JSON 檔最多 4MB；超過就截，並在結果裡說怎麼接著拿（`offset`、`next_offset`、`pointer` 往下一層）。
8. **stack**：工具的 stack＝呼叫者給的小格 `$AOS_STACK/<名>/`（P-17）；base 層是純函數、不用 stack，要跨呼叫留東西的工具（中層以上）才寫那裡。
9. **自成一格**：一個工具資料夾裡的東西只靠自己，不 `import` 隔壁或上層的檔——搬到哪、被捷徑掛到哪都跑得動（C-61「兩份一起搬也不斷」）。同樣的十幾行開頭（讀 stdin、查工作區、報錯）每個工具各留一份；長到第三份一樣的大段再抽成共用庫（STRUCTURE 膨脹即拆）。
10. **命名**：工具名＝資料夾名，一個動詞（`read`、`ls`）或「主題_動詞」（`json_read`、`json_edit`，C-54 主題在前）；縮寫照 [abbr.json](../CONCEPTS/abbr.json)；錯誤代號主詞在前。

## 怎麼引用（不複製）

agent 的 `tools/` 裡放**一條相對捷徑指到庫裡那個工具**，一個工具一條：

```sh
cd proto8/demo/agent-liv/tools && ln -s ../../../lib/base/read read
```

- agent 的程式**一個字不用改**：act 照舊 `aos-exec tools/read`（P-25、P-33，地址零個 `..`）；aos-exec 走進捷徑指到的真資料夾（cwd、`AOS_CF`、`AOS_CD` 都是庫裡的位置，N-57、N-59），brain 照舊從 `tools/*/tool.json` 組 tools 陣列。agent 不知道、也不必知道這個工具是庫的（C-52）。
- **要哪些掛哪些**，自己的工具（真資料夾）跟庫的並存在同一個 `tools/`；同名時自己的贏（一個名字只能有一個東西），這就是覆寫。
- **版本＝git**：庫改了，掛著的 agent 下次跑就是新的；要釘住某一版就複製那個資料夾進自己的 `tools/`（複製＝覆寫＝自己維護）。
- 不選的幾條（比較在 [thinking](../thinking/2026-10-24-tool-lib.md)）：整個 `tools/` 一條捷徑（10-24 agent-pip 的寫法：不能挑、不能混自己的）；`tools.json` 清單（要改範本的 brain、act 兩支）；`_entry` 寫字串轉向（`tool.json` 還是得複製一份）；PATH（C-61 已否決）。
- 代價：只有 Linux 有捷徑（使用者 10-19「先只考慮在linux上」）；repo 外的 agent 要寫絕對路徑；複製 agent 資料夾時要保留捷徑（`cp -a`，不要 `cp -r`／跟著捷徑複製，不然就變成複本）。

## 索引：base（10-24）

回 JSON 的工具裡，計數（幾個、幾行、幾字）的 key 一律 `counter_<被數的東西>`（10-25 使用者「計數這塊，幫我改成counter_*」，C-54 命名方法 R6；原 `total`、`children`、`hidden`、`keys_more`、`children_more`、`lines`、`total_lines`、`len`、摘要裡的 `keys`／`items`／`chars`、`set`／`del`、`files`）；陣列本身（`items`、`keys` 清單）照舊。aos 那幾個：信的 `hops` 改 `counter_hops`、memory 頂層索引的 `count` 改 `counter_active`。

| 工具 | 一句話 | 參數 | 回什麼 | 來源 |
|---|---|---|---|---|
| [read](base/read/) | 讀工作區裡一個文字檔，太長從頭截 | `path`、`offset`、`limit` | 內容（不加行號）；被截時尾巴寫從第幾行接著讀 | demo/pi-tools/read |
| [write](base/write/) | 整份寫進一個檔（建或蓋）、上層資料夾自動建 | `path`、`content` | 一行：寫了幾 bytes | demo/pi-tools/write |
| [edit](base/edit/) | 幾處照字面替換，一處不合整個不改 | `path`、`edits[{old_text, new_text}]` | 一行：換了幾處 | demo/pi-tools/edit |
| [bash](base/bash/) | 在工作區用 bash 跑一行指令 | `command`、`timeout_s`（30／300） | stdout＋stderr 合在一起、尾巴寫結束碼；留最後 2000 行／50KB | demo/pi-tools/bash（`timeout` 改名 `timeout_s`） |
| [ls](base/ls/) | 列一個資料夾的子項，一次一頁 | `path`、`offset`、`limit`（100／500）、`hidden` | JSON：`counter_items`（一共幾項）、`items[{name, type, size, mtime}]`（資料夾多 `counter_children`、`aos`，檔多 `exec`，`.json` 多 `keys`）、`next_offset`、`counter_hidden` | 新寫，遷移時併進 demo/file-tools/ls 的加料 |
| [stat](base/stat/) | 單一個檔或資料夾的屬性 | `path` | JSON：`type`、`mtime`、`mode`；檔多 `size`、`exec`、`text`、`counter_lines`、`format`、`top` | demo/file-tools/stat |
| [view](base/view/) | 漸進看一個檔：JSON 照指標一次一層、大文字檔先給大綱 | `path`、`pointer` 或 `start`／`end` | JSON：`value` 或 `children`；文字的 `text` 或 `outline` | demo/file-tools/view |
| [json_read](base/json_read/) | 看一份 JSON 檔的某個位置，大的摺起來 | `path`、`pointer`、`depth`（1／10） | JSON：`value`，物件摺成 `{type, keys}`、陣列 `{type, counter_items}`、長字串 `{type, counter_chars, head}` | 新寫（Python；換 aos-json 的 peek 輸出不同、沒好處，沒換） |
| [json_edit](base/json_edit/) | 照指標改幾個位置，一處不合整份不寫 | `path`、`set{指標: 值}`、`del[指標]` | JSON：`counter_set`、`counter_del`（改了幾個）、頂層 key | 新寫；遷移時寫檔改叫 aos-json（只重寫有變的那塊），介面不變 |
| [mkdir](base/mkdir/) | 建資料夾（上層一起建；已有＝沒事） | `path` | JSON：`path`、`created` | demo/file-tools/mkdir |
| [move](base/move/) | 搬移或改名（to 有東西就不搬） | `from`、`to` | JSON：`from`、`to` | demo/file-tools/move |
| [copy](base/copy/) | 複製檔或整個資料夾（捷徑照捷徑） | `from`、`to` | JSON：`from`、`to`、`counter_files` | demo/file-tools/copy |
| [trash](base/trash/) | 丟進 `.trash/<時間>/`（不真的刪，move 救回） | `path` | JSON：`path`、`to` | demo/file-tools/trash |
| [math](base/math/) | 算一個算術式子（不用 eval） | `expr` | 結果 | demo/agent-dan/tools/math |
| [clock](base/clock/) | 現在的 UTC 時間 | （無） | `2026-10-23T08:00:00Z` | demo/agent-dan/tools/clock（原本是 sh，改 python3 才能照契約驗 stdin） |
| [run_python](base/run_python/) | 跑一段 Python，回結束碼與輸出 | `code`、`timeout_s`（60／300） | 第一行「結束碼 N」、接著輸出 | demo/agent-gus/tools/run_python |

不碰工作區的三個（`math`、`clock`、`run_python`）不收路徑、不看 `$AOS_WS`；`run_python` 把程式寫進自己的小格再跑（規則 8 的例外：拿小格當草稿區，不跨呼叫留東西）。
每個工具的細節看它 `_entry` 開頭的幾行說明與 `tool.json`。

## 索引：aos（10-24 遷移）

| 工具 | 一句話 | 參數 | 回什麼 | 來源 |
|---|---|---|---|---|
| [memory](aos/memory/) | 長期記憶庫：存、找、讀、忘（庫在 `$AOS_HEAP`，沒設＝`$AOS_WS/.heap/`） | `op`（save／search／read／forget）、`kind`、`title`、`text`、`tags`、`query`、`limit`、`id`、`reason` | 給模型看的文字 | demo/agent-meg（`heap.py` 一起搬，brain 也 import） |
| [send_message](aos/send_message/) | 寄信給名冊（`$AOS_ROSTER`）上的成員或群組 | `to`、`subject`、`body`、`expect_reply` | 一行：寄了幾封、對話串第幾手 | demo/talk |
| [check_inbox](aos/check_inbox/) | 看自己信箱還沒處理的（只看不拿） | （無） | 一封一行摘要 | demo/talk |
| [spawn_agent](aos/spawn_agent/) | 從範本產生一隻 agent（`aos-ai spawn`） | `name`、`template` | aos-ai 那行 JSON | ai_tools/dan_tools |
| [ask_agent](aos/ask_agent/) | 問一隻 agent、等它答完（沒有就先 spawn） | `name`、`question`、`template` | JSON：`ok`、`answer` | ai_tools/dan_tools |
| [agent_status](aos/agent_status/) | 看 agent 的狀態 | `name` | aos-ai 那行 JSON | ai_tools/dan_tools |
| [make_json](aos/make_json/) | 生成一份 aos 的 JSON、先驗形狀 | `kind`、`spec`、`out` | aos-ai 那行 JSON（含 notes） | ai_tools/dan_tools |
| [make_tool](aos/make_tool/) | 在 agent 的 `tools/` 下起工具骨架 | `name`、`tool`、`description`、`params`、`lang` | aos-ai 那行 JSON | ai_tools/dan_tools |
| [explain_aos](aos/explain_aos/) | 查 aos 的概念 | `concept` | aos-ai 那行 JSON | ai_tools/dan_tools |
| [try_run](aos/try_run/) | 在工作區 `target/` 的暫時複本上跑一次 | `args`、`stdin`、`timeout_s`（10／60） | 結束碼、stdout、stderr | demo/self-improve 的改進者（`timeout` 改名 `timeout_s`） |

遷移前這幾個「模型的錯」多半印一段話退 0（memory、send_message 印「錯誤：…」，ai 那六個印 `{"ok": false}`）；現在一律照規則 3 退 1。原本靠退 0 讓腦自己改的 agent（agent-meg、talk 的 member），act 改成「工具退非 0 回給腦、不停」（同 agent-pip）。
`memory` 的 `$AOS_HEAP`、`send_message` 的 `$AOS_ROSTER`、ai 那六個的 `$AOS_AI_ROOT` 是規則 4「只碰 `$AOS_WS`」的例外，照原樣留著（放哪由叫的人決定，像 stack）。

**共用模組 [aos_ws.py](aos/aos_ws.py)**（不是工具、沒有 `_entry`）：「放題、等答案、讀 stack」——`names`、`where`、`put`（先寫工作區頂層暫存檔再 link 進 `new/`，不蓋已有的）、`answer_name`／`answer_text`、`tail_jsonl`、`last_jsonl`。給人用的 [proto8/human](../human/README.md)（aos-say／listen／chat）與給 AI 用的 [aos-ai](../ai_tools/README.md) 兩份合成這一份，各自用 realpath 找到這個資料夾 import。

## 索引：agent（10-24 遷移）

| 工具 | 一句話 | 參數 | 回什麼 | 來源 |
|---|---|---|---|---|
| [pyfix](agent/pyfix/) | 把改 Python 的事交給子 agent pyfix-agent（`agent/`，它的工具是 base 的 ls、read、write、edit、bash） | `task`、`dir` | 子 agent 的報告＋實際 diff | demo/agent-eve |
| [claude](agent/claude/) | 交給 Claude Code CLI 做、同一段對話續著講（人可以 attach 進去） | `prompt` | CLI 的回答 | demo/agent-fay |
| [codex](agent/codex/) | 交給 Codex CLI 做、同上 | `prompt` | CLI 的回答 | demo/agent-fay |

**共用模組**（不是工具、沒有 `_entry`；工具用 realpath 找到 `lib/agent/` 再 import）：
- [agent_tool.py](agent/agent_tool.py)：「把一隻 agent 包成工具」的轉接，共用一支——每次呼叫開新小格 `$AOS_STACK/runs/NNN/`、題目寫進子 agent 的 `ws/new/`、`aos-exec --dotenv-override --ws` 跑、拿 `ws/out/` 的答案（錯 `AgentFailed`、`AnswerMissing`）。要把另一隻 agent 包成工具：資料夾裡放 `agent/`、`_entry` 叫 `agent_tool.run_agent`（pyfix 是範例）。
- [cli_session.py](agent/cli_session.py)：claude／codex CLI 接成工具的做法（非互動續對話、或 tmux 畫面開著時從畫面送字）；工具資料夾由 `_entry` 傳進來（`cli.json` 在那裡）、agent 資料夾由 `attach` 傳進來。工具被整個複製進某隻 agent 的 `tools/`（覆寫）時，`_entry` 改找那隻 agent 根的 `cli_session.py`。

pyfix 的子 agent 要改的程式在 `PYFIX_DIR`（`$AOS_WS/<dir>`），自己的 `$AOS_WS` 是收題交答案的小格，所以它的 act 用 `aos-exec --ws $PYFIX_DIR tools/<名>` 叫庫的工具（規則 4：換根是呼叫者的事）；庫的工具錯一律退 1，子 agent 的 act 把那行回給腦。
沒收進來的：agent-gus 的「小念頭」（`thought.json`／`thought.py`）——它是 agent-gus 自己的入口、遞迴起 agent-gus 本身（`shared.launch`），要收就得把整隻 agent-gus 搬進庫；也沒有給模型的 `tool.json`。aos-json 自帶的 `tools/json`、`tools/json_edit`（小念頭式兩步改）留在 `impls/aos-json/`，跟它的測試在一起。

## 範例：demo/agent-liv

agent-dan 的複本（只改錯誤訊息開頭與假腦；act 10-24 真腦實測後改照 agent-pip：工具的錯回給腦、不停），`tools/` 裡七條捷徑掛上面七個，加一個自己的 `clock/`（真資料夾，示範並存）；`_metainfo` 寫這隻 agent 的特性。假腦叫一次 `ls`、拿 `counter_items`（10-25 原 `total`）答題，證明捷徑掛進來的工具經 aos-exec 跑得動、小格落在 `$AOS_STACK/ls/`。跑法同 agent-dan：`aos-exec --ws <工作區> proto8/demo/agent-liv`（PATH 放好 impls 三支；設 `AOS_BRAIN_URL` 才用真腦）。

## 測試

`python3 -m unittest discover -s proto8/tests -p test_lib.py`：形狀檢查跑過 `lib/` 底下每個工具（三個檔、NAME 行、`tool.json` 與 `_metainfo` 的形、壞 stdin 的錯誤行格式與 stdout 同一行），base 上午那七個各自的行為（截斷、全有或全無、逾時整群停、路徑出不去、沒 `AOS_WS`；不碰工作區的 math、clock、run_python 不驗這條），agent-liv 經捷徑用庫的工具跑完一題。遷移進來的工具，行為案例留在原本那幾份：`test_pi_tools.py`、`test_file_tools.py`（base）、`test_meg.py`、`test_talk.py`、`test_ai_tools.py`、`test_self_improve.py`（aos）、`test_eve.py`、`test_fay.py`（agent）、`test_gus.py`（run_python）。
