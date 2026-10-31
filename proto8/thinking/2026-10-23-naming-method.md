# 2026-10-23 命名方法

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)｜前一份：[命名統合](2026-10-23-naming.md)

規矩見 [thinking/README](README.md)：只留使用者原文、決定、結論。查老慣例的過程（Unix／Linux／GNU／Go／POSIX 的原文與出處）是 AI 調查，放在 [notes/命名-老慣例查證](../notes/命名-老慣例查證.md)，不在這裡。

## 使用者原文（整理版）

### 10-23 晚，命名方法

> 關於命名規則這塊，我想嘗試一些新的概念，在現有的原則與規則上添加一些能讓人更快看懂的...算小技巧吧。是這樣的，我在寫程式的時候，會先用簡短的介紹描述自己要做的東西，比如aos-loop，我會這樣說：以指定設定，定期執行某個aos-exec目標。 對，我知道這個說起來很爛，但沒關係，反正大概就是這個意思。照着這個規則去寫出來之後，就是基礎實作。然後爲了因應各種情況，或是單純是我想要improve這個程式，那我們可能會給他添加額外的功能。然後我會給這些額外的功能添加更多說明，比如說：這個loop他在執行過程中，會將自身狀態與自身控制，放到外部檔案，並隨着loop的執行過程不斷讀取或更新這些檔案。　好，然後就按照這句話開始實作，同樣，隨便弄一些檔案做狀態和控制，做好後就是基礎實作。然後是命名問題：狀態/控制，可以走簡寫，所以就是state/ctl。那這兩個檔案的內部呢？比如state，他包含這些資訊：執行到第幾個exec，最多執行到第幾個exec，兩次exec之間要間隔多久，這個loop是啥時候啓動的，這個loop的pid是啥，上個exec跑出來的結果(錯誤與輸出)...。把這些資訊寫出來後，在去將其命名，比如執行到第幾個exec，這句話中有"第幾個"，所以可以有index，也就是_i，所以可以叫他run_i/exec_i...這可能不太好，要再想想。然後是最多執行到第幾個，這可以用上限/極限/最大值來描述，現在是用max，所以有max_*，但也可以用其他的，具體要用哪個，除去看哪個的意義最貼近之外，也要看他是否有簡寫(容易認，少寫幾個字母)，還有是否與現有體系的概念相符。然後是這個loop啥時候啓動的，可以用stated_at，後面接參照與單位(兩者可以合一)：started_at_ticks，然後是間隔多久，可以用interval，配合單位成爲interval_ms，以及上次exec的結果，可以用last_exec_err/out等，但這太長了，可以適當簡短爲last_err/out，簡短的原則是簡短後，不要與同檔案，或是同主題下的概念產生關聯，也就是簡短後也仍然保有獨特性，比如last_*，也就是"上次"，在現有的程式功能描述中，能夠配的上這個詞的，也只有"上次exec"。

> 讓fable想想

> 先試試看，不要急着寫進去

### 10-23 深夜，問老慣例

> 這種命名規則，那些unix年代的老人，或是linux的開發者，有慣例嗎

> 好，幫我去查，順便再幫我弄一套，結合了這些的新命名規則，拿去更新artifact

> nr_這東西還是建議不要用，現在這東西不太常見了

（fable 寫的方法、查證與 12 條規則在 artifact「命名方法」 https://claude.ai/artifact/7gwCnksBm1ztXhnPGiJnf1 。）

### 最後

八題選完後：

> 寫進去吧

## 決定：八題（頂層出題，使用者選）

1. **事件時間**：`<事件>_at`＝某事件發生的時間 → **補**（時間點一律這樣叫、不用單獨的 `at`，見文末 10-25）。
2. **`start_ticks`** → **改成 `started_at_ticks`**（照使用者原文的例子）。
3. **index**：`_i` 不進縮寫表；真要用時寫 `idx` → 照此。
4. **ctl 的 `stop`** → **改成 `stopped`**：跟 state 的 `phase: stopped` 同字，ctl 全是宣告狀態（`paused`、`stopped`）。
5. **「上一拍的結果」`last_code`** → 先不加。
6. **時間點的值** → 留 ISO 8601 UTC 到毫秒（不改 Unix 的 epoch 秒）。
7. **`_entry` 的 `_` 開頭** → 留 `_entry`；C-54 補一句「`_` 開頭的檔＝入口」。
8. **`AOS_CF`／`AOS_CD`／`AOS_CO`** → 留著（表上已有的縮寫不追溯）。

計數：不用 kernel 的 `nr_`（使用者「nr_這東西還是建議不要用，現在這東西不太常見了」）；計數現叫 `counter_<被數的東西>`（見文末 10-25）。

## 結論：命名方法 R1～R12（定案版）

寫進 C-54，細則在 [CONCEPTS C-54 命名方法](../docs/CONCEPTS/01-設計理念/C-54-命名方法.md)。骨幹是使用者的六步（一句話 → 加功能先一句話 → 替檔取名 → 每格一句白話 → 挑字造名 → 簡化），加上 Unix／Linux 老慣例。

1. **R1 先寫一行 NAME**：`名字 - 一句話`（照 man page 第一行；英文小寫開頭、不加句號）。放檔頭或 README 第一行；所有名字都要能從這行推回來。加功能也先一句話，再加 key（C-48）。
2. **R2 每一格一句白話，先不想名字。**
3. **R3 先查固定格**：原值 `val`、上限 `max`、種類 `kind`、結束碼 `code`、訊號 `signal`、流水號 `seq`、階段 `phase`、行程號 `pid`。對得上就直接用。
4. **R4 主題字從白話的主詞來，全體系一詞一義；巢狀已經說了的不再重複**（`loops.bob.pid`，不寫 `loop_pid`）。ctl 是宣告，key 用狀態詞、跟 state 回的同字（`paused`、`stopped`）。
5. **R5 縮寫只用縮寫表；進表門檻＝一眼還原得了**（Unix／POSIX 老慣例，或看一眼就還原得了全字）；「刪母音」式不收。表上已有的不追溯（`cf`、`cd`、`co`）。
6. **R6 修飾成分照表貼**：上限 `max`／`max_`；計數＝`counter_<被數的東西>`（不用 `nr_`；撞名時照 R9 換角度，得到的名字不一定合這條）；時長與單位當後綴（`_ms`、`_ticks`）；時間點一律 `<發生了什麼>_at`（`recorded_at`、`started_at`），值是 ISO 8601 UTC 到毫秒；同一個時間點用別的單位記，單位接在後面（`started_at_ticks`）；上一次 `last_`；index 不進表，真要用寫 `idx`。
7. **R7 排字序**：主題在前、由大到小，單位一律在最後；`max_`、`last_` 這種修飾詞在前是例外（C-54 原有）。
8. **R8 名字長度跟「要被認多遠」成正比**：環境變數（`AOS_` 前綴）＞程式名（`aos-` 前綴）＞檔名、JSON key（同檔唯一就好，可短到 `max`、`code`）＞程式內部的區域變數（照該語言慣例，`i`、`tmp`）。
9. **R9 簡化**：能省就省，條件是省完在同檔、同主題裡仍然獨一無二；同檔出現第二個同類的格就把主題字補回來。**撞名就換角度**：照方法推出來的名字跟同一個檔或同一個主題裡的名字撞了，就換一個角度，用白話重新描述它的功能與特性，再從那句白話取名。
10. **R10 形式照已定的**：小寫底線、指令名換連字號、環境變數全大寫、副檔名三種、複數只加 s、錯誤代號四種（C-54 原有）。
11. **R11 不用型別前綴；`_` 開頭不表「私有」**：`_` 開頭的檔＝入口（`_entry`）。
12. **R12 最後回頭清**：每個名字要能從 R1 那一句推回來；推不回來的，要嘛名字錯，要嘛那一句漏寫了功能（補句子）。

## 照規則改的名字

對照表補在 [2026-10-23-naming.csv](2026-10-23-naming.csv) 最後三列：

- state 窗的 `start_ticks` → `started_at_ticks`（aos-loop、aos-daemon 的 state 與子項列；N-32）
- ctl 的 `stop` → `stopped`（N-06、N-07）
- state 窗的 `last_warning` → `ctl_warning`（N-08；主詞是 ctl、主題在前，`last_` 留給「上一次」）

bin／impls README 每支程式開頭補 R1 的 NAME 行：

```
aos-exec   - 在工作區裡執行一個資料夾程式
aos-loop   - 以指定設定，定期執行一個 aos-exec 目標
aos-daemon - 照一張名單，把幾個 aos-loop 各自起在自己的小格裡、看著它們
aos-fsm    - 照一張狀態表，每叫一次跑「現在狀態」那一格，成功就換到下一個
aos-tick   - 把時鐘檔的回合數往前走一格
```

## 10-23 深夜：「拍」改「次」、撞名換角度

### 使用者原文

頂層用白話講 aos-loop 時用了「拍」：

> "拍"，其實我們人類不常用這個來說，我們都是說"次"。重新說一次白話

頂層問要不要把文件與名字也改：

> 改，beats改runs，然後val寫要跑啥，通常不會用val，應該用run。

頂層問兩個衝突，使用者選：

1. C-55「原值那一格一律叫 val」跟改回 `run` 衝突 → 選「**只有 loop、daemon 用 run**」。
2. 頂層說 daemon 子項已有 `runs`（子項被啟動過幾次），跟 loop 的新 `runs` 撞名 → 使用者自己填「**restarted_times**」。

之後補一條規則：

> 像這種命名重複的，可以用另一個角度用白話描述其功能與特性

### 決定

- 條文、程式說明與註解、錯誤／提示訊息、README、demo 說明裡用「次」（「第 N 次」），不用「拍」；thinking／notes 歷史與使用者原話不改。
- 「要跑什麼」那一格現叫 `exec`、state 的計數現叫 `counter_runs`（[命名統合](2026-10-23-naming.md) 10-23 深夜與 10-25 那兩段；取代這裡的 `run`／`runs`）。
- 「beat」這個字在 aos 裡沒有對應的概念：庫叫 `aos_run.py`；impls 的 `run_once`、結果型別 `Run`、`src/run/`。`heartbeat`（心跳）是另一個概念，不動。
- **不用 `restarted_times`**：daemon state 裡子項那一列只有 `pid`、`started_at_ticks`、`phase`、`code`、`signal`，沒有 `runs`；子 loop 結束後也不會自動重起，沒有「重啟過幾次」可記。demo stamp 工具在它自己 stack 裡的 `runs.txt`（記 stamp 被用了幾次）跟 loop state 不在同一個檔、也不是同一個主題，照 R9 不算撞名。
- **「撞名就換角度」併進 R9**（見上）。C-54 命名方法裡的例子是假設的（fsm trace 的「第幾格」→ 撞 `states` → 換角度「走了幾步」→ `steps`），標明是假設。

## 10-25：計數 `counter_`、時間點 `<發生了什麼>_at`

使用者 10-25：「state.json中，runs改counter，at改成recorded_at」，再說「計數這塊，幫我改成counter_*」；頂層問時間點的兩題，使用者回「都好」（頂層代定、可翻案）。R3、R6 已照這段寫；state.json 是 `counter_runs`、`recorded_at`，細則在 [命名統合](2026-10-23-naming.md) 10-25 段與 [C-54 命名方法 R3、R6](../docs/CONCEPTS/01-設計理念/C-54-命名方法.md)。

## 10-31 使用者原文：aos 的環境變數加 AOS_ 前綴（先記、之後處理）

使用者原文（10-31 早，另一個唯讀 session，看 bob-1/parts.json 的 `ECA_ON_EMPTY` 時）：

> 那個環境變數，感覺要加上 AOS_ 前綴。

定調：先記下來、之後處理。

範圍，使用者原文（10-31）：

> 先記下來，之後再來一次性改。

決定（10-31）：之後**一次性全改**，下面核出的整份清單一起補齊、不分批；時機未定。

跟 AI 討論後的結論（10-31 對過碼，grep `proto8/bin`、`lib`、`extras` 讀 env 的地方）：

- 依據是 [C-54 命名方法 R8](../docs/CONCEPTS/01-設計理念/C-54-命名方法.md)：名字長度跟「要被認多遠」成正比，環境變數全系統都看得到 → 全大寫、帶 `AOS_` 前綴。env 是全域命名空間；現有 `AOS_STACK`、`AOS_WS`、`AOS_CD` 等都有前綴。
- 使用者看到的那一組（四個）：
  - `ECA_ON_EMPTY`：`lib/eca/turn/turn.py`
  - `ROUND_ON_EMPTY`、`ROUND_AGENT`：`bin/aos-round`（`ROUND_AGENT` 也被 `lib/agent/round/fsm-*.json` 用 `{"$env": "ROUND_AGENT"}` 帶給每一格）
  - `MAX_RETRIES`：`lib/agent/round/roundlib.py`；連領域字都沒有，最易撞名
- 同類、也沒掛 `AOS_` 的（核對時多找到的）：
  - `TIMEOUT_MS`、`ENDPOINT_NAME`：`lib/endpoint/openai/_entry`（`ENDPOINT_NAME` 由 `roundlib.py` 設給 endpoint）
  - `ENDPOINT`、`MODEL_NOTE`、`MODEL_SEG`、`MODEL_FINAL`：`lib/agent/compact/_entry`
  - `MAX_PARALLEL`：`lib/agent/act/_entry`
  - `ASK_AGENT`、`ASK_MAX_STEPS`、`ASK_WS`：`lib/aos/ask_round/_entry`
  - `PYFIX_DIR`：`lib/agent/pyfix/_entry` 自己設給子 agent，是 aos 的、不是外部工具的
  - `S6_BIN`：`extras/sandbox/root/setup.sh`，覆寫 s6 的位置，算邊界
- 不算：外部工具自己的 `CODEX_HOME`、`CLAUDE_CONFIG_DIR`，系統的 `PATH`、`TMUX`、`SUDO_USER`。
- 可能有個刻意分野（沒前綴＝格自己的設定、只有該格讀），但沒有寫明，也防不了撞名。

狀態：**10-31 已改**（`9424ff9b`，見下面「10-31 已改」）。

交互：`ECA_ON_EMPTY` 使用者另想改 argv（→ [eca § 10-31 想法](2026-10-30-eca/10-10-31-使用者原文-turn-的定義檔只認固.md#10-31-使用者想法turn-的兩個改法先記之後處理)），一次性全改時對齊。

### 10-31 已改（隊長與工人照 R8／R9 代定新名，可翻案）

commit `9424ff9b`，共 49 個名字，程式、`fsm-*.json` 的 `$env`、parts.json、`.env`、README、測試、code map 一起改，**不留舊名相容層**；條文 [C-54 R8 加註](../docs/CONCEPTS/01-設計理念/C-54-命名方法.md)、[P-42 加註](../docs/CONVENTION/02-題目stack停錯腦.md)。`ECA_ON_EMPTY` 不在內：它改成 aos-eca-turn 的 argv `--on-empty`（`a8d42682`，[eca § 實作時代定（10-31）](2026-10-30-eca/13-實作時代定.md#實作時代定10-31隊長與工人照原則定的細節可翻案)）。家機試驗場 `~/code/playground/nia-idle/parts.json` 也跟著改。

| 舊名 | 新名 | 誰讀 |
|---|---|---|
| `ROUND_ON_EMPTY`、`ROUND_AGENT` | `AOS_ROUND_ON_EMPTY`、`AOS_ROUND_AGENT` | `bin/aos-round`、`lib/agent/round/fsm-*.json` |
| `MAX_RETRIES` | `AOS_ROUND_MAX_RETRIES` | `lib/agent/round/roundlib.py`（補上領域字） |
| `TIMEOUT_MS`、`ENDPOINT_NAME` | `AOS_ENDPOINT_TIMEOUT_MS`、`AOS_ENDPOINT_NAME` | `lib/endpoint/openai` |
| `ENDPOINT`、`MODEL_NOTE`、`MODEL_SEG`、`MODEL_FINAL` | `AOS_COMPACT_ENDPOINT`、`AOS_COMPACT_MODEL_NOTE`、`AOS_COMPACT_MODEL_SEG`、`AOS_COMPACT_MODEL_FINAL` | `lib/agent/compact` |
| `MAX_BYTES`、`SEG_KB`、`KEEP_TURNS`、`KEEP_MAX`、`KEEP_FINAL_MAX`、`KEEP_LINE_MAX`、`RESULT_CUT`（核對補上） | `AOS_COMPACT_` 加原名 | `lib/agent/compact` |
| `MAX_PARALLEL` | `AOS_ACT_MAX_PARALLEL` | `lib/agent/act` |
| `ASK_AGENT`、`ASK_MAX_STEPS`、`ASK_WS` | `AOS_ASK_AGENT`、`AOS_ASK_MAX_STEPS`、`AOS_ASK_WS` | `lib/aos/ask_round` |
| `PYFIX_DIR` | `AOS_PYFIX_DIR` | `lib/agent/pyfix` |
| `S6_BIN`（邊界，判成 aos 的） | `AOS_S6_BIN` | `extras/sandbox/root/setup.sh` |
| `IMPROVE_RUN`、`IMPROVE_SANDBOX`、`IMPROVE_TARGET`（核對補上） | `AOS_IMPROVE_RUN`、`AOS_IMPROVE_SANDBOX`、`AOS_IMPROVE_TARGET` | `demo/self-improve`、`lib/aos/try_run`、`extras/sandbox/examples` |
| `JSON_EDIT_MAX_ROUNDS`（核對補上） | `AOS_JSON_EDIT_MAX_ROUNDS` | `impls/aos-json/tools/json_edit` |
| `COMPACT_*`（agent-hal，含 `COMPACT_URL`、`COMPACT_TIMEOUT_S`、`COMPACT_OVER_KB`） | `AOS_COMPACT_*` | `demo/agent-hal/compact`（跟 lib compact 同名同義） |
| `THOUGHT_*`（agent-gus，含 `THOUGHT_DEPTH`、`THOUGHT_BUDGET`） | `AOS_THOUGHT_*` | `demo/agent-gus` |
| `KAI_FULL_UNDER`、`RECALL_HISTORY` | `AOS_KAI_FULL_UNDER`、`AOS_RECALL_HISTORY` | `demo/agent-kai` |
| `BRAIN` | `AOS_IVY_BRAIN` | `demo/llm-kernel`（只有 agent-ivy 讀，所以用 agent 名當領域；不跟 `AOS_BRAIN_*` 那一組混） |

代定與留意：

- Python 裡的區域變數名照語言慣例留著，只改環境變數字串，例如 `MAX_BYTES = env_int("AOS_COMPACT_MAX_BYTES", …)`。
- **副作用**：好幾處給子程式的環境會先清掉 `AOS_*`（`lib/aos/try_run`、`demo/self-improve/common.py`、多數測試的 `env_of`），所以這些改了名的設定現在也會被清掉。`try_run` 原本從清過的那份環境讀 `IMPROVE_SANDBOX`，所以改成從自己的環境讀。其餘幾處照「aos 自己的變數」本意，讓它們被清掉，沒有再改。`aos-llm-kernel` 只疊信裡 `AOS_` 開頭的變數，所以這些設定現在也會跟著信疊進去。
- **沒改、待使用者定**：`proto8/topdown/`（galtxt 兩隊凍結的試驗）有 33 個自己的變數，`GALTXT_*` 20 個、`OPTKIT_*` 11 個、`SELFOPT_*` 2 個，約 320 處，還會牽動 `test_topdown_*`。這些名字已經帶領域前綴，又是歷史試驗場，所以這批先不動。使用者 10-31 照預設、這批不補，可重訪 → [eca § 實作時代定（10-31）決定](2026-10-30-eca/13-實作時代定.md#決定10-31)。

