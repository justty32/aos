# 任務書 3：把「一次呼叫」抽成第一層指令 `aos-llm`（像 cuda），worker 改叫它；lisp 端加 `aos/llm`

你在 repo `/home/lorkhan/repo/simple_tools/aos`。**只准改 `proto4-5/` 與 `proto4-4/` 底下的檔案**。**不要 git commit、不要 push。** 不要開其他 agent。不要打真網路（測試用假 server）。`janet` 在 `~/.local/bin/janet`。

## 先讀

`proto4/notes/22-llm-cpu.md` §22.6、§22.7（為什麼分兩層、規格）；`proto4-5/README.md`、`llm_cpu_worker.py`、`llm_cpu_home.py`（`load_endpoints`、`endpoint_document`）、`test/_fake_openai.py`、`test/test_worker.py`；`proto4-4/README.md`、`src/aos.janet`（`call`、`:read`、`:json` 的寫法）、`test/aos.janet`。

## A. `proto4-5/aos-llm`（薄殼）＋ `proto4-5/aos_llm.py`（函式庫＋命令列）

- **函式庫**：`aos_llm.call(endpoint: dict, req: dict) -> dict`——把現在 `llm_cpu_worker._request` 裡「組 body、打 HTTP、正規化回應、strict_model、錯誤分類」那段搬過來，**不碰任何檔案、不知道什麼是家**。回的 dict 就是 v1 results 的形狀（`ok`／`id`／`endpoint`／`model`／`model_requested`／`text`／`finish_reason`／`usage` 五欄／`ms`／`raw`／`error{kind,msg,status,retryable}`）；`id` 用 `req.get("id")`，沒有就 null。另一個 `aos_llm.models(endpoint) -> dict`：`GET {base_url}/models`，回 `{"ok","ids":[…],"raw","error"}`。endpoint 驗證（必要欄位、kind 只認 openai、`api_key_env` 沒設）也在這一層，錯就回 `ok:false` 的結果，不丟例外。
- **命令列** `aos-llm call ENDPOINT REQ OUT [--timeout-ms N]`：
  - `ENDPOINT`：路徑指到一個 JSON 檔——若檔裡是**一個 endpoint 物件**（有 `name`／`base_url`）就直接用；若路徑長 `FILE#name` 就讀 `FILE`（endpoints.json 那種 `{"default","endpoints":[…]}`）挑出 `name`；`FILE` 沒 `#` 但內容是 endpoints.json 形狀 → 用 `default` 那筆。
  - `REQ`：檔或 `-`（stdin）。內容照 v1 請求（`messages` 必填、選填 `priority`（這層忽略）、`timeout_ms`、`params`、`id`），**不准 `model`**。
  - `OUT`：檔（先 `.tmp` 再 `os.replace`）或 `-`（stdout）。
  - 退出碼：結果 `ok:true` → 0；`ok:false` → 1（結果照寫，錯誤一行也印到 stderr：`aos-llm: <kind>: <msg>`）；用法錯／檔讀不到／ENDPOINT 解不開 → 2，stderr 一句話。
- `aos-llm models ENDPOINT`：印 ids 一行一個；失敗退出 1。
- **`llm_cpu_worker.py` 改成叫 `aos_llm.call`**：讀 running/<id>.json、組 endpoint、呼叫、把結果寫 `results/`、append usage——行為與既有 28 條測試一個都不能變。worker 裡跟 HTTP 有關的程式碼全部刪掉（只留一份在 aos_llm.py）。
- 檔案超過 300 行照 STRUCTURE.md 拆。

## B. `proto4-4/src/aos.janet` 加 `aos/llm`

`(aos/llm endpoint req out &opt opts)`：
- `endpoint`：字串，原樣傳給 `aos-llm call`（相對路徑以呼叫者 cwd 為中心，跟 `:read` 一樣）。
- `req`：Janet table／struct，用 spork `json/encode` 寫到 `(string out ".req.json")`（同資料夾，方便對帳）。
- `out`：結果檔路徑。
- 做法：用既有 `aos/call` 叫 `<proto4-5>/aos-llm`（路徑跟 `aos-exec` 一樣的解法：環境變數 `AOS_LLM` 蓋過，預設 `<proto4-4 的上一層>/proto4-5/aos-llm`），參數 `["call" endpoint reqfile out]`，opts 合併 `{:read out :json true}`。**普通檔案目標會繼承三條流**，所以 aos-llm 的 stderr 會直接出現在 aos-step 的 stderr（這是想要的）。
- 回 `aos/call` 的結果 table（`:code`、`:kind`、`:out`、`:value`＝解好的結果 dict）；呼叫者拿 `(get-in r [:value "text"])`。
- `opts` 支援 `:timeout-ms`（給 aos/call，也就是整個子行程上限）。
- 加 `(aos/llm-text r)`：`ok` 真回 `text`，否則回 nil。

## 測試

- `proto4-5/test/test_aos_llm.py` 至少 10 條（用既有假 server）：單一 endpoint 檔成功 → 退出 0、OUT 形狀齊；`FILE#name`；`FILE` 無 `#` 用 default；`fail:500` → 退出 1、OUT 有 `error.kind http`、stderr 有 `aos-llm: http`；REQ 有 `model` → 退出 1 `bad_request`（或 2，選一種寫進 README）；REQ `-`／OUT `-`；ENDPOINT 檔不存在 → 2；`models` 印出假 server 回的 ids（假 server 加 `/v1/models` 路由，回 `{"data":[{"id":"fake-model"}]}`）；worker 既有 28 條全過。
- `proto4-4/test/aos.janet` 加 3 條：起假 server（`python3 <proto4-5>/test/_fake_openai.py` 要能當腳本跑：加 `if __name__ == "__main__"`，port 由參數給或印到 stdout；測試用 `os/spawn` 開、測完 kill），寫一份 endpoint 檔，`(aos/llm ep @{:messages [@{:role "user" :content "echo:hi"}]} out)` → `:code 0`、`(aos/llm-text r)` 是 `"hi"`；`fail:500` → `:code 1`、`llm-text` nil、`:value` 裡 `error.kind`；`.req.json` 檔存在且內容對。
- 全綠：
  ```
  cd /home/lorkhan/repo/simple_tools/aos/proto4-5 && python3 -m unittest discover -s test 2>&1 | tail -2
  cd /home/lorkhan/repo/simple_tools/aos/proto4-4 && for t in test/*.janet; do janet "$t" || echo "FAIL $t"; done
  ```

## README

- `proto4-5/README.md` 改成**兩層**開場：「第一層 `aos-llm`：像 cuda，給任何 inst 用的一次呼叫」（用法、ENDPOINT 三種寫法、退出碼、`models`）＋「第二層 `llm-cpu`：排程，收很多請求排隊派工」（現有內容縮一點）。開頭一句寫「第二層之後會變成 kernel module，見筆記 §22.7」。200 行以內。
- `proto4-4/README.md` 函式庫那節加「叫 LLM」：`aos/llm` 一個例子（endpoint 用 `endpoints.json#local`）、`aos/llm-text`、`AOS_LLM` 環境變數、「這是同步的：那一格會等到回應回來，幾十秒也等；要不等就走排程層」。

## 回報（十行以內，大白話）

改了哪些檔各幾行；測試數與最後一行（Python、Janet 三支）；自己決定的事、坑、沒做到的。
