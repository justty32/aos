# sol 只回開場白：查 LiteLLM（2026-10-09）

## 結論

**答案其實有回來，是 aos 只讀了 `choices[0]`。**sol 系列（gpt-6-sol）會先講一段「我先確認…再跑三關」（後端標成 `phase: commentary`），再給答案本體（`phase: final_answer`）。LiteLLM 1.87.5 把 Responses API 轉成 chat 格式時不看 `phase`，**每一段 message 都變成一個 choice**。所以 `choices[0]` 是開場白，答案在 `choices[1]`。llmcall（`packs/llmcall/aos7_llmcall_litellm.py:76`）和 `core/llm/src/llm.cpp:188` 都只讀 `choices[0]`。

A5 的 5 次失敗都能從 raw.json 證實：4 次「只回開場白」和 1 次「空回覆」（`choices[0]` 是空字串），`choices[1]` 都有 8～13k 字的完整 JSON。那 5～6 千 token 是推理加上被丟掉的答案，沒有白算。

另一個原因是模型以為自己在 Codex 裡。LiteLLM 的 chatgpt provider 每次都會在指令最前面硬塞 litellm 內建的 Codex CLI 系統提示（`CHATGPT_DEFAULT_INSTRUCTIONS`，開頭是 "You are Codex… running as a coding agent in the Codex CLI"）。所以模型會想先看檔、跑指令。重放時有 3/4 次 sol-high 的 `final_answer` 寫「目前無法讀取原型檔」，交出 `files:{}`。F2 遇到的「我先確認工作區…」也是同一個原因。

不是「reasoning token 被算進輸出」：`completion_tokens` 本來就包含推理 token，跟這個問題無關。

## 怎麼測的（46 次呼叫，全是 gpt 系）

用 `probe.py` 直打 `localhost:4000`，不經 aos。內容是 A5 學徒 `diag-sol-r1` 的真實請求原樣重放（system 已經寫了「只輸出一個 JSON，不加說明」），每次只換模型。

| 變體 | 次數 | 有 ≥2 個 choice | 備註 |
|---|---|---|---|
| sol-high 非串流 | 4 | **4** | 有一次 3 段（開場白＋兩份 JSON） |
| sol（預設推理深度）非串流 | 4 | 3 | |
| sol-nothink 非串流 | 4 | 2 | 不推理也會分段 |
| astra-high 非串流 | 4 | 0 | 一律單段，14～17k 字 |
| sol-high 串流 | 3 | — | 只有 index 0，但開場白和 JSON **直接黏在一起**，沒有分隔，0/3 開頭是 `{` |
| astra-high 串流 | 2 | — | 2/2 開頭是 `{` |
| sol-high＋system 尾加「你沒有工具…第一個字元就是 {」 | 4 | **0** | 4/4 都是完整 JSON（9～11k 字） |
| sol-high 走 `/v1/responses` | 3 | — | 原生 output：2/3 是 `commentary`＋`final_answer` 兩段 message |

- 每個 choice 都沒有 `tool_calls`。`reasoning_content` 是空的，推理只留在 `reasoning_items` 的加密內容裡。每段的 `finish_reason` 都是 `stop`。
- 短的玩具提示（toy-prompt）從來不分段，要任務夠像 agent 工作才會出現。玩具那輪同時開 4 路並發，拿到 12 次 429，還有 1 次 sol-high 回 200 但沒有 choice、usage 是 null（3 秒就回）。這要另外留意：llmcall 會把它判成 `error`。
- 開銷：送一句 "hi" 的 `prompt_tokens` 是 1631，`total` 是 1644，就是 E1 量到的 1644。其中約 1.4k 是上面那段 Codex 提示。`cached_tokens` 常見 1408（只命中這段前綴），偶爾 4608（整份請求都命中）。

證據放在 `evidence/litellm-truncation/`：`replay.jsonl`（重放各變體，每個 choice 只留長度和前 80 字）、`responses-api.jsonl`（原生 output 項目和 phase）、`toy-prompt.jsonl`、`probe.py`、`responses_probe.py`。LiteLLM 的程式在 `litellm/completion_extras/litellm_responses_transformation/transformation.py` 的 `_convert_response_output_to_choices`（每個 `ResponseOutputMessage` 都 append 一個 choice）和串流的 `response.output_text.delta`（一律 index 0）。

## aos 這邊能做的（不用動 LiteLLM）

1. **llmcall 取答案的方式改成「最後一個 content 非空的 choice」**，不再固定讀 `choices[0]`。收據多記 `choices_n` 和被略過的開場白。`core/llm/src/llm.cpp` 也照這個改。這一條就能救回 A5 的 5 次重問，大約省 5 萬 token。測試要補「兩個 choice，第一個是開場白」和「第一個是空字串」兩種假回覆。
2. **提示詞**：凡是要求只回 JSON 的呼叫（作者、審查、up/brain），system 尾端固定加上「你沒有任何工具、不能看檔或跑指令，所需資料都在使用者訊息裡。不要說明計畫、不要開場白，第一個字元就是 {。」重放 4/4 有效，F2 也獨立驗證過。建議和第 1 條一起做，兩層保險。
3. **不要用串流拿 JSON**：sol 的開場白會黏在 JSON 前面，要切開只能猜。
4. **預設模型**：產出候選檔用 astra-high（8/8 單段，cache 也比較常命中）。sol-high 等第 1、2 條做完再用。審查本來就是 astra-high，維持不變。
5. 想做到最精準：改打 `/v1/responses`，挑 `phase == "final_answer"` 的 message。但改動比較大，先不做。

## 要使用者決定的 LiteLLM 設定（只是建議，沒有動）

- **A. 換掉 Codex 系統提示**：啟動 proxy 前設定環境變數 `CHATGPT_DEFAULT_INSTRUCTIONS`（litellm `llms/chatgpt/common_utils.py:256` 會讀它，目前的程序沒設）。例如改成一句「You are a helpful assistant. You have no tools; answer directly.」。好處是每次呼叫少大約 1.4k token（E1 說占 64%），模型也不會再以為自己在 Codex 裡。風險是 chatgpt 後端可能檢查 instructions：有些舊版 Codex 後端會拒絕非官方的 instructions。先用一個模型試打 200 再定案。代價是 astra 那 1408 的前綴 cache 也會跟著失效。
- **B. 回報 LiteLLM 上游**：chat 橋接應該看 `phase`，把 `commentary` 丟掉或併進 final，串流也一樣。這沒辦法靠設定修。等上游修好或升級前，靠 aos 的第 1 條處理。
- 套用 A 或升級 LiteLLM 之後，用 `probe.py` 重放一次（約 10 次呼叫）確認。

## 修補後（MC 隊，分支 loop10/mc）

做了三件事：llmcall 真傳輸與 `core/llm/src/llm.cpp` 改成取「最後一個 content 非空的 choice」，全部是空的才退回 `choices[0]`；被略過的開場白記進 `raw.json` 的 reply（`choices_n`，`skipped` 記每段的 index、字數、前 80 字）。回條的鍵順序是凍結的，所以這些不進回條。author 的 propose、審查、learn 三個 system 尾端都加上上面驗過的那句；learn 要的是條列，所以改成「第一個字元就是 -」。

**真 AI 重放**：經 llmcall 打 `chatgpt-gpt-6-sol-high`，共 6 次，請求是 A5 `diag-sol-r1` 原樣。其中 4 次用舊 system，2 次用新 system。

| 組 | 次數 | 有 2 個 choice | 回條 text 是完整 JSON | files 有 5 檔 |
|---|---|---|---|---|
| 舊 system（只靠取 choice 的修法） | 4 | 3 | 4/4 | 3/4 |
| 新 system（兩層保險） | 2 | 0 | 2/2 | 2/2 |

- 舊 system 那 3 次分段，回條拿到的都是 `choices[1]` 的 JSON（9.1～9.7k 字）。開場白（31～50 字）只留在 raw 的 `skipped`。修補前這 3 次會只拿到開場白。
- orig-2 的答案是完整的 JSON，但 `files:{}`（370 字）。原因是模型以為自己在 Codex 裡、讀不到原型檔，也就是上面講的「另一個原因」，不是取錯 choice。加了新 system 之後 2/2 都正常。
- token：6 次合計 54,804（每次 5.1k～10.8k）。
- 證據：`evidence/litellm-truncation/after-fix.jsonl`（每次的 choice 數、略過段、text 長度、usage），重放腳本是 `after-fix-run.sh`。
