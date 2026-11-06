← [入口](README.md)｜件 2：endpoint 代號打包成能力包｜上一份 [01-self-tools](01-self-tools.md)｜下一份 [03-scheduling](03-scheduling.md)

# 件 2：endpoint 代號打包成能力包（fable 照原則定，可翻案）

使用者原文（11-05 午，逐字）：「把endpoint打包成smart-high, stupid-fast, ...這類，並且附上各種屬性(各種temperature也固定)」。前情：11-04 晚「各種llm設定也可以包裝，這樣寄信的時候只要寫簡單的代號就可以」已落成 `kernel.json` 的 `endpoints`（代號 → `url`／`model`／`key`／`body`／`exec`，[aos-llm-kernel docs/01](../../../../impls/aos-llm-kernel/docs/01-用法.md)）；`body` 現在是**預設**、信裡寫的蓋過它（`lib/base/llm_http`）。

## 已定（照原則推得出）

- **包＝`endpoints` 表的一組，代號就是能力名**（`smart-high`、`stupid-fast`、`local-qwen`、`fake`）。信與 `llm.json` 照舊只寫代號（P-23）；url／key 信改不了（N-42）。不另造「能力檔」格式：一組想獨立成檔就 `"smart-high": {"$ref": "packs/smart-high.json#/"}`（N-45 指示詞，用到那組才解；kernel 現在已這樣解，實作時驗一次）。
- **「固定」就是固定**（C-56 寫什麼就做什麼）：包釘死的參數不給信蓋。`body` 這個「預設、可蓋」的語意退場，改名 **`fixed`**（proto8 一律當沒有舊版、不留別名）。
- **kernel 只認自己要用的 key，其餘原樣交給 endpoint 函數**（C-48 不認得的忽略；現況已如此）。

## 代定（照推薦定，可翻案）

一組的形狀（全選填，除 `url`＋`model` 或 `exec`）：

```json
{"url": "...", "model": "...", "key": {"$env": "..."}, "exec": "...",
 "fixed": {"temperature": 0.2, "top_p": 1, "max_tokens": 4096},
 "slots": 1, "budget": {"max_calls": 200, "max_tokens": 2000000},
 "speed": "fast", "cost": "high", "context": 200000, "summary": "一句話給人與腦看"}
```

1. **kernel 看的**：`exec`（跑誰）、`slots`（這包同時幾封在飛，沒寫＝只受 kernel 總 `slots` 限）、`budget`（這包的窗內上限，窗跟 kernel 的 `budget.window` 同一個；`used.json` 多一格 `packs: {代號: {counter_calls, counter_tokens}}`）、`speed`（排序用，`fast`／`normal`／`slow`，沒寫＝`normal`）。這四個 kernel 拿掉後才交給函數。
2. **交給函數的**：`url`、`model`、`key`、`fixed` 與其他（`cost`、`context`、`summary` 函數不看、無害）。`llm_http` 的合併改成 **request 先、`fixed` 蓋上**；`model` 一律用包的。
3. **信裡寫了被釘死的 key**（`request.temperature` 而包有 `fixed.temperature`、或 `request.model`）＝kernel 回 **`RequestBad`**：`temperature is fixed by endpoint smart-high`（留題 1；見衝突）。`fake` 這類沒 `fixed` 的包照舊全收。
4. **agent-fsm 的 `llm.json` 拿掉 `model` 鍵**（只剩 `endpoint`）：包就是能力，臨時換同端點的模型＝換代號。eca 的 `model` 不經 kernel、不動。wait.py 比對 request 與 llm.json 的那段只比 `endpoint`。
5. **包的屬性表當一扇窗**：kernel 每次把 `{代號: {speed, cost, context, slots, summary}}`（不含 url／key／fixed／exec）寫成 `$AOS_STACK/endpoints.json`（有變才寫，N-05 暫存改名）；**`aos-llm ls`** 讀 `$AOS_LLM_KERNEL/endpoints.json` 印一行一包。給人挑代號、也給件 4 的父 agent 替子挑便宜的腦；腦自己要看就加一個工具叫 `aos-llm ls`（不在這輪做）。
6. **範本 `demo/llm-kernel/kernel.json`** 的表改成：`smart-high`（LiteLLM `localhost:4000`，`claude-haiku`〔便宜：每百萬 token 輸入 0.1／輸出 0.5 美金，整輪 demo 遠低於 0.5 美金；真名以 `curl localhost:4000/v1/models` 為準〕，`fixed.temperature` 0.2、`cost: high`、`speed: normal`、`slots: 4`）、`stupid-fast`（LM Studio `local-qwen`，`fixed.temperature` 0.7、`cost: free`、`speed: fast`、`slots: 1`）、`fake`、`fake-demo-*`（劇本假腦，給 steps 的 demo；見件 1、4）。`luna`／`sol` 照留。
7. **劇本假腦**：`llm_fake` 多認包裡一個 `script` 鍵（陣列；第 n 則 assistant 回答＝`script[n]`，n＝request.messages 裡已有的 assistant 數；超過＝原本 FAKE ANSWER）；一則＝`{"content": "..."}` 或 `{"tool_calls": [{"name": "self_tools", "arguments": {...}}]}`（llm_fake 補 id／type）。這是包「其他 key 原樣交給函數」的第一個正式用法。

## 衝突（哪條、在哪、各自後果）

- **C-56「寫什麼就做什麼」vs 使用者「temperature 也固定」**：信寫 `temperature: 1`、包釘 0.2——(a) 推薦 kernel 拒收 `RequestBad`，agent 得把釘死的 key 從請求拿掉（agent-fsm 的 brain 本來就不寫 temperature，零影響）；代價：想「請求給建議值、包有就蓋」的人得改寫請求。(b) 包默默蓋過、回信多一欄 `fixed_applied`——方便，但「我寫 1 它用 0.2」正是 10-16 說的埋雷。(c) 兩個 key 並存（`defaults` 可蓋＋`fixed` 不可蓋）——多一個旋鈕，使用者只說了固定。選 (a)。
- **P-23「選填 `model`（臨時換模型）放 `llm.json`」**：跟「包＝能力」相撞；代定 4 把 `model` 鍵拿掉、P-23 那句改成「換模型＝換代號」。後果：想同端點換模型就多登記一包（兩行 JSON）。
