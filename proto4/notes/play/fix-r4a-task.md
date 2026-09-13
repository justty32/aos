# fix-r4a：LLM 兩層（只改 `proto4-5/`）

r3 試玩清單 #1–#5（`proto4/notes/play/README.md` 的 r3 表）。兩個試玩的都在 LLM 這層第一步卡住，先把「照 README 做就能過」補齊，再修三個會花錢或會騙人的行為。

## 共通規矩（三本任務書都一樣）

- 你在 repo `/home/lorkhan/repo/simple_tools/aos`。先讀 `AGENTS.md` 開頭三軸與 `wf/workflows/dev-env.md`，再讀你要改的那個 proto 的 README 與原始碼。**不要讀 `proto4/notes/`** 以外的設計筆記；這本任務書引用的試玩報告在 `proto4/notes/play/2026-09-13-r3-opus.md` 與 `2026-09-13-r3-gptsol.md`，可以看。
- 動手前先跑 baseline 並記下數字：`proto4-3`：`cd proto4-3 && python -m unittest discover -s test`（226）；`proto4-4`：`cd proto4-4 && for t in aos step cpu; do janet test/$t.janet; done`（42／45／12，`janet` 在 `~/.local/bin`）；`proto4-6`：`cd proto4-6 && python -m unittest discover -s test`（71）。做完三邊都要重跑，數字只能變多不能變少。
- **只改任務書點名的資料夾**。另外兩本任務書同時在別的 codex 手上改別的資料夾，你碰了會撞。
- 程式碼與 README 單檔 **不超過 300 行**（`aos_kernel_tick.py` 285、`aos_kernel.py` 286、`aos-step-lua` 275 都在邊上）；要破就把一塊完整功能搬到新檔，行為不變。
- 每個行為變更都要有測試；README／`docs/` 同步改，大白話、繁體中文。
- LLM 真打只准本機 LM Studio（`http://localhost:1234/v1`，模型 `google/gemma-4-e4b`，已載好）；**不要碰 DeepSeek、不要讀任何 `*_API_KEY`**。單元測試用假的 OpenAI server（`proto4-5/test/_fake_openai.py` 已有）。
- **不 commit、不 push、不開 agent。** 最後用 markdown 回報：改了哪些檔、每條怎麼做、三邊測試數字、沒做或做不到的說清楚。

## 要做的

1. **README 貼 `endpoints.json` 完整範例**（#1）。現在 README 只寫「endpoints.json#local」，沒給檔長什麼樣，Opus 照猜寫 `{"local":{...}}` 退 2，最後靠 `llm-cpu init` 挖範例才知道是 `{"default":"local","endpoints":[...]}`。在「第一層」第一個 `call` 範例前面放一份**可以直接抄、只含本機 LM Studio** 的完整檔（單一 endpoint 檔與 endpoints.json 兩種各一份，五到八行）。結果檔欄位在 README 分三組講：日常（ok／text／usage／ms／error）、除錯（id／endpoint／model／model_requested／finish_reason）、原始供應商資料（raw，說明為什麼留著）。
2. **`aos-kernel llm … --wait` 成功時只印 `text` 與結果檔路徑**（#1）。現在整份 JSON 含 raw 倒到終端機。加 `--json` 才印整份。不等（沒 `--wait`）的維持印路徑＋「下一回合處理」。
3. **module 自動生的 `K/llm/endpoints.json` 只留 local**（#2）。DeepSeek、pi 那些範例搬到 README（或 `docs/endpoints-examples.md`）當文件，預設檔不放任何會花錢的東西。local 的 `model` 佔位字串旁邊在 JSON 裡沒法寫註解，所以：module 第一次生檔時印一行「請把 `K/llm/endpoints.json` 裡 local 的 model 換成 `aos-llm models` 看到的 id」；README 的 `$EDITOR K/llm/endpoints.json` 那行後面也補這句。
4. **模型名送出前先比對**（#3）。`strict_model` 為真的 endpoint，`aos_llm.call` 送 chat 之前先 GET `<base_url>/models`，要的 model id 不在列表就直接回 `ok:false`、`error.kind = "model_not_found"`、`retryable:false`，**不送 chat、不花 token**。`/models` 本身打不到（連不上、非 200）→ 不擋、照原本流程送（免得一個沒實作 /models 的服務整個不能用），並在結果的 `error` 以外找個地方記一筆（例如 `raw.preflight` 或新欄位 `notes`，你選簡單的）。`strict_model:false` 的 endpoint 完全跳過這步。事後的 `model_mismatch` 檢查保留。
5. **`model` 欄意思固定**（#3）。`model` 永遠是「對方回應裡的 model」，沒收到回應就 `null`；設定值一律看 `model_requested`。現在 connect 失敗時 `model` 放的是設定值，改掉，README 的欄位說明跟著改。
6. **`--wait` 逾時或 kernel 沒回應時的下場要誠實**（#4，gpt-sol 排第一）。現在退 1 說「kernel 沒回應」，但單子還留在 `K/syscalls/`，daemon 回來照跑、結果照出。改成：逾時當下檢查那張單——**還在 `K/syscalls/` 沒被撿走 → 撤掉（unlink）並印「沒送出去，已撤單」退 1**；已經被撿走（不在 inbox 了）→ 印「已送出，kernel 還沒做完；結果會出現在 `K/llm/results/<name>.json`，不要就 `aos-kernel llm rm`…」（如果 module 沒有 rm 子命令，就告訴使用者刪哪個檔）退 1。兩種訊息都要能讓人分辨「會不會有副作用」。
7. **同名同內容不報錯**（#5）。`aos-kernel llm K req.json --name X` 撞到已存在的 X 時：比對請求內容（把 req 正規化後算 sha256，存在 request 檔或 result 檔裡；結果檔若已有也算），**一模一樣就視為同一張**——印結果檔路徑、退 0，`--wait` 照等；內容不同才維持「id 已經存在」退 1，並補印撞到的是 requests／running／results 哪一個。這樣 `--reset` 重跑 `llm_submit` 不會卡死。README 說明這條規則。

## 測試

假 OpenAI server 加 `/models` 可控的行為（列表裡有／沒有／404），覆蓋第 4、5 條；module 測試覆蓋第 2、6、7 條（syscall 單子撤掉／已被撿走兩條路都要有；同名同內容退 0、同名不同內容退 1）。真打 LM Studio 一次確認第 4 條不會擋住正確的 model id。
