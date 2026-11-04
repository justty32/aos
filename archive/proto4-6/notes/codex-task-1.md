# 任務書：proto4-6 `aos-step-json`——一個 JSON 陣列、每個元素一份 inst、每叫一次跑下一個、狀態存外部 JSON

你在 repo `/home/lorkhan/repo/simple_tools/aos`。**只准新增／修改 `proto4-6/` 底下的檔案**（新資料夾，`proto4-6/notes/` 已有這本任務書）。其他一律不碰（別人正在改 proto4-3／proto4-5）。**不要 git commit、不要 push。** 不要開其他 agent。

## 先讀

`proto4/notes/23-step-json-python.md`（使用者原話與定案）、`proto4-4/README.md` 與 `proto4-4/src/step.janet`（逐步 lisp：pc 怎麼走、`--status`／`--reset`、改動偵測、回 100——**行為照抄，語言換 Python**）、`proto4-3/README.md`、`proto4-3/docs/exec.md`（inst.json 七欄、相對路徑以 cwd 為準、`aos-exec` 的退出碼 125／2）、`proto4-3/aos_exec.py` 的 `run_target()`（可以直接 import 當函式用：`code, kind = aos_exec.run_target(path)`）。

## 使用者要的（原話）

> 一個 json arr 檔案，裡面每個元素都是 inst 格式，逐一執行，狀態儲存於外部 json。最重要的是 ai 容易看懂，容易產出。

## 定案

- 檔案：`proto4-6/aos-step-json`（薄殼）＋ `proto4-6/aos_step_json.py`（Python 3 標準庫；超過 300 行就拆）。
- 用法：`aos-step-json PROG.json`（跑下一格）、`--status`（印狀態 JSON）、`--reset`（刪狀態檔）、`--stderr -|PATH`（原樣轉給 aos-exec，看不到錯誤時用）。
- **PROG.json**：嚴格一個 JSON 陣列，每個元素是一個 inst 物件（`argv` 必填；`cwd`／`stdin`／`stdout`／`stderr`／`exit`／`envs` 選填，語意完全照 inst.json）。允許元素多一個選填欄 `"note"`（字串，給人和 AI 註解用，執行前拿掉）。不是陣列／元素不是物件／沒 argv → 那一格失敗：stderr 一句話、退出碼 2、pc 不動。
- **相對路徑**：`cwd` 沒寫＝PROG 所在資料夾；相對 `cwd` 以 PROG 所在資料夾為準。其他欄位照 inst 規則（以 cwd 為準），**不要自己轉**，交給 aos-exec。
- **每格做什麼**：讀狀態（沒有＝pc 0）→ 取 `prog[pc]`、拿掉 `note`、把 `cwd` 轉絕對 → 寫到 `<PROG 所在資料夾>/.aos-step-json/current.json`（先 `.tmp` 再 replace）→ `aos_exec.run_target(current.json, stderr=旗標值)` → 記結果。
  - `kind=="child"` 且 `code==0` → pc+1，退出 0。
  - `kind=="child"` 且 `code!=0` → pc 不動，退出碼原樣回（修好重跑同一格）。
  - `kind=="aos"` → pc 不動，退出 125；`kind=="usage"` → 2。
  - pc 已經 == 元素數 → 什麼都不跑，`done:true`，退出 **100**（跟 aos-step、kernel 的 done_exit 一致；README 要講）。
- **狀態檔** `<PROG>.state.json`（跟 PROG 同資料夾、同名加 `.state.json`；例如 `job.json` → `job.state.json`）：
  ```json
  {"pc": 2, "n": 5, "done": false,
   "src": {"n": 5, "sha256": "…"},
   "last": {"pc": 1, "exit": 0, "kind": "child", "at": "2026-09-13T12:00:00+00:00", "ms": 12},
   "history": [{"pc": 0, "exit": 0, "kind": "child", "at": "…", "ms": 3}, …]}
  ```
  先 `.tmp` 再 replace。`history` 只留最近 50 筆。`--status` 就是印這份（沒有狀態檔就印 `{"pc":0,"n":N,"done":false}`）。
- **改動偵測**：`src.sha256` 是 PROG 內容的 sha256（Python 有 hashlib，不用像 Janet 那樣湊）。pc>0 且對不上 → stderr 一行 `aos-step-json: PROG 改過了（上次 N 個、現在 M 個），pc=k 可能已經錯位；確定要重來就 --reset`，照跑不擋，成功後更新 src。
- **訊息口吻**跟 aos-step 一樣：失敗印 `aos-step-json: 第 k 個元素（0 起算）失敗：exit=N`（child 非 0）／`aos-step-json: 第 k 個元素 aos-exec 自己失敗（125），加 --stderr - 看原因`。
- **放上 kernel**：README 給一份行程 inst.json 範例：`{"argv":["/abs/proto4-6/aos-step-json","job.json"],"cwd":"/abs/那個資料夾","stderr":"err.txt"}`——每格 kernel 跑一次、做完回 100 被收走。

## 測試（`proto4-6/test/test_step_json.py`，unittest，真開進程、暫存在 /tmp、跑完自己收；至少 12 條）

三個元素的 PROG（用 `sh -c` 寫檔／讀檔／`exit 3`）：初始 `--status` pc 0；跑一格 → 檔案出現、pc 1、狀態檔有 last 與 history；第二格用相對 cwd 子資料夾、沒寫 cwd 的元素 cwd＝PROG 資料夾；第三格 `exit 3` → 退出 3、pc 不動、再修成 exit 0 重跑 → pc 前進；全跑完 → 100、`done:true`、再跑還是 100；`--reset` 後 pc 0；`note` 欄不會傳給 aos-exec（元素帶 note 也能跑）；PROG 不是陣列 → 2；元素沒 argv → 2、pc 不動；cwd 不存在 → 125、pc 不動；`--stderr -` 看得到子程式的錯字；改 PROG 前面插一個元素 → 有警告行、照跑；狀態檔是合法 JSON 且 key 就是上面那幾個。

```
cd /home/lorkhan/repo/simple_tools/aos/proto4-6 && python3 -m unittest discover -s test 2>&1 | tail -2
```

## README（`proto4-6/README.md`，大白話、繁體中文、120 行以內）

一句話（給 AI 寫、給人看的最簡逐步程式：一個 JSON 陣列、每個元素一份 inst）；一份完整範例 `job.json`（三步：寫檔、讀檔、清理，帶 `note`）；怎麼跑（三次 `aos-step-json job.json`、`--status`、`echo $?` 看 100）；狀態檔長什麼樣；規則（pc 怎麼走、退出碼表、相對路徑、改動偵測）；放上 kernel；沒做什麼（沒有變數、沒有條件、沒有迴圈——那是逐步 Python 的事，§23.2）；出處。

## 回報（八行以內，大白話）

檔案與行數；測試數與最後一行；自己決定的事、坑、沒做到的。
