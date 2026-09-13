# 任務書：四支逐步執行器加「宣告要等的檔」（wait_for）＋ `llm_submit`

你在 repo `/home/lorkhan/repo/simple_tools/aos`。**只准改 `proto4-4/`（`src/step.janet`、`src/aos.janet`、`test/`、`README.md`）與 `proto4-6/`**。**不要 commit、不要 push。** 不要開 agent。不要打真網路（LLM 相關測試用 `proto4-5/test/_fake_openai.py`；kernel 測試不開 daemon，直接叫 `aos-kernel-tick`）。`janet` 在 `~/.local/bin/janet`。開工前先跑三邊測試確認綠：proto4-4 三支 Janet、proto4-6 `python3 -m unittest discover -s test`（55 條）。

## 先讀

`proto4/notes/23-step-json-python.md` **§23.7（規則，照做）**；四支執行器：`proto4-4/src/step.janet`、`proto4-6/aos_step_json.py`、`aos_step_py.py`、`aos-step-lua`＋`step_common.py`＋`lua/aos.lua`＋`aos_py.py`＋`proto4-4/src/aos.janet`；`proto4-5/README.md`「第二層」（`aos-kernel llm K req.json --name ID` 不帶 `--wait` 會立刻回、結果在 `K/llm/results/ID.json`）。

## 要做

### A. 宣告的形狀（每種語言一個）

- Python：`aos.wait_for(path)` 回一個哨兵物件（例如 `aos.Wait(path)`，或 dict `{"$wait_for": path}`）；格函式 `return` 它。
- Lua：`aos.wait_for(path)` 回 `{["$wait_for"]=path}`；格函式 `return` 它。
- lisp（`aos.janet`）：`(aos/wait-for path)` 回 `{:aos/wait-for path}`；aos-step 看那格的**值**。
- JSON：元素多一個選填欄 `"wait_for": "out.json"`（執行 inst 之後才生效；inst 失敗就不生效）。
- 路徑：相對 → 以程式所在資料夾（`here`）為準轉絕對；存進狀態檔的是絕對路徑。

### B. 執行器行為（四支一致，能共用的放 `step_common.py`；Janet、Lua 各自寫一份同邏輯）

1. 每次被叫、讀完狀態後**先看 `waiting`**：有、且 `waiting.for` 這個檔**不存在** → `waiting.checks += 1`，寫回狀態檔，退出 0，不跑任何格、`last`／`history` 不動。有、且檔存在 → 刪掉 `waiting`（記一筆 `history` 項 `{"pc": after_pc, "step": "(wait)", "exit": 0, "waited_checks": n, …}`），繼續往下正常跑第 pc 格。
2. 跑完一格若回的是宣告：pc+1（跟成功一樣）、`last`／`history` 照記、多寫 `"waiting": {"for": 絕對路徑, "since": ISO 時間, "after_pc": 這格的 pc, "checks": 0}`，退出 0。
3. pc == n 而且沒有 `waiting` → 100（照舊）。pc == n 但還在等 → 照 1. 處理（等到檔出現才變 done；也就是最後一格也能等）。
4. `--status`：有 `waiting` 就原樣印在狀態 JSON 裡（本來就是同一份）；另外 stderr 一行給人看：`在等 /abs/out.json（已看 N 次，從 … 起）`。
5. `--reset` 連 `waiting` 一起清。
6. 改動偵測、失敗 pc 不動、退出碼，全部照舊。

### C. `llm_submit`（三個語言的 aos 模組）

- Python `aos.llm_submit(K, req: dict, name: str) -> str`、Lua `aos.llm_submit(K, req, name)`、Janet `(aos/llm-submit K req name)`：把 req 寫到 `here`（或 cwd）底下 `name + ".req.json"`，跑 `<repo>/proto4-3/aos-kernel llm K <reqfile> --name name`（`AOS_KERNEL` 環境變數可蓋路徑；**不帶 `--wait`**），退出碼非 0 → 丟例外／error（把 stderr 帶上）；成功回 `K/llm/results/name.json` 的絕對路徑。
- 用法就是：`state["r"] = aos.llm_submit(K, req, "q1"); return aos.wait_for(state["r"])`，下一格 `json.load(open(state["r"]))`。

### D. 測試（三邊都要；至少 16 條新）

每支執行器 3 條：宣告後 `waiting` 出現、pc+1、退出 0；檔不在時再叫 → 退出 0、`checks` 變 1、格沒跑（用副作用檔證明）；把檔建出來再叫 → `waiting` 消失、下一格跑了、`history` 有 `(wait)` 那筆。JSON 版用 `wait_for` 欄。加：最後一格等 → 檔出現前不是 100、出現後下一叫 100；`--reset` 清 `waiting`；`--status` stderr 有「在等」。`llm_submit` 一條端到端（Python 版就好）：`aos-kernel-init` 暫存家帶 `--module <abs proto4-5/llm_cpu_module.py>`，改 `K/llm/endpoints.json` 指到假 server，程式第 0 格 `llm_submit` + `wait_for`，然後在測試裡輪流叫 `aos-kernel-tick`（不開 daemon）與執行器，直到第 1 格讀到 `text == "hi"`。

```
cd /home/lorkhan/repo/simple_tools/aos/proto4-4 && for t in test/*.janet; do janet "$t" || echo "FAIL $t"; done
cd /home/lorkhan/repo/simple_tools/aos/proto4-6 && python3 -m unittest discover -s test 2>&1 | tail -2
```

### E. README

- `proto4-6/README.md` 三支共通段加「等一個檔」：規則五行、狀態檔 `waiting` 長什麼樣、Python 一個 `llm_submit`＋`wait_for` 的兩格範例；JSON 那節補 `wait_for` 欄；Lua 那節一句。250 行內。
- `proto4-4/README.md`：`aos/wait-for`、`aos/llm-submit` 各一句＋一個兩 form 的例子；「沒做什麼」補「等待沒有逾時、一次一個檔、kernel 不會叫醒」。

## 回報（十行以內，大白話）

改了哪些檔；三邊測試數與最後一行；自己決定的事、坑、沒做到的。
