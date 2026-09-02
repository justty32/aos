# experiments — LM Studio 並行度：本機實測、證據與待跑腳本

← [scheduling](README.md)｜交接書 [proto-S-scheduling](../../dispatch/proto/done/proto-S-scheduling.md)

**日期**：2026-08-30（隊 S）。**硬限制**：不 load／unload 模型，只 GET；所以「真並行」數字**今天量不到**（見 §一），
但 LM Studio 的並行槽數與過往請求的排隊行為可以從 server log 直接讀到（§二、§三）。

## 一、今天的端點狀態：沒有模型載入，POST 會觸發 JIT 載入

```sh
curl -s http://localhost:1234/v1/models | jq -r '.data[].id'
# qwen/qwen3.5-9b  google/gemma-4-e4b  google/gemma-4-12b-qat  text-embedding-nomic-embed-text-v1.5
curl -s http://localhost:1234/api/v0/models | jq -r '.data[] | "\(.id) state=\(.state)"'
# 四顆全部 state=not-loaded
lms ps          # No models are currently loaded.
lms server status   # The server is running on port 1234.
```

`~/.lmstudio/settings.json` 第 56–60 行：`"unloadPreviousJITModelOnLoad": true`、`"jitModelTTL": {"enabled": true, "ttlSeconds": 3600}`；
server log `2026-08-30.1.log:19`：`Just-in-time model loading active.`；同檔 `:157–191`：15:48:21 一個 POST `/v1/chat/completions` 直接觸發
`load_model: loading model … Qwen3.5-9B-Q4_K_M.gguf`；`:1513`：17:59:26 `Unloading model qwen/qwen3.5-9b due to TTL expiration.`。

**結論**：對這台機器，「打一次 chat/completions」＝「載入模型」，所以今天的並行度實測只能停在讀 log；真並行數字留給 §四的腳本，
由使用者在模型載好時跑（列入待使用者）。

## 二、並行槽數：LM Studio 預設把這顆模型開 4 個 slot

`lms load --help` 有旗標 `--parallel <count>`：「Maximum number of predictions the model can run at a given time. The speed of each individual
prediction may decrease with concurrency, but each prediction will start faster and higher total throughput can be achieved.」

沒帶旗標時本機實際的值，三天的 log 都一樣：

| log | 行 | 內容 |
|---|---|---|
| `2026-08-12.1.log` | 74、584、1113、1682、1759 | `load_model: initializing, n_slots = 4, n_ctx_slot = 71936 / 8192 / 57344, kv_unified = 'true'` |
| `2026-08-23.1.log` | 132 | `n_slots = 4, n_ctx_slot = 8192, kv_unified = 'true'` |
| `2026-08-30.1.log` | 191 | `n_slots = 4, n_ctx_slot = 8192, kv_unified = 'true'`（JIT 載入的那次） |

讀法：`n_slots = 4`＝llama.cpp server 可同時處理 4 條 prediction（continuous batching）；`n_ctx_slot`＝每槽 context；`kv_unified = true`＝
四槽共用一池 KV。**所以 LM Studio 這顆的並行上限預設是 4，不是 1**；VRAM 只夠載一顆模型是另一回事（並行是同一顆模型的槽數）。

## 三、過往請求的排隊行為：aos 打的從沒重疊；別的客戶端曾同時佔到 2 槽

`2026-08-23.1.log` 14 次、`2026-08-30.1.log` 18 次 `POST /v1/chat/completions`，每一次都是 `launch_slot_` → `release` 之後下一條才 `launch_slot_`；
連 16:05:28／33／35／38 十秒內四連發（`2026-08-30.1.log:543–713`）也是逐條完成（各 5.0 s、1.6 s、2.4 s、2.2 s）——因為呼叫端（`aos agent step`、`aos llm`）本來就是同步串行打的，
不是端點排隊。

codex（sol）把所有 server log 依 slot launch／release 掃過：`2026-07-14.1.log:2643–2789` 有真正重疊——task 15163（slot 0）與 15453（slot 3）同時跑 0.9 s，
15533 與 15453 重疊 3.3 s；`2026-04-14`、`2026-07-28` 也各見過同時 2 條。**最大同時 active 數＝2，沒有任何一天壓滿 4 槽**，也找不到「slot 全忙、請求排隊」的紀錄。
所以「4 槽真並行、第 5 條排多久」仍要靠 §四。官方文件（未經本機滿載驗證）：Max Concurrent Predictions 預設 4，超過者排隊；本機 app 版本 0.4.22
（`.internal/historical-version-info.json:10`）、llama.cpp runtime 2.31.2。

單次耗時的量級（qwen3.5-9b Q4_K_M，`2026-08-23.1.log:142–146`）：prompt eval 393 tok/s，生成 67.8 tok/s，440 token 總計 6.1 s；1177 token 的回覆 17.1 s（`:248`）。
**一次 agent 思考 2–17 秒**是這顆 CPU 的常態，正是回合被拖長的來源。

## 四、待跑：模型載好之後量並行度（不要在沒模型時跑——會觸發 JIT 載入）

```sh
#!/bin/sh
# 用法：先確認 `lms ps` 有 qwen/qwen3.5-9b，再 ./par.sh 1 && ./par.sh 2 && ./par.sh 4 && ./par.sh 8
N=${1:-1}; M=${AOS_LLM_MODEL:-qwen/qwen3.5-9b}
body() { printf '{"model":"%s","max_tokens":32,"messages":[{"role":"user","content":"count from 1 to 40"}]}' "$M"; }
one() { s=$(date +%s.%N); curl -s -o /dev/null -w '%{http_code}' -H 'Content-Type: application/json' -d "$(body)" http://localhost:1234/v1/chat/completions; e=$(date +%s.%N); echo " req $1 wall=$(echo "$e - $s" | bc)s"; }
export -f one body 2>/dev/null; export M
S=$(date +%s.%N); seq "$N" | xargs -P "$N" -I{} sh -c 'one {}'; E=$(date +%s.%N)
echo "N=$N total=$(echo "$E - $S" | bc)s"
```

怎麼讀：令 T1＝N=1 的 total。N=4 時 total ≈ 4×T1 → 端點**串行**（並行上限實際是 1）；≈ T1 → 真並行；介於（例如 1.5–2.5×）→ continuous batching
（同時跑但每條變慢——`--parallel` 說明文字預告的就是這個）。N=8 > `n_slots`=4 時，超出的請求會在端點內排隊，total 應接近 2×（N=4 的 total）。
把四行 `N=… total=…` 貼回本檔 §五。

## 五、實測結果（待使用者填）

| N | total | 每請求 wall（最小／最大） | 判讀 |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
| 4 | | | |
| 8 | | | |

## 六、DeepSeek 那顆（依知識，未驗證）

- OpenAI 相容端點 `https://api.deepseek.com/v1`。codex（sol）2026-08-30 查官方 rate-limit 頁：`deepseek-v4-flash` 帳號層級併發上限 2500、同帳號所有 key 共用、超限回 429、
  10 分鐘內沒開始推論會被斷線；沒有通用 RPM／TPM 數字。價格量級（V4 Flash，每 1M token）：cache-hit input $0.0028、miss input $0.14、output $0.28。
  所以使用者說的「同時 3 個」是 **aos 自己的 admission cap**，端點不會替我們擋，也遠低於官方上限。
- `core/agent/docs/pi-cpu.md` 的實測：`deepseek-v4-flash` 一次 pi step 1～4 秒，pi 在一次 step 內會**連續**多次呼叫（工具迴圈），對排程者而言是「一個佔住 slot 的長呼叫」而不是多個短呼叫。
- 價格量級與 RPM／TPM 要以官方頁面為準，本檔不抄數字。
