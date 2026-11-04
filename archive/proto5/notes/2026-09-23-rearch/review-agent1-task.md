你可以開自己的 subagent 平行做事（multi_agent 已開）。全程唯讀，不要改任何檔案。用繁體中文回報。

# 任務：審查 agent 線三份規範草稿（第一輪）

repo `../../..`。三份草稿（剛寫、還沒審過）：
- `proto5/spec/aos-llm-call.md`（新）：一支程式，組 body＋打 HTTP＋stdout 印 message。
- `proto5/spec/agent.md`（整份重寫）：agent 資料夾的 info.json／state.json。
- `proto5/spec/aos-agent.md`（整份重寫）：`aos-agent [dir]` 走一格：think／act 都是「寫 inst → 往 kernel `add --once` → 等 `K/responses/<名>.json` → 讀 → ack」。

它們要接的下層（今天四輪審過、已定稿）：`proto5/spec/cpu.md`、`kernel.md`、`daemon.md`；底層 `aos-exec.md`、`inst-posix.md`、`directives.md`。
舊版（被取代的，拿來對照哪些行為被砍、砍得對不對）：git 裡 `git show HEAD~1:proto5/spec/agent.md`、`git show HEAD~1:proto5/spec/aos-agent.md`、還在的 `proto5/spec/aos-llm-ask.md`、`llm-cpu.md`、`tool-cpu.md`。
現行程式 `proto5/lib/aos_agent.py`、`aos_agent_info.py`、`aos_llm_ask.py` 仍照舊版（新版程式還沒寫）。
背景與前幾輪審查在 `proto5/notes/2026-09-23-rearch/`（README 先看）。

使用者已拍板的前提（不要質疑）：所有 request 都是 aos-exec；llm／tool cpu 不是 cpu 種類、是程式＋cpu 的環境；agent 的問模型／跑工具都走 kernel `add --once`；ack 才刪回音；規則一（一個家一個主人）軟性。

草稿撰寫者自己選、要使用者拍板的三件（你可以評，但別替使用者決定）：同步工具整個拿掉一律經 kernel；agent 自己怎麼進 kernel（草稿假設「agent 是一個反覆行程」沒展開）；`llm.json` 放 agent 家還是共用。

## 要你做的

### A. 對得上下層嗎
逐條核對三份引用 cpu.md／kernel.md 的 §、鍵名、代號、檔名慣例（`add --once` 的 params、`K/responses/<名>.json`、ack 的 params、回音只報執行狀態不含輸出、`aos_client` 五步、`pool`、`timeout_ms`、`Interrupted`／`stopped`／`Removed`／`Stopping`）。哪裡對不上、哪裡假設了 kernel 沒承諾的事。

### B. 崩潰窗口與競態（agent 這層的）
think／act 的每一步：寫 inst → 放單 → 加 waits → 等 → 讀回音 → 讀 stdout 檔 → 接記憶 → ack → 寫 state。每個縫崩了下次怎麼接；waits 的門跟回音檔的關係（ack 之後回音消失、門就永遠開？）；連敗 3 次暫停；工具 arguments 檔跟 stdout 檔誰清、什麼時候清；同一個 agent 兩份同時跑；kernel stop／boot 期間 agent 在等會怎樣（`Stopping`、殘留回音留到下次 boot）。

### C. 砍得對不對
舊版被拿掉的：`engine.cpu`／`tool_cpu`／`_run`／waits 的 `mtime`／`any`／`ask-result.json`／`tool-results/`／同步工具／自癒的哪些條。每一項：砍了會不會少掉一個真的需要的能力；有沒有舊版的自癒規則在新版變成必要卻沒寫。

### D. 說明清不清楚、KISS 不 KISS
跟第四輪同樣的標準：第一次讀哪裡卡、名詞表夠不夠、三份「一句話」對不對、寫 agent 程式的 AI 照著能不能直接寫、有沒有多餘的檔或欄位（工作區四個資料夾 `insts/`、`llm-out/`、`tool-in/`、`tool-out/` 是不是太多）。

## 回報格式
markdown：1. 總評（五行內）；2. A：X-n；3. B：C-n（每條時序／後果／建議／嚴重度：擋／要修／可先放）；4. C：K-n；5. D：R-n（建議直接給改好的句子）；6. 「定稿前必改」清單 ≤ 12 條。不客套、不重講規範。
