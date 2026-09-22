# 任務書：aos-agent 實作（2026-09-22）（精簡版）
完整版：[../notes/2026-09-22-agent-task.md](../notes/2026-09-22-agent-task.md)

## 要做什麼

使用者已定方向：「往 agent 方向做。」照既有規範實作 **先看 `waits` 的門，再走 `idle`、`think`、`act` 其中一格**。`aos-agent.md` 管程式，`agent.md` 管資料夾、state、waits 與錯誤代號。現成的 `aos_agent_info` 負責讀驗 info，`aos_llm_ask` 負責問模型，直接 import，保留既有行為。規範有矛盾就回報，不自行改規範。

## 要交出的程式與文件

| 檔案 | 要做的事 |
|---|---|
| `proto5/lib/aos_inst.py` | 加 `load_obj(obj, base, env=None) -> dict`，讓工具 `_meta` 這種記憶體 dict 也能走原來的 `_load`。文件用 `Document(None, obj)`，中心路徑是 `base`；`load()` 讀檔後共用此流程。原有 139 條測試不改。 |
| `proto5/lib/aos_exec.py` | 加 `run_inst(inst, stdin_text, timeout_ms=0) -> (code, kind, stdout_text)`。inst 已由 `load_obj` 解好；stdin 是 UTF-8 字串，stdout 整段收回，解碼用 `errors="replace"`。stderr、exit、cwd、envs 照 inst；stderr 未寫就用 `/dev/null`。工具 `_meta` 已禁止 stdin／stdout，交給 agent_info 驗證。 |
| 同上，執行共用邏輯 | mkdir、cwd 檢查、126／127、逾時砍整個 group，都與 `_run_inst` 抽共用，不複製。`kind="child"` 表示跑過一次；`kind="aos"` 表示根本沒跑成，例如 mkdir 失敗、cwd 不是資料夾、重導向開不起來。 |
| `proto5/lib/aos_agent.py` | `step(dir, env=None) -> int` 回 0／101，讀驗錯丟 `AgentError`；另提供 `main()`。 |
| `proto5/cli/aos-agent` | 仿 `cli/aos-llm-ask` 的薄入口。 |
| `proto5/lib/test/test_agent.py` | 補下表測試；可在 `_util.py` 加 `AgentCase` 方法，也可把 `FakeLLM` 搬來共用。 |
| 文件 | `proto5/lib/README.md` 加 agent 一節、補 inst／exec 新入口、測試表加列，標題「五支」改「六支」；`proto5/README.md` 程式表加列；code map 的 proto5 列補一句。 |

## 第一步：全部讀驗通過，才可以動檔案

先用 `aos_agent_info.load(dir, env)` 讀 info，再讀 state。`state.json` 不存在就用全部預設；存在就保留原始 JSON，改寫時只換需要動的格。

| 欄位／情況 | 必須遵守的驗法 |
|---|---|
| 指示詞上下文 | 與 info 相同，使用 `Context(Document(path, raw), base_dir=dir, env=env)`；位置是實體路徑。`$env` 讀執行者環境，`$ref` 中心是 agent 資料夾。 |
| 頂層、`state` | 頂層必須是物件；`state` 在原始 JSON 必須是字面字串，且只能是三格之一，否則 `StateInvalid`。 |
| `input` | 解完必須是字串或字串陣列，否則 `FieldTypeMismatch`。 |
| `waits` 外形 | 原始 JSON 必須是字面陣列，或單條字串／`$opt` 物件。整格若用 `$ref`、`$env` 等指示詞，報 `FieldTypeMismatch`；`$opt` 只在每條 wait 上處理。 |
| 每條 wait | 先 `resolve_located`，再 `parse_options`。`exists`、`mtime`、`consume`、`any`、`all` 都是 `val: required`；`exists` 與 `mtime`、`any` 與 `all` 各自互斥，衝突報 `OptionConflict`。 |
| wait 的值 | `$val` 再 `resolve`，位置加 `$val`；結果是字串或字串陣列，陣列元素也要解。`mtime` 缺 `since`，或 `since` 不是數字，都報 `FieldTypeMismatch`。 |
| 讀驗失敗 | **什麼都不寫，命令列退出 1。** agent 錯誤使用 `aos_agent_info.AgentError`，錯誤代號沿用 agent 與 directives 規範。 |

## 第二步：先看門

逐條檢查等待條件。條件到了，先做有開啟的 consume，再按索引從原始 waits 陣列刪掉該條。還有剩就只更新 `waits`，退出 101；全到了且原本有條目，就先寫回 `[]`，接著走當前那一格。

| 項目 | 行為 |
|---|---|
| 路徑 | 相對 agent 資料夾；指到資料夾時看其中所有 `*.json`，不算 `.done`。 |
| `exists` | 檔存在就算到；資料夾內有任何一個 `*.json` 就算到。 |
| `mtime` | 檔案 mtime 必須大於 `since`。Claude 暫選：資料夾內只要任一 `*.json` 較新，就算到。 |
| `consume` | 用 `os.replace` 改名為 `<原名>.done`，同名舊檔直接蓋掉。資料夾則把當時其中的 `*.json` 全部改名；`any` 只 consume 真正到達條件的那些檔。 |

## 第三步：只走一格

| 格子 | 正常流程 | 沒東西／失敗／恢復 |
|---|---|---|
| `idle` | 按 input 列出的路徑順序收檔；路徑是資料夾就按檔名排序讀 `*.json`。字串變 user 訊息，物件是一則，陣列是一串；物件與每則陣列訊息沿用 agent_info 驗法。不合法報 `MessageInvalid`。有訊息就接到記憶尾巴，先寫記憶，再把每個讀過的 input 檔改名 `.done`，最後寫 `state="think"`，退出 0。 | 檔不存在或內容是空陣列，表示該檔沒訊息；全部都沒訊息就不寫、退出 101。 |
| `think` | 用 `request_from_info(info)` 組 body，再 `call(info["engine"], body)` 問一次。回來的 message 原樣接到記憶；只有 `content=null` 且沒有 `tool_calls` 時補成空字串，避免下次讀驗失敗。有非空 tool_calls 陣列就去 `act`，否則去 `idle`，退出 0。 | `EngineFailed`：stderr 寫一行 `aos-agent: engine: <白話>`，記憶與 state 都不動，仍退出 0。Claude 暫選自癒：若進格時記憶最後已是帶 tool_calls 的 assistant，就不再問模型，直接改去 `act`；這處理了上次寫完記憶卻沒寫 state 的崩潰，也避免模型因未配對的 tool_calls 拒絕請求。 |
| `act` | 按尾端 assistant 的 tool_calls 順序逐一執行。以 `function.name` 找 `info["tools_raw"]` 的同名工具，`_meta` 交 `load_obj(meta, base=dir, env)`，再用 `run_inst(inst, arguments)` 跑。arguments 是字串就原樣傳，否則 `json.dumps`。每次都補一則 tool 訊息；全做完先寫記憶，再改 `state="think"`，退出 0。 | Claude 暫選自癒：尾端若不是帶 tool_calls 的 assistant，就不跑工具，直接改回 `think`，退出 0。 |

工具回覆一律帶 `role="tool"`、原 call 的 `tool_call_id`（缺 id 用空字串），content 依下表，順序與原 calls 相同。

| 結果 | content |
|---|---|
| exit 0 | stdout 原樣。 |
| exit 非 0 | `工具 xxx 失敗（exit n）：` 加 stdout。 |
| 找不到工具 | `沒有這個工具：xxx`。 |
| `load_obj` 丟 `InstError`，或執行回 `kind="aos"` | `工具 xxx 跑不起來：` 加那一行錯誤。 |

## 寫檔與命令列

| 項目 | 規則 |
|---|---|
| 記憶 | 整份 `json.dumps(ensure_ascii=False, indent=2)` 加換行重寫。 |
| state | 只替換原始 JSON 的 `state`／`waits`，其他格保留原意；重排版可以。原檔不存在，首次寫成 `{"state": …}`。 |
| 安全寫入 | 所有寫入先 `.tmp` 再 `os.replace`；順序永遠是 **記憶 → input 改名 → state**。 |
| CLI | `aos-agent [dir]`，省略 dir 就是 `.`。不是資料夾或未知旗標：退出 2，stderr 為 `aos-agent: usage: …`。讀驗 `AgentError`／`InstError`：退出 1，stderr 為 `aos-agent: <代號>: <白話>`；其餘回 step 的 0／101。 |
| 實作限制 | Python 3.12 標準庫。不改 `aos_directives.py`、`aos_agent_info.py`、`aos_llm_ask.py`；真的非改不可要回報，既有測試仍須全綠。 |

## 驗收與回報

| 測試面向 | 必須覆蓋 |
|---|---|
| 兩個新入口 | load_obj 與 load 同結果、純記憶體文件的 `$ref:""`、錯誤代號；run_inst 的 stdin／stdout、非零 exit、127、逾時、壞 cwd 回 aos。 |
| 等待門 | 五個選項、資料夾與排除 `.done`、any／all、單檔與資料夾 consume、部分到按索引刪除且只改 waits、全到寫 `[]` 並走格。每條能用 `$fmt`／跨檔 `$ref`；整格指示詞與缺 since 報型別錯；未知選項與互斥分別報 `UnknownOption`／`OptionConflict`。 |
| idle | 三種內容、多路徑、資料夾排序、沒有輸入時 101 且不寫、改名 `.done`、首次建立 state、壞訊息不寫並報 `MessageInvalid`。 |
| think | 用 FakeLLM 驗一般回話到 idle、tool_calls 到 act；500／斷線保持 state 與記憶、退出 0 且 stderr 有 `engine:`；另驗自癒。 |
| act | 用真 sh 工具回 stdin；多 call 順序、未知工具、非零 exit、壞 `_meta`、不存在 cwd、tool_call_id、完成後回 think。 |
| 寫入與 CLI | 驗證記憶先於 state，例如 input 改名前讓 state 無法寫，確認記憶已寫、state 沒動；CLI 的 0／101／1／2 與預設 `.`。 |
| 回歸 | 既有 470 條測試不改，`aos_inst.load` 行為不變。跑 `cd proto5/lib && python3 -m unittest discover -s test`，必須全綠。 |

還要真跑一次 LM Studio：endpoint `http://127.0.0.1:1234/v1`，模型 `qwen/qwen3-1.7b`。沒開就用 `/mnt/c/Users/WG-Guanyu/.lmstudio/bin/lms.exe server start --port 1234`，稍等後以 `curl 127.0.0.1:1234/v1/models` 確認。

示範資料夾指定在 `/tmp/claude-1000/-home-guanyu-projs-aos/c15290bb-f956-4ef2-8f96-46acea00faa2/scratchpad/agent-demo/`：info 指向該 engine，人格「有工具就用工具」，放一個 now 工具（argv 為 `["date"]`）、預設 state，以及內容為「現在幾點？用工具查」的 input。反覆呼叫 CLI 直到退出 101，回報每次退出碼、state 變化、最後整份記憶。小模型若沒叫工具，也照實記錄。

回報交代做了什麼、測試數字、規範矛盾或含糊處，以及自己拿不定的決定。**不 commit。** 上述資料夾 mtime 判法與兩條自癒是 Claude 暫選，不能藏成已由使用者拍板的規則。
