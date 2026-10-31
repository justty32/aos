← [入口](../2026-10-30-aos-round.md)｜涵蓋：B. aos-round 長什麼樣（結論）｜上一份 [02-A-N-36-分岔的格式](02-A-N-36-分岔的格式.md)｜下一份 [04-C-換過去的路](04-C-換過去的路.md)

## B. aos-round 長什麼樣（結論）

**一句話（C-54 R1）**：`aos-round <agent 資料夾>` ＝ 把 agent 的「一輪」跑一格：拿 `lib/agent/round/` 裡的那張 fsm 表交給 aos-fsm，表上的每一格是薄薄一支程式、只叫 agent 自己登記的器官（queue／history／endpoint／act／hook）。外面照舊由 agent 的 `loop.json`（aos-loop）一次一次叫它、開 ctl／state 窗。

1. **形狀＝一支小程式 ＋ lib 裡兩張 fsm 表 ＋ 五個薄格**。
   - **`proto8/bin/aos-round`**（跟 aos-parts、aos-tools 同一層；Python）：收一個參數 agent 資料夾（存在的絕對路徑，`AgentBad`）；用 `aos-parts --file <agent>/parts.json which --json round` 拿 `round` 槽的 `env`（`ROUND_ON_EMPTY`，預設 `stop`；`MAX_RETRIES` 照舊）；設 `ROUND_AGENT=<agent>`；`exec` 成 `aos-fsm <lib>/round/fsm-stop.json` 或 `fsm-idle.json`。沒有旗標（N-11 新程式盡量不收旗標）、不開窗、不寫檔；自己的錯一行 `aos-round: 代號 原因`、退 1。aos-fsm 的碼就是它的碼（exec 成它，透明）。
   - **兩張表**（`lib/agent/round/fsm-stop.json`、`fsm-idle.json`），只差 idle 那格接不接 10：

     ```json
     {"start": "idle",
      "states": {
        "idle":   {"exec": ["idle",   {"$env": "ROUND_AGENT"}], "next": {"0": "think"}},
        "think":  {"exec": ["think",  {"$env": "ROUND_AGENT"}], "next": {"0": "act", "10": "finish"}},
        "act":    {"exec": ["act",    {"$env": "ROUND_AGENT"}], "next": {"0": "think", "10": "more"}},
        "more":   {"exec": ["more",   {"$env": "ROUND_AGENT"}], "next": {"0": "act", "10": "act"}},
        "finish": {"exec": ["finish", {"$env": "ROUND_AGENT"}], "next": "idle"}}}
     ```

     `fsm-idle.json` 的 idle 是 `{"0": "think", "10": "idle"}`。`exec` 陣列的第一個是格的相對路徑，從表所在的資料夾算（N-36：`exec` 的相對路徑從 cwd 算、aos-exec 表檔時 cwd＝表的資料夾；aos-round exec aos-fsm 前先 cd 到 `lib/agent/round/`）；`{"$env": "ROUND_AGENT"}` 是 N-45 的指示詞、argv 陣列裡本來就能放（P-40）。agent 資料夾照 10-28 衝突 1 仍是每格的第一個參數，只是從表上經環境變數帶進去（P-39「往下只流環境變數、別的都明給」——明給的就是這個參數，變數只是表寫得出來的辦法）。
   - **五個薄格**（`lib/agent/round/{idle,think,act,more,finish}/_entry`，Python；現有 `_entry` 的函數搬成同資料夾的 `roundlib.py` 共用，叫格的方式、trace 以外的代定 28～38 照舊）：

     | 格 | 做什麼（都是叫 agent 的器官） | 退 0 | 退 10 | 其他 |
     |---|---|---|---|---|
     | `idle` | `cur/` 有信＝補認領（`queue claim`，不叫 `pre_round`）；沒有＝`hook/pre_round` → `queue claim` | 認到了 | queue 空 | 格的錯 |
     | `think` | `hook/pre_think`（有掛就重讀 history）→ `endpoint/<目前>` → 失敗問 `hook/on_error`（retry／switch 在格內數，`MAX_RETRIES`）→ `hook/post_think` → `history append` → `queue emit` | 那則 assistant 有 `tool_calls` | 沒 `tool_calls`（該交卷了） | `EndpointFailed` 等 |
     | `act` | 最後一則 assistant 還有沒回的 `tool_calls` 才叫 `act`，吐的 tool 訊息逐則 `history append`；沒有要跑的＝什麼都不做退 0 | 跑完（或沒事） | act 退 10＝插話（`on_interrupt` 說打斷） | 格的錯 |
     | `more` | `queue claim --more`（把插進來的那封接進 history） | 接到了 | 沒信（搶輸了） | 格的錯 |
     | `finish` | `queue finish`（stdin＝那則 content）→ `hook/post_round` | 收掉了 | — | 格的錯 |

2. **round 的順序怎麼對成格與分岔**：一輪＝idle → think → (act → think)* → finish → idle，跟 agent-round § 2 的順序一樣，只是「下一步是什麼」從 round 的 `where()` 搬到了表上，「現在在哪」從重算改成讀 `$AOS_STACK/state.txt`（fsm 的，N-39）。**每格對 state 與資料不一致要能自保**（N-38「半成品由格自己看自己的檔判斷」）：state 說 act、history 最後一則卻沒待回的 `tool_calls`＝act 退 0 直接去 think；state 說 finish、`current.txt` 空＝finish 退 0（沒東西可收）；state 說 idle、`cur/` 有信＝補認領。這樣 P-20「人修好再跑一次、從 state.txt 接著做同一格」直接成立，不用另一套判斷。
3. **五個難點各怎麼靠分岔解**：
   - **idle 等（不阻塞）**：idle 格 queue 空退 10。`fsm-idle.json` 接住 `"10": "idle"` → fsm 退 0 → loop 隔 `interval_ms` 再叫一次（反應時間＝`interval_ms`，agent-lifecycle 衝突 6 已定）；`fsm-stop.json` 不接 → fsm 退 10 → loop 退 0、停。`ROUND_ON_EMPTY` 的兩個值就是這兩張表。
   - **插話**：act 格裡 `act` 器官退 10（它在兩批工具之間看了 `queue/new/`、`hook/on_interrupt` 說打斷）→ act 格退 10 → `more` 接進那封 → 回 act 把剩下的工具跑完 → think。act 的 10 不再到 loop 手上（隊長難點 2 的「包一層轉碼、加一格和記號檔」只剩表上一行）。
   - **答完一題就停**：`fsm-stop.json`＝答到 queue 空就停。`ask_round` 用自己的小工作區、一次放一題，所以「queue 空」就是「答完這一題」，兩者在它身上等價；`ROUND_ON_EMPTY=stop` 的常駐 agent 收到連續幾題會一口氣答完才停，這跟現在 round 的行為一樣。「不管 queue 還有沒有、嚴格一題一停」沒有人需要，不加（C-56）——見方向題 2。
   - **retry／switch**：留在 think 格**裡面**（一次問腦最多重來 `MAX_RETRIES` 次，計數在行程記憶體、用完 `EndpointFailed` 退 1），跟現在 round 一樣、不落檔。理由：N-38 允許「想優雅處理的格自己接錯」，這是格內的事；不把重試寫成表上的 `"1": "think"`（那是沒上限的自動重試，只有 loop 的 `max` 擋，跟 N-53「agent 自己不數連錯」的精神打架，見衝突 3）。think 退 1 → 表上沒接 → fsm 退 1 → loop 停下等人（P-20 預設）。
   - **trace 撞檔**：**格不寫 trace，fsm 的一格一行就是 aos-round 的 trace**（加了 `next` 欄之後一行看得出走到哪）。round 現在的 `{"unit"}` 行退場；端點換到哪看 `endpoint.txt`、用量看 `usage.jsonl`、工具呼叫看各工具小格的 trace（P-38 stack 樹）。一個 stack 一種 trace 形狀，`find … | sort` 照舊（見衝突 5）。
4. **退場的東西**：`hook/pause`（它的工作「一輪中途讓出、好讓 loop 看 ctl」現在每格之間 loop 本來就看）、`round --step`（fsm 一次一格就是 step）、round 的 `unit` trace、`where()`。`hook/pre_round`、`pre_think`、`post_think`、`post_round`、`on_error`、`on_interrupt`、`pre_tool`、`post_tool` 都照舊（在對應的格或 act 器官裡）。
5. **aos-loop 在外面包什麼、ctl／state 窗誰開**：跟現在 agent-nia 一樣，agent 的 `loop.json` 開 `ctl`／`state` 窗、設 `max`、`interval_ms`，`exec` 改成 `{"argv": ["aos-round", {"$env": "AOS_CD"}], "timeout_ms": 600000}`。**`timeout_ms` 現在管的是一格、不是一輪**（think 那格包含問腦）；要整輪上限自己在外面包（P-36 外層包內層）。aos-round 與 fsm 都不開窗（N-39）。P-36 殺整群照舊：loop 的單子逾時 → killpg → aos-round／aos-fsm／那格／它叫的器官與工具一起收，那格碼 128＋15、表沒接 → 停。
6. **什麼是「薄」**：aos-round 自己不到 80 行（找表、設變數、exec）；五個格加起來就是現在 `_entry` 的函數換個切法；「下一步」只寫在表上一處（C-52）。器官（queue／history／act／endpoint／hook）一行不改。
