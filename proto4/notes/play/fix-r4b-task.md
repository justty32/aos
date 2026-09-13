# fix-r4b：逐步執行器側（只改 `proto4-6/` 與 `proto4-4/`）

r3 試玩清單 #6 的執行器那一半、#7、#8（`proto4/notes/play/README.md` 的 r3 表）。kernel 那一半（看到 101 怎麼辦）由另一本 fix-r4c 在 `proto4-3/` 做，你只管執行器退什麼碼；兩邊約好的號碼是 **101**。

## 共通規矩（三本任務書都一樣）

- 你在 repo `/home/lorkhan/repo/simple_tools/aos`。先讀 `AGENTS.md` 開頭三軸與 `wf/workflows/dev-env.md`，再讀你要改的那個 proto 的 README 與原始碼。**不要讀 `proto4/notes/`** 以外的設計筆記；這本任務書引用的試玩報告在 `proto4/notes/play/2026-09-13-r3-opus.md` 與 `2026-09-13-r3-gptsol.md`，可以看。
- 動手前先跑 baseline 並記下數字：`proto4-3`：`cd proto4-3 && python -m unittest discover -s test`（226）；`proto4-4`：`cd proto4-4 && for t in aos step cpu; do janet test/$t.janet; done`（42／45／12，`janet` 在 `~/.local/bin`）；`proto4-6`：`cd proto4-6 && python -m unittest discover -s test`（71）。做完三邊都要重跑，數字只能變多不能變少。
- **只改任務書點名的資料夾**。另外兩本任務書同時在別的 codex 手上改別的資料夾，你碰了會撞。
- 程式碼與 README 單檔 **不超過 300 行**（`aos_kernel_tick.py` 285、`aos_kernel.py` 286、`aos-step-lua` 275 都在邊上）；要破就把一塊完整功能搬到新檔，行為不變。
- 每個行為變更都要有測試；README／`docs/` 同步改，大白話、繁體中文。
- LLM 真打只准本機 LM Studio（`http://localhost:1234/v1`，模型 `google/gemma-4-e4b`，已載好）；**不要碰 DeepSeek、不要讀任何 `*_API_KEY`**。單元測試用假的 OpenAI server（`proto4-5/test/_fake_openai.py` 已有）。
- **不 commit、不 push、不開 agent。** 最後用 markdown 回報：改了哪些檔、每條怎麼做、三邊測試數字、沒做或做不到的說清楚。

## 要做的

1. **等檔沒到改退 101**（#6）。四支（`aos-step-json`、`aos-step-py`、`aos-step-lua`、proto4-4 的 `aos-step`）現在 `waiting` 而檔沒出現時退 0、什麼都不跑。改成退 **101**（等待碼），其餘行為不變：狀態檔 `checks` 照加、不跑格、檔出現後同一次呼叫接著跑。號碼跟 100（全部做完）一樣是「kernel `config.json` 說了算」的預設值，執行器寫死 101 就好，README 在 100 旁邊加一句 101。手動跑的人看到 101 要知道是在等：stderr 印一行「在等 <path>（第 N 次）」（原本有印就維持）。
2. **Lua `aos.b64` 改回 `$b64` 物件**（#7）。`aos.b64(s)` 回 `{["$b64"]=<base64>}`（跟自動轉的長一樣，存進狀態檔、讀回來會還原成 bytes 字串）；`aos.unb64(x)` 物件與純 base64 字串兩種都吃。README 的 binary 那段改成一句話能講完：「不合法 UTF-8 的字串會自動變 `$b64`；想手動包就 `aos.b64`；兩者長一樣」。Python 那邊 `aos_py` 如果有 `b64`／`unb64` 也對齊同一規則。
3. **Lua 的 `ms` 改牆鐘**（#7）。現在用 `os.clock()`（CPU 時間），等子程式 8 秒還是 0。Lua 5.4 沒有 ms 牆鐘，讀 `/proc/uptime` 或用 `os.time()` 秒數乘 1000，二選一，README 說精度。Python／JSON 那兩支確認是牆鐘。
4. **`aos-step-lua --help`**（#7）。另外兩支有正常 help，Lua 回「不認得選項」退 2。補上，內容跟另外兩支同格式。
5. **Lua `return` 表漏列函式要警告**（#7）。用最笨的辦法：掃程式原始碼裡 `function <名字>` 與 `local function <名字>` 的名字，減掉 return 表裡 `fn` 對得上的（對不上函式物件就比名字），剩下的印一行警告「這些函式沒列進 return 表，不會被執行：a, b」，**不擋**。以 `_` 開頭的名字跳過（跟 Python 的 helper 慣例一致，README 寫）。
6. **錯誤全文改 `<PROG>.error`**（#8）。`.aos-step-py/error` 是每個資料夾一份，同資料夾跑第二支就蓋掉。三支統一：全文寫在狀態檔旁邊的 `<PROG>.error`（例如 `job.py.error`），錯誤訊息裡的提示字跟著改；成功跑過那格就把它刪掉。若 JSON／Lua 現在沒有這個檔，也一起有。
7. **README 五句**（#8）：Python 那節列 `aos.call` 的選項（現在只寫在 Lua 那節）；`out.req.json` 寫成 `<OUT>.req.json`；waiting 那段畫一條小時間線 `pc=3 的格回 wait_for → pc 變 4、狀態多 waiting → 檔沒到：退 101、只加 checks → 檔到了：清 waiting、記一筆 (wait)、接著跑第 4 格`；`llm`（同步、用自己的 endpoint 檔、不用 kernel）與 `llm_submit`（丟給 kernel 排隊、結果在 `K/llm/results/<name>.json`）是**兩個家**，一句話對比；`--reset` 旁邊警告「只重設執行器，不會清你的輸出檔或撤銷外部動作」。proto4-4 README 只改 101 那句與 `aos/llm-submit` 同樣的對比句。

## 測試

三支 Python 測試（`proto4-6/test/`）與 Janet `test/step.janet` 都要覆蓋：等檔沒到退 101、檔到了接著跑；Lua `b64` 物件寫入讀回；`ms > 0`（用 sleep 0.2 的 shell）；`--help` 退 0；漏列函式警告有印、`_` 開頭不印；`<PROG>.error` 兩支不同程式不互蓋、成功後刪掉。
