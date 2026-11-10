aos-llm、aos-eca-turn、aos-eca-screen、aos-mcp 照 C-85 掃一遍（比 01～03 淺，都實跑過）。

← [入口](README.md)｜上一份 [03-aos-exec與copy-out](03-aos-exec與copy-out.md)｜下一份 [05-其餘指令](05-其餘指令.md)

實跑：llm kernel 用 `copy-out kernel/llm-kernel` 抄出、端點 `fake`（假腦）；eca 用 `cmd/aos-eca/tests/fake_claude` 放在 PATH 最前面（確認過沒有叫到真的 claude：假 claude 的呼叫紀錄有記到）。

# aos-llm（lv4——改法只列加法與訊息，行為改動留大修）

## 現況的一段白話

> aos-llm 是問腦的窗口。把一份請求（JSON，從 stdin 進）寄給 llm kernel：`ask` 寄完等回答；`send`／`recv` 把寄與收分開；`regret` 撤回還沒被接走的；`ls` 列出有哪些腦可選。kernel 在哪由環境變數 `AOS_LLM_KERNEL` 指。

## 裝不下的（七樣）

1. 請求要多包一層：`{"request": {"messages": […]}}`。
2. kernel 只能靠環境變數指，沒有旗標。
3. `send` 一定要 `--reply-to BOX`，BOX 得自己先 `aos-post init`。
4. `ask` 沒有逾時；kernel 沒開就一直等。
5. 退出碼 10＝「還沒有回信」。
6. 印出來的是整個 message 的 JSON，不是回答的文字；`--full` 再多幾格。
7. 「endpoint pack」這個詞。

## 怪點

**L1　人想試一下腦通不通，要手打一整段 JSON。**（真問題，但人不常打；加法）

```
$ echo 'hi' | aos-llm ask
aos-llm: error: RequestBad stdin must be one JSON document (the body): stdin is not JSON
$ echo '{"messages":[{"role":"user","content":"hi"}]}' | aos-llm ask
aos-llm: error: RequestBad stdin must be {"endpoint"?: name, "request": {"messages": [...], ...}, "priority"?} …
$ echo '{"request":{"messages":[{"role":"user","content":"hi"}]}}' | aos-llm ask
{"role": "assistant", "content": "FAKE ANSWER to: hi"}
$ aos-llm ask hi
aos-llm: error: ArgumentsBad ask takes no positional arguments …
```

`aos-tools call` 今天才加了行內寫法（`call NAME [ARGS_JSON]`）；這邊沒有對應的。有 `--priority` 旗標，卻沒有 `--endpoint`（要寫在 JSON 裡）。

**L2　kernel 沒開時 `ask` 無限等，沒有 `--timeout-s`。**（設計如此＋缺一個旗標）

```
$ AOS_LLM_KERNEL=/tmp/cli-sweep/deadk timeout 6 aos-llm ask < req.json
aos-llm: warning: /tmp/cli-sweep/deadk: no llm daemon here (no state.json: never started, pointing at def/, or started without --stack .?); letter sent anyway, the reply comes once it runs
[rc=124]
```

「印 warning、原地等」是使用者 11-10 裁的（HANDOFF 第 6 點「kernel 不在＝印 warning、原地等」），不動。只是全家其他會等的指令都有 `--timeout-s`，這支沒有。

**L3　`send --reply-to` 給一個不存在的信箱也成功。**（真問題，小）

```
$ aos-llm send --reply-to nobox < req.json
01794295670147434123.886087.2486825        [rc=0]
```

回信寄不到，寄的人不會知道。

**L4　指 kernel 的方式跟指 daemon 不一樣**：daemon 有 `-d`＋`$AOS_DAEMON`＋預設 `./.stack`；kernel 只有 `$AOS_LLM_KERNEL`（[06](06-跨指令不一致.md) X1）。使用者說過「llms我可能會用環境變數指定」，所以環境變數是主路沒問題；只是臨時想問另一台時沒有旗標可用。

**設計如此**：`recv` 收過一次再收＝退 10（實跑）；`regret` 只撤得回還在 `new/` 的；`ls` 的欄（name speed cost context slots backend summary）沒表頭（X7）。

**已知、不重報**：設計-58（共用回信信箱）、B16（問腦被 pause 的列沒兜底）。

## 照推薦改完後的一段白話

> aos-llm 是問腦的窗口。`ask "一句話"` 問一次、等回答（也可從 stdin 給完整的請求 JSON）；`send`／`recv` 把寄與收分開；`regret` 撤回；`ls` 列出有哪些腦。kernel 在哪由 `AOS_LLM_KERNEL` 指。

少掉 1（人用的時候）、4（有 `--timeout-s`）、6（行內問時印文字）。**這是 lv4，README 把它排在「留大修」，不在這輪推薦施工範圍。**

---

# aos-eca-turn（lv5；人平常不直接打）

## 現況的一段白話

> aos-eca-turn 讓外部的 coding agent（claude／codex）答一輪：把這隻 agent 信箱裡所有的信併成一段話交給 CLI，等它答完，把問與答寫進 history。平常是 loop 每圈叫它；`--one` 是把它當工具叫一次（stdin 給 `{"prompt"}`、stdout 拿回答）。

## 裝不下的（六樣）

`--on-empty stop|idle`、`--on-busy yield|answer`、冷卻（cooldown.json）、「之前的對話不在這台」時自動開新對話並帶紀錄（reseed_bytes）、`--prompt` 開場白、DEF_DIR 一定要絕對路徑。

## 怪點

**T1　定義資料夾只收絕對路徑；錯誤代號叫 `AgentBad`。**（真問題，小）

```
$ aos-eca-turn --one defs/eca
aos-eca-turn: error: AgentBad definition dir must be an existing absolute path, got 'defs/eca'
$ echo '{"prompt":"one shot"}' | AOS_STACK=… AOS_WS=… aos-eca-turn --one $PWD/defs/eca
FAKE: one shot
```

全家其他收資料夾的地方（aos-exec、ctl add、aos-eca-screen、copy-out）都收相對路徑。loop.json 裡是用 `{"$env": "AOS_CD"}` 給它，所以正常路線碰不到；只有人手動試才撞。（`aos-eca-turn:447`）

**T2　help 是一整面牆**（27 行、每行 130～150 字、沒有 `usage:` 也沒有 `flags:` 段）。內容都對，形狀跟 aos-agent 那一型差很多（X10）。這支是寫給維護者看的，補一個照家規排的 help 即可，內文搬去 README。

**設計如此**：五樣行為都是裁過的（冷卻、掉信、換台重開對話——HANDOFF 11-10 第 3、6 點）。

---

# aos-eca-screen（lv5；人用 aos-agent open／close／watch）

## 現況的一段白話

> aos-eca-screen 開、關、旁觀一隻 eca 的互動畫面。人平常不打它，打的是 `aos-agent open／close／watch`，那三個就是轉呼叫這支。

## 裝不下的（兩樣）

`--eca 資料夾` 必給、而且只能寫在動作前；哪一隻是靠 `AOS_STACK`／`AOS_WS` 兩個環境變數指的。

## 怪點

- **S1**　`aos-eca-screen watch --eca defs/eca` → `FlagUnknown unknown flag --eca`（同 A2、B5 的旗標位置）。
- **S2**　定義資料夾在這裡叫 `--eca ECA_DIR`，在 aos-eca-turn 是位置參數 `DEF_DIR`，在 `ctl add` 是 `XXX`（X10 佔位名）。
- **S3**　`watch` 閒置時安靜等（同 A8）。

都屬「補說明就好」；這支本來就註明「people normally use aos-agent open / close / watch」。

---

# aos-mcp（lv5）

## 現況的一段白話

> aos-mcp 把一份（或幾份）工具通訊錄裡的工具，變成 MCP 工具端給外部 agent（Claude Code 等）用：對方列工具、叫工具，它就轉給 aos-tools 去跑。

## 裝不下的（五樣）

1. 工作區一定要給（`--ws` 或 `$AOS_WS`），不會用現在站的地方。
2. 通訊錄是位置參數（aos-tools 是 `--file`）。
3. `--memory 名字`：開場時把知識庫根目錄當說明塞給對方。
4. `--enable-logs`／`--logs-path`。
5. 會在工作區留 `.stack/`。

## 怪點

**M1　不給 `--ws` 就報錯；而且先報這個、再報通訊錄不在。**（真問題，小）

```
$ cd /tmp/cli-sweep/proj && aos-mcp defs/ann/tools.json < mcp.in
aos-mcp: error: WsMissing no --ws and no AOS_WS, or it is not a folder
$ aos-mcp --ws . defs/ann/tools.json < mcp.in        ← 可以，三個回應都對（initialize、tools/list、tools/call wall_clock）
```

aos-exec 與 `aos-agent ctl add` 的 ws 都預設現在站的地方；這支不預設（`aos-mcp:114`）。可能是故意的（MCP 是被別的程式起的，cwd 不可靠）——拿不準，列給使用者。

**M2　通訊錄檔不在時的代號是 `ToolMissing`**（aos-tools 同一件事是 `RegistryBad`／另有 `ToolsMissing`）：

```
$ aos-mcp --ws .
aos-mcp: error: ToolMissing tools.json is not a file (give the path of a registry, e.g. tools.json; register tools with aos-tools --file it add)
$ aos-mcp --file defs/ann/tools.json
aos-mcp: error: FlagUnknown unknown flag --file
```

**M3　help 同 T2 是牆型**（18 行）。

**設計如此**：多份通訊錄合併、撞名報錯；每次 list／call 都重讀。

## 照推薦改完後的一段白話

同現況；多一句「工作區預設你現在站的地方」（若使用者同意 M1），help 換成家規形狀。
