# wf/public/sol-排隊與額度 — sol 名額全體共用：排隊慢時怎麼辦、日額用光、掛法的幾個坑

← [wf/public](README.md)｜任務書、必讀清單、guard、rlimit 實測見 [sol-crew](sol-crew.md)；一行做法見 [recipes-隊員](recipes-隊員.md)

## sol 排隊很慢：小題隊長自己讀，大盤點或大施工改派 Claude 子 agent

llm-gpt 的 sol-high 名額全體共用（只有兩三個），十幾條線同時派 sol 時，開工半小時只寫幾百位元組、蒐集員近一小時沒交稿都會發生。

1. 先判斷是不是卡住：看 sol 的 history，只有十幾行、沒有改動，就是在排隊。
2. 小題目不必等蒐集：隊長自己讀關鍵六七個檔把設計寫出來，把蒐集員停掉、名額讓給施工員。
3. 大量對程式的盤點、大施工：改派 Claude 子 agent，任務書照用同一份（通常一小時內交回）；sol 留給範圍小、路徑明確的題。改派要經部長同意，也要守額度時段。原來的 sol 用 `subagent rm` 收（只是下表，stack 留著，不刪檔）。
4. 任務書本身也有責任：一張單塞八段題目、先要它讀六份必讀，會更慢。照 [sol-crew「任務書」](sol-crew.md)：一張單一件事、讀完同一回合就動手。
5. 看包的 sol 沒有 shell，量不了檔案大小這類事，隊長代跑（同 [sol-crew「guard」](sol-crew.md) 的代跑做法）。

## 暫存 llm kernel 的日額會讓整隊 sol 一起停

自己的暫存樹起了一台 llm kernel、好幾隻 sol 共用時：暫存 kernel 的 sol-high 有每日 `max_calls`（例 600），幾隻 sol 同一天用完，全部 `BudgetMissing … max_calls 600 reached in this window (day)` 停下。kernel 每輪重讀 kernel.json，改了數字以後 `ctl start` 就能繼續，不用重起 kernel；正在答的那則會丟掉，要重新 say 一次。每隻 sol 自己那份額度見 [sol-crew「腦額度」](sol-crew.md#rlimit-實測與腦額度)。

## 掛法的幾個坑

- **沒帶 `AOS_LLM_KERNEL`**：第一個 brain call 就 `LlmKernelMissing`。定義的 `.env` 要有它（[kits/gather](../workflows/dispatch/kits/README.md) 的 `.env` 已帶），或 `subagent add` 的 `envs` 帶 `{"AOS_LLM_KERNEL": "<llm-gpt 的 stack>"}`。
- **要開 headless Chrome 的隊員不能設 `mem_mb`**：AS 上限讓 Chrome 起不來，改用 `limits {"files":4096}`。
- **停下來的訊息措辭會改變行為**：hook 訊息寫 `Stop and report this as BLOCKED`，sol 就把整份工作丟掉。要接進流程的訊息，接線前拿真 sol 試一次。
- **借別線的假 agent 腳本先看信的格式**：例 `aos-agent say` 的信是 `{"body":{"role","content"}}`，照 `m["content"]` 讀會 `KeyError`。

## sol 施工員的任務書：五句寫死，驗收只要讀 diff、重跑新測試

派 sol 在暫存複本裡改程式、補測試時，寫死「只改暫存複本」「另一位在改哪些檔你不碰」「先跑改動前基準」「證明新測試會紅（暫時改回舊碼）」「貼真實輸出尾巴」。

## 縮工具清單之前先量它佔提示的幾成；快取命中低先看 session id

想省 sol 的額度時：

- 照問腦時實際送出的樣子量工具清單（`{type, function:{name, description, parameters}}` 的 JSON 字元數），再跟帳本上後段的提示大小比。例：55 支約 2 萬 token，sol 做到後段提示 7～15 萬，拿掉四成工具整體只省約一成。
- 帳本 `ledger.jsonl` 上 `cached_tokens/prompt_tokens` 常只中一個固定的小數字（共用的 system 加工具清單）、自己的對話一次都不中：不是請求內容在變，是請求沒帶固定的 session id（pack 的 `session_key`）；帶了命中八成以上，不帶兩三成。
- 驗「請求開頭有沒有變」：對自己隊員的 `think/request.json` 隔一分鐘各取一次，只存各段的雜湊比對，不存內容、不讀別線的 history。對照實驗要兩隻同時跑、各做一樣大小的真工作。
