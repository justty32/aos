# 任務書：aos-agent 實作（2026-09-22）

使用者一句話：「往 agent 方向做。」規範已定：先看門（`waits`），再走一格（`idle`／`think`／`act`）。

## 要做什麼

照 [spec/aos-agent.md](../spec/aos-agent/README.md)（程式規範）＋ [spec/agent.md](../spec/agent/README.md)（資料夾、`state.json`
三格、`waits` 五個選項、錯誤代號）寫程式。讀驗 `info.json` 那塊已有 `aos_agent_info`、問模型已有 `aos_llm_ask`，
**都直接 import、不改它們的既有行為**。規範是老大；對不上的地方**不改規範**，寫進回報。

| 檔 | 職責 |
|---|---|
| `proto5/lib/aos_inst.py` | **補一個入口** `load_obj(obj, base, env=None) -> dict`：inst 已經是記憶體裡的 dict（工具檔的 `_meta`），不是檔案。走同一條 `_load`，文件用 `Document(None, obj)`（純記憶體），中心路徑＝`base`。`load()` 改成讀檔後叫它（或共用），既有 139 條測試不能動 |
| `proto5/lib/aos_exec.py` | **補一個入口** `run_inst(inst, stdin_text, timeout_ms=0) -> (code, kind, stdout_text)`：吃 `aos_inst.load_obj` 解好的 dict，stdin 塞一段字串（utf-8）、stdout 整段收回來（bytes → utf-8，`errors="replace"`）；stderr／exit／cwd／envs 照 inst 的欄位走（`_meta` 規範已禁止寫 stdin／stdout，agent_info 驗過；stderr 沒寫＝/dev/null）。mkdir／cwd 檢查／126／127／逾時砍 group 這些跟 `_run_inst` 一樣，抽共用、別複製一份。`kind` 同 `run_target`：`"child"`＝跑完了一次、`"aos"`＝沒跑成（mkdir 建不起來、cwd 不是資料夾、重導向開不起來） |
| `proto5/lib/aos_agent.py` | 主角。`step(dir, env=None) -> int`（回退出碼 0／101；讀驗錯丟 `AgentError`）＋ `main()`（`aos-agent [dir]`）。細節在下面 |
| `proto5/cli/aos-agent` | 薄入口，跟 `cli/aos-llm-ask` 一樣 |
| `proto5/lib/test/test_agent.py` | 測試（見下） |

## `aos_agent.step(dir)` 要做的事（照 aos-agent.md §2～§4）

1. **讀驗**：`aos_agent_info.load(dir, env)` 拿 info；再讀 `state.json`——不存在＝全部預設；存在＝讀原始 JSON（留著，
   之後要改寫）＋每格解指示詞（跟 info.json 同一套：`Context(Document(path, raw), base_dir=dir, env=env)`、位置＝實體路徑、
   `$opt` 只在 `waits` 的每一條吃）。驗：頂層物件；`state` 在原始 JSON 是字面字串且是三個之一（不然 `StateInvalid`）；
   `input` 解完是字串或字串陣列（不然 `FieldTypeMismatch`）；`waits` 在原始 JSON 是字面陣列或字面一條（一條＝字串或
   `$opt` 物件；整格是 `$ref`／`$env` 之類＝`FieldTypeMismatch`），每一條先 `resolve_located` 再 `parse_options`（表：
   `exists`／`mtime`／`consume`／`any`／`all`，都 `val: required`；`exists`×`mtime`、`any`×`all` 互斥→`OptionConflict`）、
   `$val` 再 `resolve`（位置加 `$val`），解完是字串或字串陣列（陣列每個元素也解）；`mtime` 沒 `since` 或 `since` 不是數字
   ＝`FieldTypeMismatch`。**讀驗不過＝什麼都不寫**，退出碼 1。
2. **門**（aos-agent.md §2）：逐條判「到了」；到了的先 consume（有開的話；`any` 只 consume 真的到了的那幾個檔）、再從原始
   `waits` 陣列按索引劃掉。有剩→寫回 `state.json`（只動 `waits`）、退 101。空了→若本來有條目就寫回 `[]`，接著走格。
   - 路徑相對 agent 資料夾；路徑指到資料夾＝裡面所有 `*.json`（`.done` 結尾的不算）。`exists`：檔存在／資料夾裡有任何一個
     `*.json`。`mtime`：檔的 mtime > `since`；資料夾＝裡面任何一個 `*.json` 的 mtime > `since`（我先這樣選）。
   - `consume`：rename 成 `<原名>.done`（`os.replace`，舊的蓋掉）；資料夾＝裡面當時在的 `*.json` 都 rename。
3. **走一格**（aos-agent.md §3 的表）：
   - `idle`：收 `input`（字串→一個路徑、陣列→多個，順序照寫；路徑是資料夾＝裡面 `*.json` 照檔名排序）。每個檔：字串→
     `{"role":"user","content":…}`；物件→一則（用 `aos_agent_info` 的訊息驗法，不合＝`MessageInvalid`）；陣列→一串（每則驗）。
     不存在或空陣列＝這個檔沒東西。全部都沒東西→不寫、退 101。有→接在記憶尾巴、**先寫記憶**（整份重寫）、再把每個讀過的
     input 檔 rename `.done`、最後寫 `state`＝`think`，退 0。
   - `think`：`aos_llm_ask.request_from_info(info)` 組 body、`aos_llm_ask.call(info["engine"], body)` 問一次；回來的
     `message` 接在記憶尾巴（原樣；`content` 是 `null` 且沒有 `tool_calls` 就補成 `""`，不然下次讀驗會 `MessageInvalid`）；
     有非空 `tool_calls` 陣列→`state`＝`act`，不然→`idle`；退 0。`EngineFailed`→stderr 一行 `aos-agent: engine: <白話>`、
     不寫任何東西、`state` 不變、退 0。
     **自癒（我先選的）**：進 `think` 時若記憶尾巴那則已經是帶 `tool_calls` 的 `assistant`（上次崩在寫記憶跟寫 state 之間），
     不問模型、直接 `state`＝`act`，退 0——不然模型那邊會因為 tool_calls 沒接 tool 訊息而一直拒絕。
   - `act`：尾巴那則 `assistant` 的每個 `tool_calls[i]`：名字＝`function.name`、參數＝`function.arguments`（字串原樣；
     不是字串就 `json.dumps`）。在 `info["tools_raw"]` 找同名工具→`_meta` 用 `aos_inst.load_obj(meta, base=dir, env)` 解→
     `aos_exec.run_inst(inst, arguments)` 跑。每個 call 接一則 `{"role":"tool","tool_call_id": <call 的 id，沒有就 ""> ,
     "content": …}`，順序照 `tool_calls`。`content`：exit 0＝stdout 原樣；非 0＝`工具 xxx 失敗（exit n）：`＋stdout；找不到
     ＝`沒有這個工具：xxx`；`load_obj` 丟 `InstError` 或 `run_inst` 回 `kind=="aos"`＝`工具 xxx 跑不起來：`＋那一行錯誤。
     全部接完→先寫記憶、再寫 `state`＝`think`，退 0。
     **自癒（我先選的）**：尾巴不是帶 `tool_calls` 的 `assistant`→不跑、`state`＝`think`，退 0。
4. **寫檔**：記憶＝整份 `json.dumps(ensure_ascii=False, indent=2)`＋換行；`state.json`＝原始 JSON 只換 `state`／`waits`
   那格、其他原樣（`json.dumps` 重排版沒關係）；`state.json` 本來不存在→寫 `{"state": …}`。一律 `.tmp` 再 `os.replace`。
   順序永遠：記憶 → input 檔 rename → `state.json`。
5. **`main()`**：`aos-agent [dir]`，`dir` 留空＝`.`；不是資料夾或旗標不認得＝2（stderr `aos-agent: usage: …`）；
   `AgentError`／`InstError` 讀驗錯＝1（stderr `aos-agent: <代號>: <白話>`）；不然回 `step()` 的 0／101。

## 測試（`proto5/lib/test/test_agent.py`；`_util.py` 可以加 `AgentCase` 的方法）

- 新入口：`aos_inst.load_obj`（跟 `load` 同結果、`$ref:""` 在純記憶體文件也對、錯誤代號）；`aos_exec.run_inst`
  （stdin 進、stdout 回、exit 非 0、127、逾時、cwd 不是資料夾＝aos）。
- 門：五個選項各自的「到了」（含資料夾、`.done` 不算）、`any`／`all`、`consume` 單檔與資料夾、部分到了→按索引劃掉、寫回
  只動 `waits`、其他格原樣；全到→`[]` 並走格；`waits` 每一條吃指示詞（`$fmt` 拼路徑、`$ref` 到別檔）；整格是指示詞＝
  `FieldTypeMismatch`；`mtime` 沒 `since`＝`FieldTypeMismatch`；不認得的選項＝`UnknownOption`；互斥＝`OptionConflict`。
- `idle`：三種檔內容、陣列多路徑、資料夾排序、不存在／空陣列＝101 不寫、rename `.done`、`state.json` 不存在時第一次寫出來、
  壞訊息＝`MessageInvalid` 不寫。
- `think`：用 `test_llm_ask.py` 那個 `FakeLLM`（搬到 `_util.py` 共用也行）：回話→`idle`、回 `tool_calls`→`act`、500／斷線→
  `state` 不變、記憶不變、退 0、stderr 有 `engine:`；自癒那條。
- `act`：真的 sh 工具（`_meta` 的 `argv` 用 `sh -c 'cat'` 之類回 stdin）、多個 call 順序、找不到工具、exit 非 0、`_meta` 壞
  （`InstError`）、`cwd` 不存在（aos）；接完 `state`＝`think`；tool 訊息的 `tool_call_id`。
- 寫檔順序：記憶先於 `state`（例如在 rename input 之前把 `state.json` 弄成唯讀，驗記憶已寫、state 沒動）。
- 命令列：0／101／1／2；`dir` 留空＝`.`。
- 既有 470 條不能動（`aos_inst.load` 的行為不能變）。

## 規則

1. Python 3.12 標準庫；不改 `aos_directives.py`、`aos_agent_info.py`、`aos_llm_ask.py`（真的非改不可再回報，改的話既有測試要照綠）。
2. 錯誤代號照 agent.md §5（`StateInvalid`／`FieldTypeMismatch`…）＋ directives.md §6；`aos_agent` 的錯誤用 `aos_agent_info.AgentError`。
3. `$env` 讀執行者環境（`step(dir, env=None)` 留一個參數給測試）；`$ref` 中心＝agent 資料夾。
4. 寫完：`proto5/lib/README.md` 加一節（＋新入口寫進 aos_inst／aos_exec 那兩節、測試表加列、標題「五支」改「六支」）、
   `proto5/README.md` 程式表加列、`wf/workflows/common/code-map.md` proto5 那列補一句。
5. 測試 `cd proto5/lib && python3 -m unittest discover -s test` 全綠。
6. 真跑一次：LM Studio 在 `http://127.0.0.1:1234/v1`（模型 `qwen/qwen3-1.7b`；沒開的話
   `/mnt/c/Users/WG-Guanyu/.lmstudio/bin/lms.exe server start --port 1234`，等幾秒再 `curl 127.0.0.1:1234/v1/models`）。
   在 `/tmp/claude-1000/-home-guanyu-projs-aos/c15290bb-f956-4ef2-8f96-46acea00faa2/scratchpad/agent-demo/` 建最小 agent：
   `info.json`（engine 指 LM Studio）、人格「有工具就用工具」、一份工具檔（例如 `now`：`_meta` 的 `argv` 是 `["date"]`）、
   `state.json` 預設、`input.json` 寫 `"現在幾點？用工具查"`。反覆叫 `cli/aos-agent <dir>` 直到它退 101，把每次的退出碼、
   `state` 變化、最後的記憶檔貼進回報（模型小、可能不叫工具，那就照實貼）。
7. 回報：做了什麼、測試數字、規範對不上或含糊的地方（條列）、自己拿不定的決定。不 commit。
