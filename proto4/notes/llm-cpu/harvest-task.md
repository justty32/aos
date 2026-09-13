# 任務書：撈舊 proto 的「LLM 排隊／分發」遺產，逐條說採不採（給下一段 LLM cpu 用）

你在 repo `/home/lorkhan/repo/simple_tools/aos`。這是**只讀研究＋寫一份報告**，不是改程式。**只准新增 `proto4/notes/llm-cpu/legacy-harvest.md` 這一個檔**，其他路徑一律不碰（另一個人正在改 `proto4-3/`、`proto4-4/`，別動）。**不要 git commit、不要 push。** 不要開其他 agent。**不要打任何網路、不要碰 LM Studio、不要印任何 API key／token 的值**（環境變數 `DEEPSEEK_API_KEY` 只准提名字）。

## 背景（使用者原話，照這個方向讀）

> llm cpu 的一格，你可以參考 proto2,3,4，我是認為 llm cpu 他就是很普通的，收到很多個 llm 呼叫請求，然後做排序，分發給不同 endpoint 那樣，整圈推論工具執行那是 agent 的事情。llm cpu 可以先基於普通 cpu 去做。

> 先前幾個版本的 proto 都是可以參考的遺產，只是謹慎採用。

所以 LLM cpu 的定義：**一顆普通 cpu（aos-run 反覆跑一份 inst.json）上跑的一支程式**，每格做一輪：收請求 → 排序 → 分發給 endpoint → 把結果放回去。不做 agent 迴圈、不做工具呼叫。endpoint 目前三種：本機 LM Studio（`localhost:1234`，OpenAI 相容，**一次只能載一顆模型、換模型要先 unload**）、DeepSeek（`DEEPSEEK_API_KEY`，OpenAI 相容）、`pi -p` 子行程（CLI agent，之後才接）。

## 先讀現在的方向（免得建議跟已定案的打架）

- `proto4/notes/20-21-step-lisp-and-next.md` 的 §21、§21.1、§21.6、§21.7（LLM cpu 是什麼、Claude 訂閱怎麼接、CLI agent 子行程）。
- `proto4/notes/07-10-inst-json-cpu.md`（cpu＝aos-run 反覆跑 inst.json；§8 行程不需要知道自己被誰跑）。
- `proto4-3/README.md`、`proto4-3/docs/exec.md`（inst.json 長什麼樣、三條流的規則）、`proto4-3/docs/kernel.md`（行程排進 `procs/`、做完回 100）。
- `proto4-4/README.md`（逐步 lisp 怎麼叫資料夾、`:read`＋`:json` 把結果讀回來——LLM cpu 的「請求」很可能就是 lisp 這樣叫出去的）。

## 要撈的地方（全部本機）

1. **proto（第一版，Python）**：`proto/aosp/llm.py`、`proto/README.md` 的 `llm <op>` 那列與底下三段（`max_wait_ms`、`.aos/llm-inflight/`、帳簿 `tokens_out`／`tokens_reasoning`）、`proto/FINDINGS.md`（尤其第 4 條「LLM 世界的圈跟 run 的走格是兩套」）、`proto/examples/llm-echo/`、`proto/tests/test_llm.py`。
2. **proto2（Python）**：`proto2/aos_llm.py`、`proto2/aos-llm`、`proto2/docs/llm-scheduling.md`、`proto2/docs/cost.md`、`proto2/notes/tools/cost-metering.md`、`proto2/tests/sched.sh`、`cost.sh`、`anthropic.sh`、`claude_cli.sh`、`proto2/README.md` 裡 aos-llm 那段。
3. **proto3／proto3-1／proto3-2（Janet）、proto4-1、proto4-2**：`grep -ril "llm\|endpoint\|deepseek" <dir>` 掃一下，有東西才讀，沒有就寫一行「沒有 LLM 相關」。
4. **reference/llmkit/**（freepy 搬來的 Python，「已定型」的 LLM client）：`llms/client.py`、`engine.py`、`presets.json`／`presets.py`、`usage.py`、`caps.py`、`reply.py`、`llms/README.md`、`USAGE.md`；`proxy/litellm.yaml`、`proxy/README.md`。這是**打 OpenAI 相容 endpoint 的成熟寫法**，重點看：請求怎麼組、串流不串流、usage 怎麼算、錯誤與重試、preset 怎麼描述一個 endpoint＋模型。
5. **core/llm/**（C++，凍結分支搬回來的）：只看 README 與標頭，寫兩三行它定了什麼介面，不深讀。

## 報告 `proto4/notes/llm-cpu/legacy-harvest.md`（繁體中文、大白話、250 行以內）

1. **一段總覽**：每個來源一句話——它把 LLM 那塊做成什麼樣、最後為什麼被放下（從 README／FINDINGS／notes 裡找，找不到就寫「沒寫」）。
2. **逐題比對表**（每題一個小節，每個來源一行「它怎麼做」＋一行「採／改採／不採 ＋ 為什麼」；「為什麼」要對得上上面「現在的方向」）：
   - (a) **請求長什麼樣**：一份檔？JSON 欄位有哪些（prompt／messages、model、endpoint、max_tokens、優先級、逾時、回哪裡）？請求放哪個資料夾、誰寫進去？
   - (b) **排隊與排序**：FIFO？優先級？`max_wait_ms` 那種「排隊上限」？一格處理幾件？
   - (c) **endpoint 怎麼描述、怎麼挑**：設定檔長怎樣？模型→endpoint 對應？多個 endpoint 怎麼分（輪流、指定、依模型）？
   - (d) **在飛中（inflight）怎麼記**：搬資料夾？寫狀態檔？cpu 一格只有幾秒，一次推論可能幾十秒——它怎麼處理「送出去了、還沒回來」跨格這件事？（**這題最重要**，跟「一格＝一輪」直接衝突。）
   - (e) **結果怎麼回**：寫到請求指定的檔？回件匣？呼叫者怎麼知道好了？
   - (f) **帳簿**：tokens／cost 記哪裡、格式？
   - (g) **逾時、重試、錯誤**：後端掛了怎麼辦、部分失敗怎麼記？
   - (h) **本機模型的載入／卸載**：有沒有人處理過「一次一顆」？沒有就寫沒有。
   - (i) **測試怎麼做的**：假 endpoint？錄放？能不能搬來用？
3. **建議的 LLM cpu v1 骨架**（只是建議，使用者拍板）：資料夾長什麼樣（請求進哪、在飛放哪、結果出哪、設定放哪）、請求 JSON 的最小欄位、一格做什麼（含跨格的在飛怎麼處理，給兩個方案＋你推薦哪個）、endpoint 設定檔最小長相（三種 endpoint 各一筆範例，key 只寫環境變數名）、v1 明確不做的。**KISS，越小越好**；能直接沿用 `proto4-3/aos-exec` 的 inst.json 慣例就沿用。
4. **要問使用者的**（最多 5 條，每條一句，附你的預設答案）。
5. **附：讀過的檔案清單**（路徑＋行數）。

## 回報（八行以內，大白話）

- 一句話結論（舊遺產裡最值得撿的是哪兩三樣）。
- 報告幾行。
- 你最不確定的一件事。
- 確認沒印 key：`grep -rn "sk-\|DEEPSEEK_API_KEY=" proto4/notes/llm-cpu/` 要是空的。
