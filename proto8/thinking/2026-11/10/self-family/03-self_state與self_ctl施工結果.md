# 03 self_state 與 self_ctl 施工結果（11-10 晚）

← [self-family](README.md)｜原話與決定見 [02](02-self_state與self_ctl.md)

## 動作與例子

**人用：`aos-agent ctl state [-t 名字] [-j] [類別...|all]`**

| 叫法 | 印什麼 |
|---|---|
| `aos-agent ctl state -t bob` | 總覽：十類各一行（who state tools llm hooks history mailbox children resources time） |
| `aos-agent ctl state -t bob history mailbox` | 那兩類的細節，`== 類別` 分段 |
| `aos-agent ctl state -t bob all` | 十類全部細節 |
| `aos-agent ctl state -t bob -j tools` | 一個 JSON 物件 `{"tools": {...}}` |

每類的來源：tools／llm／hooks／history 轉叫 `aos-agent tools ls`、`llm ls`、`hook ls`、`history ls`；mailbox 轉叫 `aos-mailbox -s <stack> peek`；children 讀 agents_children 的帳（`<stack>/tools/agents_children/children.json`，對上 daemon 表），配額讀定義與 stack 的 `children.json`；resources＝表上的 limits，加上 `/proc` 裡行程樹的記憶體、cpu 秒數、行程數；time＝現在時間、活了多久（從表上的 `started_at_ticks` 算）。哪類拿不到就印 `not available (原因)`，其他類照印。

**人用：`aos-agent ctl stop|pause|sleep|rm --no-wait`**（給對自己下指令用）：stop 只等 daemon 收下；pause 寫了 ctl 就回；sleep 和 rm 寄出就回；`rm --no-wait --purge` 另起一個脫離的小行程，等那列不在了再刪 stack。

**腦用：`self_state`**：`{}`（總覽）、`{"parts": ["history", "mailbox"]}`、`{"parts": "all", "json": true}`。

**腦用：`self_ctl`**：`{"op": "stop"}`、`{"op": "pause"}`、`{"op": "sleep"}`、`{"op": "rm"}`、`{"op": "rm", "purge": true}`。每次回下層那行，再加一行「之後會怎樣」。

## commit

| commit | 做了 |
|---|---|
| `e2c7a7b44` | ctl state 擴充、`--no-wait`、self_state、self_ctl、兩範本登記、測試、README 兩節、code-map |
| （本檔這次） | lib/docs/03 兩列、templates/docs 01／02 工具清單、02／03 thinking、SESSION-LOG |

## 驗收

- 測試：`cmd/aos-agent/tests` 全部 42 支（含新的 test_state_parts 4 支）、self_state 3 支、self_ctl 3 支、agent-fsm 的 test_own_tools／test_cells 都過。
- 實機（scratchpad `sfam-ctl/`，起了一台 kernel 副本和一台 agent daemon，跑完都 shutdown 了，沒有殘留行程）：
  - **假腦**照劇本叫 self_state 三種叫法（總覽、`parts` 三類、`all`＋`json`），三種都印對（十類、細節分段、JSON）。
  - **假腦**對自己叫 self_ctl，四個動作各一次：
    - pause：表上是 `paused`；別人 resume 之後它把那句答完。
    - stop：表上是 `stopped`；別人 start 之後它把那句答完。
    - sleep：表上是 `sleeping`，工具結果來得及寫進 history；wake 之後它答完。
    - rm（`purge`）：不在表上了，stack 也刪了。
  - **gemma-4-e4b 真腦**：自己叫 `self_state {"json": true, "parts": ["history", "mailbox"]}`，答對 2 則、0 封；之後叫 `self_ctl {"op": "stop"}`，表上變 `stopped`。
  - **eca（haiku）**：叫 `mcp__aos__self_state {"parts": ["tools", "time"]}`，答「15 tools」；叫 `mcp__aos__self_ctl {"op": "stop"}`，這一輪答完 BYE，表上變 `stopped`。

## 代定清單（照最保守能用的定的，可翻案）

1. 類別名：who state tools llm hooks history mailbox children resources time，加上 `all`；不給類別＝總覽；`-j` 出 JSON。原本 ctl state 那幾行併進 who／state／tools 三類。
2. history 的細節只給數字加最後 5 則（一行最多 200 字），要全文用 `history ls`。
3. children 的帳固定看 `<stack>/tools/agents_children/children.json`：登記名不是 agents_children 就讀不到，印 0。
4. resources 用的是 `/proc` 裡行程樹的 RSS 和 cpu 加總，不讀 cgroup。
5. `--no-wait`：stop 等 daemon 回信（收下了），不等停好、也不關畫面；pause 不等套用；sleep 和 rm 完全不等。
6. `rm --no-wait --purge`：用脫離的小行程等那列消失再刪 stack，最多等 60 秒（或 `--timeout-s`）。如果那隻在 cgroup scope 裡被整組收掉，小行程可能跟著死，stack 就留下來。這次實機刪成功了。
7. self_ctl 對 fsm 的 stop 是「這一步結束就停」：可能還沒答就停了，start 之後接著做。tooldef 照這樣寫。
8. 兩支都登記進兩個範本，排在 self_history 後面。

## 續行點

- 每一類的來源都接上了，沒有留空的接口。hook／mailbox／llm／孩子帳要是改了名字或位置，`ctl state` 的對應類別要跟著改（在 `cmd/aos-agent/aos_agent/ctl/state.py`）。
- 「給建議」那個工具使用者說之後再做。

## 知識節點內容（給頂層轉 json-memory 隊）

- **self_state**：看自己。`{}`＝十類各一行的總覽；`{"parts": ["history", "mailbox"]}`＝那幾類的細節；`"all"`＝全部；`"json": true`＝JSON。十類是：who、state、tools、llm、hooks、history、mailbox、children、resources、time。只給數字，不給建議；拿不到的類別會說 not available 和原因。不會自動放進 prompt，要自己叫。
- **self_ctl**：管自己（管別人用 agents_ctl）。
  - `stop`：這一步結束就停，可能還沒答；別人 `aos-agent ctl start` 之後接著做。
  - `pause`：這一步結束後停住；只有別人 `aos-agent ctl resume` 才會繼續。
  - `sleep`：馬上停；`aos-agent ctl wake` 或 daemon 重起才會醒。
  - `rm`：馬上離開 daemon 表，stack 留著；只有 `aos-agent ctl add` 能回來。`purge: true` 連 stack 一起刪，救不回來。
  - 都是寄出就回。
- **人用**：`aos-agent ctl state -t 名字 [類別...|all] [-j]`；`aos-agent ctl stop|pause|sleep|rm --no-wait`。
