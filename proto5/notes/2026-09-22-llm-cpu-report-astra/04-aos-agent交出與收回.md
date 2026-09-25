← [llm cpu 調查報告（astra）](../2026-09-22-llm-cpu-report-astra.md)（分檔 4/5）｜[上一份](03-llm-cpu-下.md)｜[下一份](05-kernel-module與落差.md)

**3．proto4-7：`aos-agent` 如何交出問題再收回**

**3.1 入口與資料夾**

`aos-agent`、`aos-user` 都只有兩行 shell，分別 `exec python3` 到 `aos_agent_cli.py`、`aos_user_cli.py`。agent CLI 引入 `proto4-6/aos_py.py`，作為呼叫 aos-exec／kernel 的 helper。[agent 入口:1](../../../proto4-7/aos-agent)、[CLI import:9](../../../proto4-7/aos_agent_cli.py)

| 路徑 | 內容 | 主要讀寫者 |
|---|---|---|
| `agent.json` | 名稱、system、K、限制、可選 stop | aos-user new 建；agent 讀 |
| `messages.json` | OpenAI messages 陣列，整份讀寫 | agent |
| `state.json` | 四格狀態與計數 | agent／reset；status 讀 |
| `req.json` | 最近一次 ask 組出的 request | ask 寫；不是排程器直接消費的信箱 |
| `<name>-eE-qQ-sS.req.json` | helper 臨時請求檔 | `aos_py.llm_submit` 寫，kernel CLI 讀；agent finally 刪 |
| `tools/<名>/tool.json` | description、parameters | new／外部建；ask/act 讀 |
| `tools/<名>/run` | 可執行工具 | act 經 aos-exec 跑 |
| `inbox/user/*.json` | 使用者信件 | aos-user 寫；idle 讀 |
| `inbox/user/read/` | 已讀信件 | idle rename 入內 |
| `outbox/<遞增編號>.json` | `{time,content}` | agent 寫；aos-user listen 讀 |
| `.listen-seen` | 已看 outbox 最大數字編號 | aos-user listen |
| `inst.json` | 絕對 aos-agent 路徑、cwd=A、stderr=`err.txt` | new 建；kernel 執行 |
| `err.txt` | agent stderr | 經 inst 執行時由 aos-exec 處理 |

`new` 建 agent.json、空 messages、信箱、outbox、echo/sh 工具與 inst；**不預先建立 state.json**。state 不存在時由 agent 使用預設值。[建立 agent:52](../../../proto4-7/aos_user_cli.py)

**3.2 `agent.json`**

| 欄位 | 型別／預設 | 實際用途 |
|---|---|---|
| `name` | 必填非空字串 | 組 request ID；本層沒有進一步驗證是否符合 llm ID 字元限制 |
| `system` | 必填非空字串 | 每次 ask 都前置一則 system message |
| `K` | 必填非空字串 | kernel 家；正常 step 要求其為存在的目錄 |
| `max_steps_per_question` | 正整數，排除 bool；預設 60 | 限制 ask 次數，並非所有四格執行次數 |
| `tool_output_limit` | 正整數，排除 bool；預設 8000 | 工具結果字串截斷上限 |
| `stop` | 僅 `is True` 觸發 | 直接退 100；此時略過 K 存在檢查及 state/messages 載入 |

agent 只檢查 K 是目錄，不在這裡驗證 `config.json` 或 llm module 是否存在；更深的問題在 submit 時才顯現。[設定驗證:25](../../../proto4-7/state_machine.py)

**3.3 `state.json` 全欄位**

預設：

```json
{
  "state": "idle",
  "epoch": 0,
  "question": 0,
  "step": 0,
  "request": null,
  "checks": 0,
  "errors": 0,
  "idle_since_error": 0,
  "stuck": false,
  "last_error": null,
  "outbox_n": 0
}
```

| 欄位 | 正常型別 | 意義／更新 |
|---|---|---|
| `state` | string | `idle`／`ask`／`wait`／`act` |
| `epoch` | 非負 int | reset 加一，用於 request ID |
| `question` | int | 每收到一個有效信件檔加一；檔內陣列仍算一題 |
| `step` | int | 每次進 ask 先加一；新題歸 0 |
| `request` | 絕對路徑字串或 null | **結果檔路徑**，不是請求物件或 syscall ID |
| `checks` | int | wait 看不到結果時加一；達 600 記錯 |
| `errors` | int | 模型／submit／文字工具修復錯誤累計；新題／reset 歸 0 |
| `idle_since_error` | int | idle 尾訊息是 user/tool 且未 stuck 時的重試等待計數 |
| `stuck` | bool | 阻止 idle 安全網再重問 |
| `last_error` | string 或 null | 最近錯誤；wait 驗收成功時清 null |
| `outbox_n` | int | 回話编号；寫信時另掃 outbox 最大编号，避免 reset 後覆蓋 |

載入時是「預設 dict 加上檔案內容」。明確驗證只有 `state` 合法、`epoch` 是非負整數且不是 bool；其餘欄位沒有逐一嚴格驗型，未知 key 也會保留。[defaults／load_state:14](../../../proto4-7/state_machine.py)、[outbox 编號:11](../../../proto4-7/mailbox.py)

`--reset`：讀舊 state，寫全新 defaults，只有 epoch=舊值+1；不刪 messages、outbox、舊 LLM 請求或結果。舊 state 讀壞時 reset 也會失敗。[reset:26](../../../proto4-7/aos_agent_cli.py)

**3.4 四格的实际狀態轉移**

| 現在格子 | 本次做什麼 | 下一狀態／退出 |
|---|---|---|
| idle，有有效信 | 一次收一個檔、接 user messages、清新題計數 | ask，0 |
| idle，只有壞信 | 回「有一封信讀不懂」、搬 read | idle，0 |
| idle，沒信、沒待答尾訊息 | 保存 state | idle，101 |
| idle，尾訊息是 user/tool 且未 stuck | `idle_since_error++`；未滿 20 繼續等 | idle，101 |
| 同上，第 20 次 | 計數歸 0，準備重問 | ask，0 |
| ask，step 超過上限 | 寫 stuck outbox、清 request/checks | idle、stuck=true，0 |
| ask，提交成功 | 保存結果路徑、checks=0 | wait，0 |
| ask，提交失敗 | `_record_error()` | idle，0 |
| wait，結果未到，checks<600 | 保存檢查次數 | wait，101 |
| wait，第 600 次未到 | `_record_error("timeout...")` | idle，0 |
| wait，結果失敗／格式內容不合 | 記模型錯誤 | idle，0 |
| wait，結果驗收成功 | checks=0、last_error=null | act，0 |
| act，有 tool calls | 接 assistant；同步跑完全部工具，接 tool messages | ask，0 |
| act，純文字 | 接 assistant、寫 outbox | idle，0 |
| act，疑似文字 tool call 救不回 | 記模型錯誤，不把該 assistant 接入 messages | idle，0 |

來源：[idle:94](../../../proto4-7/state_machine.py)、[ask:119](../../../proto4-7/state_machine.py)、[wait:172](../../../proto4-7/state_machine.py)、[act:200](../../../proto4-7/state_machine.py)。

**3.5 `ask` 到底怎麼送出去**

| 順序 | 實際操作 |
|---:|---|
| 1 | `step += 1`，先檢查題目上限 |
| 2 | 重新讀工具表 |
| 3 | 組 `messages=[system,*messages.json]` |
| 4 | 工具表非空才加 `tools` 欄位 |
| 5 | 原子寫 `A/req.json` |
| 6 | 組 ID：`<name>-e<epoch>-q<question>-s<step>` |
| 7 | 暫時 `chdir(A)`，呼叫 `aos_py.llm_submit(K, request, name)` |
| 8 | helper 直接 `write_text()` 到 `A/<name>.req.json` |
| 9 | helper 經 `aos_py.call()` 啟動 aos-exec，再啟動 `aos-kernel llm K <reqfile> --name <name>` |
| 10 | **沒有帶 `--wait`**；但 kernel CLI 本身仍同步等收件回音 |
| 11 | helper 確認子命令 `kind=child` 且 code=0 |
| 12 | helper 不解析 stdout 路徑，直接計算並回傳 `K/llm/results/<name>.json` |
| 13 | agent finally 恢復 cwd，刪除 helper request 檔 |
| 14 | 將回傳路徑存入 `state.request`，state 改 wait，保存 |

來源：[ask:119](../../../proto4-7/state_machine.py)、[llm_submit:150](../../../proto4-6/aos_py.py)、[aos_py.call:56](../../../proto4-6/aos_py.py)。

此 request **沒有** agent 自填的 endpoint、priority、timeout、params、model、tool_choice；使用 llm-cpu default endpoint 與其 timeout。

agent 不直接寫 `K/llm/requests/`。它寫本地 helper 檔，呼叫 kernel CLI，由 kernel syscall handler 真正投遞。

**3.6 `wait` 等什麼、怎麼判、何時退 101**

| 判定 | 行為 |
|---|---|
| `state.request` 空 | `AgentError("wait 沒有 request")`，CLI 退 1 |
| `Path(request).exists()` 為 false | checks 加一；1–599 次保存 state 後退 101 |
| 第 600 次仍無檔 | 記 timeout，checks 重設 0，轉 idle，退 0 |
| 檔存在，但讀不到／JSON 壞／頂層非物件 | AgentError，退 1；不算模型 errors |
| `result.ok is not True` | 取 error.kind/msg 記模型錯誤 |
| raw 沒有可用 `choices[0].message` 物件 | `bad_response: 沒有 choices` |
| assistant 沒有 truthy tool_calls，且 `str(result.text or "").strip()` 為空 | `empty_reply` |
| 其餘 | 轉 act；此格**不寫 messages** |

它只看結果檔，不讀 syscall 回單、不查 worker PID、不查 queued/running 狀態、不呼叫 `aos_py.wait_for()`，也不 sleep 等結果。[wait 原碼:153](../../../proto4-7/state_machine.py)

600 是 **agent 實際被叫到 wait 且查不到檔的次數**，不是 600 秒，也不是 kernel tick 數。

**3.7 收回時怎麼接 messages**

| 情況 | `act` 寫入 messages 的內容 |
|---|---|
| 正式 tool_calls | 原始 `raw.choices[0].message` 原樣 append；接著每個 call 一則 `{"role":"tool","tool_call_id":...,"content":...}` |
| 文字格式 tool call 被救回 | 建 `{"role":"assistant","content":text,"tool_calls":救回的calls}`，再接 tool messages |
| 純文字回覆 | 建新的 `{"role":"assistant","content":str(result.text or "")}`；不是保留整個 raw message |
| 工具失敗／不存在／參數壞 | 仍是 tool message 的 content，下一輪交模型看 |
| 正常回答 | 同時寫一封 outbox；清 request/checks，回 idle |

有 calls 時，一格內按順序同步跑完所有 calls。最後 `_save()` **先重寫 messages，再重寫 state**。result 留在 K，不消費、不改名、不刪。[act／save:200](../../../proto4-7/state_machine.py)

**3.8 錯誤、重試、逾時**

| 情況 | 處理 |
|---|---|
| submit helper 例外 | errors+1、last_error=`submit: ...`、回 idle，退 0 |
| result.ok=false | 記 errors；不看 `retryable` 是否 true |
| result 缺 choices／空白回答 | 記 errors |
| 文字工具呼叫救不回 | 記 errors |
| 正式工具不存在／非零退出／工具參數 JSON 壞 | 形成 tool result；**不增加 agent.errors** |
| `_record_error` 共同行為 | errors+1，idle_since_error=0、checks=0、state=idle |
| errors>=5 | stuck=true，寫「連錯 5 次…」outbox |
| 成功模型／工具輪 | **不把 errors 歸零** |
| 新有效信件 | 清 errors、stuck、last_error、step、request 等，question+1 |
| idle 自動重試 | 只有記憶尾巴為 user/tool、未 stuck，累計 20 次 idle 後轉 ask |
| 重試的 request ID | 下一個 ask 又 step+1，所以使用新 ID |
| agent 等結果超時 | 不撤銷原 request、不殺 worker |
| stop／reset | 不取消已送出的 LLM 工作 |
| wait／act 讀壞結果檔 | 退 1；沒有轉成可重試的模型 errors |

`_record_error()` 沒有清 `request`；錯誤後的 idle state 可能仍顯示上一個結果路徑。下一次成功 submit 才覆寫。[錯誤記錄:78](../../../proto4-7/state_machine.py)、[idle 重試條件:108](../../../proto4-7/state_machine.py)

**3.9 崩在中間的實際保障與缺口**

下列窗口由寫入順序推導；proto4-7 測試沒有故障注入驗證。

| 中斷點 | 留下的狀態／後果 |
|---|---|
| idle 已把信搬進 read，messages 尚未保存 | 信已不在未讀 inbox；沒有從 read 自動重播的機制 |
| idle 已寫 messages，尚未寫 state | state 仍 idle，messages 尾端是 user；無新信時可在 20 次 idle 後回 ask，但 question 等記帳沒有同步落下 |
| ask 已被 kernel 收下，尚未保存 wait state | 重開仍可能是舊 ask；step 重算出同 ID，同 request 可由 module 冪等接回 |
| 同上，但 system／messages／tools 已變 | 同 ID 不同 fingerprint，被拒；沒有保證所有 ask 重入都冪等 |
| wait 驗收後、state 尚未改 act | 下次再驗一次同 result；此時尚無 messages／工具副作用 |
| act 已執行部分工具，尚未保存 messages | 重開仍 act，會再跑工具；無逐工具完成紀錄 |
| act 已保存 messages，尚未保存 state | 重開仍 act，仍讀同 result，再 append assistant/tool、再跑工具；沒有用 messages 尾巴去重 |
| 純文字 act 已寫 outbox，尚未保存 state | 下次可能再寫一封；outbox 掃最大编号能避免覆蓋，但不避免重複回話 |
| helper 檔寫出後程序被硬殺 | finally 不一定執行，可能留下 `<name>.req.json` |
| 多份 agent 同時跑 | 沒有鎖；state、messages、outbox、temp 檔可競爭 |

proto4-7 的單檔 JSON 寫法是 `.tmp + os.replace`，沒有 fsync，也沒有跨檔 transaction。它與 proto5 文件中描述的 `think/act` 尾訊息自癒機制不能視為同一套保障。[原子寫 helper:15](../../../proto4-7/common.py)、[收信先搬 read:38](../../../proto4-7/mailbox.py)、[act 順序:217](../../../proto4-7/state_machine.py)

**3.10 工具怎麼跑**

| 項目 | 實作 |
|---|---|
| 工具搜尋 | `tools/` 直屬子資料夾，按名稱排序；tools 不存在代表無工具 |
| 名稱 | 資料夾名，不從 tool.json 另取 name |
| tool.json | 要有 string description、object parameters |
| schema 補值 | 以 `{"type":"object", **parameters}` 合成，再 `setdefault("properties",{})` |
| 已有 type/properties | 原值保留，並非強制改成 object／dict |
| 送模型格式 | `{"type":"function","function":{"name", "description", "parameters"}}` |
| run 的存在／可執行性 | load_tools 不檢查；實際執行時才發現 |
| 正式 call 參數 | dict 先 dumps；其他值轉字串，再 json.loads／dumps 正規化 |
| schema 驗證 | 沒有按照 parameters schema 驗參數 |
| 呼叫 | `aos_py.call(run, stdin=args_text, capture=True, timeout_ms=60000)` |
| stdout | 整段收進記憶體，再做字數截斷 |
| 非零退出 | content=`[exit N] `＋stderr 前 500 字＋換行＋stdout |
| exception | content=`工具執行失敗：...` |
| 找不到 run | content=`沒有這個工具` |
| 截斷 | 前 `tool_output_limit` 個 Python 字元，加 `…（截斷）`；不是 bytes 上限 |
| timeout | 經 aos-exec 對子行程 group TERM，2 秒後必要時 KILL |

来源：[工具宣告與修復:14](../../../proto4-7/agent_tools.py)、[run_tool:105](../../../proto4-7/agent_tools.py)、[aos-exec timeout:32](../../../proto4-3/aos_exec.py)。

**cwd 有一個重要細節**：通用工具是普通檔案目標，aos-exec 把 cwd 設為 run 所在的 `A/tools/<name>/`。內建 `sh/run` 自己算出 agent 根並 `cd`，所以它才是在 A 裡執行 shell。[普通檔案 cwd:88](../../../proto4-3/aos_exec.py)、[內建 sh:35](../../../proto4-7/aos_user_cli.py)

文字 tool call 修復：

| 輸入 | 修復方式 |
|---|---|
| 開頭 `<tool_call>`、`[TOOL_CALLS]`、`<function=` | 掃第一個括號平衡的 JSON object |
| 去空白後整段 `{...}` | 直接解析成 JSON object |
| candidate.name 不在已知工具 | 失敗，計一次模型錯誤 |
| 成功 | 只產生一個 call，ID=`call_<step>_1`；arguments 預設 `{}`，再 dumps |
| 一般文字包含 JSON 但不符合開頭形狀 | 不嘗試修復 |

它不是完整解析 XML／function 標籤，也不會從 `<function=foo>` 的標籤本身取工具名；仍要求 JSON object 裡有 `name`。[修復實作:43](../../../proto4-7/agent_tools.py)

**3.11 aos-user、信件與退出碼**

| 功能 | 實際行為 |
|---|---|
| `new --name --system --K` | 只允許不存在或空資料夾；寫 K 絕對路徑；不自動 kernel add，只印下一步 |
| `say "文字"`／stdin | 寫 timestamp 微秒檔名，內容 `{from:"user",time,content}`；空內容拒絕 |
| idle 收信 | `sorted(inbox.glob("*.json"))[:1]`：按**檔名**取一個 |
| 信件內容 | 物件或非空物件陣列，每筆要有 content |
| 接進記憶 | `{"role":"user","content":"[user] "+內容}`；非字串 content 用 JSON 序列化 |
| from/time | 不保留在 messages；都轉成 user 訊息 |
| 已讀同名碰撞 | 在 read 目的檔名加 timestamp |
| outbox | `{time:UTC微秒字串,content:string}`，编号至少四位，不以四位為上限 |
| `listen --once` | 印大於 `.listen-seen` 的數字檔；沒有就明說後退出 |
| `listen --new --once` | 忽略啟動時已存在的檔，200ms 輪詢；有新批次就印出後退出 |
| `listen` | 先印現有 outbox，再追新檔；不是只印未看過的 |
| `talk` | 背景 thread listen --new；前景讀「你>」，送到 inbox |
| listen/talk | 都不推進 agent、不替 kernel tick |

來源：[mailbox:38](../../../proto4-7/mailbox.py)、[listen:110](../../../proto4-7/aos_user_cli.py)。

| agent 退出碼 | 意義 |
|---:|---|
| 0 | 有進展，或模型／submit 錯誤已記入 state |
| 101 | idle 等信／等待重試，或 wait 尚無 result |
| 100 | agent.json stop=true |
| 1 | 已捕捉的 AgentError、ToolConfigError、OSError |
| 2 | argparse 用法錯 |

aos-user：正常 0；已捕捉的 AgentError／OSError／ValueError 為 1；argparse 用法錯 2。[agent CLI:18](../../../proto4-7/aos_agent_cli.py)、[user CLI:179](../../../proto4-7/aos_user_cli.py)

---

