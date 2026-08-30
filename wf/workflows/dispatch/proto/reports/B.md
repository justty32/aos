# 隊 B 回報：`aos agent` ＋ `aos llm`

← [交接書](../proto-B-agent.md)｜[PROTOCOL](../PROTOCOL.md)｜[dispatch](../../README.md)

**STATUS：DONE**
**worktree**：`/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a082c5e93227878c0`
**分支**：`worktree-agent-a082c5e93227878c0`
**commit**：`b391bd4`（實作＋文件）、`<本檔的 commit>`（回報）
**日期**：2026-08-30

## 做了什麼

兩個新的核心小專案，加上一份規劃文件與一份調查文件。

| 產物 | 路徑 | 狀態 |
|---|---|---|
| LLM client | `core/llm/`（`aos llm`） | 完成 |
| agent | `core/agent/`（`aos agent init/step/say/listen/talk/state`） | 完成 |
| loop 替身 | `core/agent/tests/fake_loop.py`（120 行，標準函式庫，掛進 ctest） | 完成 |
| 登記 | `core/CMakeLists.txt` 加兩行 | 完成 |
| 規劃 | `wf/workflows/ideas/self-delivery-in-loop.md` | 完成（等使用者拍板） |
| pi 介面 | `core/agent/docs/pi-interface.md` | 交文件，未實作 adapter |
| code map | `wf/workflows/common/code-map.md` 檔尾新節（61 行，只增不刪） | 完成 |

核心機制三句話：

1. **agent 就是一條普通 inst**。`step` 每回合結束前（**含丟例外時**）把下一個 `step`
   原子投遞回 `.aos/inbox/`，loop 對此一無所知。
2. **呼叫工具也是投遞**。登記表就是 `agents/<name>/tools.json`；LLM 在回覆最後一行輸出
   `{"tool":...,"args":...}`，`step` 依 argv 模板組成指令 JSON 投進 inbox。
3. **工具往返固定三回合**：N 投遞 → N+1 loop 執行 → N+2 從 `batch/<N+1>/out/<id>.json`
   讀結果餵回 LLM。這是 loop「先匯聚整批、並行跑完才寫 out」的必然結果。

## 驗收證據

全部由隊長在 worktree 根目錄親自重跑一次（不是只採信隊員回報）。

### 1. `cmake --build --preset default && ctest --preset default` 全綠

```text
1/7 aos_inst_tests ......... Passed    6.90 sec
2/7 aos_inst_capi_tests .... Passed
3/7 aos_tooljson_tests ..... Passed
4/7 aos_llms_tests ......... Passed
5/7 aos_llm_tests .......... Passed        ← 新增
6/7 aos_agent_tests ........ Passed        ← 新增
7/7 aos_agent_fake_loop .... Passed        ← 新增（python 的 loop 替身自測）
100% tests passed out of 7
```

新增的測試全部**不連外**：`step` 的 completion 以 callback 注入，測試傳固定回覆進去。

### 2. `echo '只回一個字：好' | aos llm` 真的打到 LM Studio

```text
好
exit=0
```

端點 `http://localhost:1234/v1`、模型 `qwen/qwen3.5-9b`（JIT 載入）。
**全程沒有呼叫 load／unload**。

### 3. `aos agent init W --name bob` 後 inbox 有 step、status.json 存在

```text
$ ls W/.aos/inbox/
agent-bob-0.json
$ cat W/.aos/inbox/agent-bob-0.json
{"argv":["aos","agent","step","/tmp/tmp.N4LRmuAUey","bob"],"id":"agent-bob-0"}
$ cat W/.aos/agents/bob/status.json
{"detail":"等待訊息","status":"idle","turn":0,"updated_at":"2026-08-30T08:05:33Z"}
```

`tools.json` 同時建好，預設三個工具 `sh`／`ls`／`cat`。

### 4. 跑三回合，每回合 inbox 都再出現一條新的 step（自我投遞成立）

```text
turn 1: 1 command(s)   →  inbox: agent-bob-1.json
turn 2: 1 command(s)   →  inbox: agent-bob-2.json
turn 3: 1 command(s)   →  inbox: agent-bob-3.json

state.json.agents = {'bob': {'detail':'等待訊息','status':'idle','turn':3,
                             'updated_at':'2026-08-30T08:05:33Z'}}
```

這三回合都**沒有叫 LLM**（沒有新 user 訊息也沒有新工具結果），只是自我投遞——省 token。

### 5. `say` → 跑一回合 → `listen` 出現 LLM 的回覆

```text
$ aos agent say W bob "你叫什麼名字"
$ python3 core/agent/tests/fake_loop.py W --step 1
turn 4: 1 command(s)
$ aos agent listen W bob --once
## turn 4 user
你叫什麼名字

## turn 4 assistant
我叫 Bob。需要幫忙嗎？
```

### 6. `self-delivery-in-loop.md` 存在，含「做不到什麼」與 loop 原生方案＋代價

`wf/workflows/ideas/self-delivery-in-loop.md`，118 行。

- **做不到什麼**：七條——靜默死亡、停不下來、三回合往返、狀態新舊、
  agent 互不可見無排程、id 撞名指數成長、邊緣狀況（只列不展開）。
  文中明確指出第 3／4／5 條與自我投遞無關，換任何方案都還在。
- **方案 A**：常駐投遞匣（`.aos/every/<id>.json` 或 `agents/<name>/next.json`），
  loop 每回合**複製不搬**。代價：若放 `agents/` 就破協定 §1、idle 回合消失、壞檔處理。
- **方案 B**：`status.json` 加 `next` 欄反向驅動。代價：觀測面變控制面、
  半路狀態會漏投、loop 得硬寫 agent 的 argv（分層倒轉）。
- **建議走 A 且放 `.aos/every/`**：loop 只多一個「每回合重投而不搬走」的投遞匣，不碰 `agents/`。
- 文末列五條待使用者拍板的問題，並明寫「只是規劃，還沒實作」。

### 7.（使用者追加）工具呼叫真的走 inst，結果被引用

```text
$ aos agent say W bob "看看目前資料夾有哪些檔案"
$ python3 core/agent/tests/fake_loop.py W --step 3
turn 5: 1 command(s)
turn 6: 2 command(s)        ← step 與工具指令同回合並行
turn 7: 1 command(s)

## turn 5 assistant
{"tool":"ls","args":"."}
> 已投遞工具 agent-bob-tool-5-0: ["ls","."]，等下下回合的結果

## turn 7 tool
$ ls .
exit=0
stdout:

## turn 7 assistant
（LLM 收到結果後繼續，這次改要 ls -la）
```

投出去的指令真的落進了 loop 的批次：
`W/.aos/batch/6/insts/agent-bob-tool-5-0.json`。`aos agent state` 同時顯示
`{"status":"tool","detail":"等工具結果","turn":7}`。

**誠實補充兩點**：

- 交接書追加要求寫「跑兩回合」，**實測需要三回合**——理由見上面的往返時序，
  這是協定 §5 的結構性後果，不是實作偷懒。
- 這次 `qwen3.5-9b` 拿到結果後選擇再呼叫一次工具（`ls .` 空 → 改 `ls -la`），
  而不是用散文引用。機制（投遞→執行→讀回→餵給 LLM）已完整走通並被 LLM 消費；
  「回覆長什麼樣」是模型行為，不是協定問題。另一次跑同樣流程時它就用散文答了
  （「目前資料夾中只有一個名為 `.aos` 的子目錄」）。

## pi 介面的結果

**結論：不做內建 adapter，交一份調查文件**（`core/agent/docs/pi-interface.md`，140 行）。

實測（每條都附了指令與輸出）得到三句話：

1. `pi` 0.84.2 是**完整的 LLM coding-agent TUI**，不是單純 REPL。
2. 它支援 OpenAI 相容自訂 provider 與 extension 自訂工具；沒有內建 MCP，但 extension 可加。
3. **能**以 extension 攔截輸入、完全跳過 pi 自己的 LLM，把外部程式的輸出顯示在 TUI ——
   所以技術上接得上 aos。實際做過 8 行 extension 的 RPC 與 TUI 驗證，
   成功顯示 `EXTERNAL_REPLY:hello` 且沒打 LLM。

三種接法與建議：

| 接法 | 判斷 |
|---|---|
| 專用 pi extension（`input` 事件轉 `aos agent say`，背景 `listen`，`pi.sendMessage(display:true)`） | **建議走這條**，最符合「思考只由 `aos agent step` 負責」 |
| OpenAI shim（讓 pi 以為我們是 provider） | 可行，但會製造兩份 session／history |
| MCP／tool 路線 | 不合需求——pi 自己的 LLM 仍會參與 |

沒有做 probe 腳本：8 行只能證明「外部回覆可顯示且不打 LLM」，
要誠實處理長駐 `listen` 的分幀、取消、重連，十行內做不到。
`aos agent talk --interface pi` 目前會明確報錯並指向這份文件。

## 團隊

- **codex gpt-5.6-sol ×5 條線**：`core/llm`、`fake_loop.py`＋smoke、pi 調查、`core/agent`、code map。
- **Fable ×1**：`self-delivery-in-loop.md`。
- **隊長**：規格（一份 SPEC 給全隊當唯一依據）、任務書、審 diff、驗收、commit。沒有親自寫實作。

## 給隊 A ／收線時要注意的

- `core/CMakeLists.txt` 我們加了 `add_subdirectory(llm)` 與 `add_subdirectory(agent)`
  兩行在檔尾——rebase 時就是協定 §7 預告的那個一行衝突。
- `wf/workflows/common/code-map.md` 我們**只在檔尾追加**（`git diff` 零刪除行），
  應該不會跟隊 A 的段落打架。
- `fake_loop.py` 落地後可以直接換成 `aos run`，協定不用動。它刻意忠實實作了
  「idle 回合不建 `batch/`」「`.json.tmp` 不收」「殺 process group 時 signal 填 9」
  「`agents/*/status.json` 原樣鏡射」這些細節。
