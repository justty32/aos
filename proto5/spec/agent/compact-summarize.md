← [agent](README.md)｜[compact.md](compact.md)｜[compact-more.md](compact-more.md)｜[spec 總導航](../README.md)

# 記憶壓縮：`--summarize`（模型濃縮封存摘要）

（第三波 W3-2）機械壓縮（[compact.md](compact.md)）照舊算，**只多一步**：這次新生的每段封存摘要，中間那段送模型濃縮成幾句。
實作 [`lib/aos_agent_compact.py`](../../lib/aos_agent_compact.py) 的 `make_summarizer`；命令列在 [cli-memory.md](../aos-agent/cli-memory.md)。

## 1. 誰會叫模型

- **只有人跑的** `aos-agent compact --summarize [--model ALIAS]`。
- tick 自動壓縮（[compact.md §4](compact.md)）與 compact 申請（[compact-more.md §5](compact-more.md)）**一律不叫模型**，沒有設定鍵可以打開（代裁：自動那條持著 tick 鎖在 idle 一步裡跑，叫模型會讓每格多等幾秒、模型壞了還要處理退路；要濃縮就人跑一次）。
- `--dry-run --summarize` **不叫模型**（代裁：dry-run 保證什麼都不寫，叫模型就得記用量，兩者衝突；而且 dry-run 應該免費、立刻回）。它照樣先查設定（下一條），多印一行「正式跑會把 N 段封存摘要送模型濃縮」。

## 2. 設定與模型代號

- 設定跟 `aos-llm call` 同一份：環境 `AOS_LLM_CONFIG`＝`llm.json` 的絕對路徑（通常就是 kernel 那個 llm 池 `envs` 裡寫的那份）。人的終端要自己 `export AOS_LLM_CONFIG=/絕對路徑/llm.json`。
- 模型代號預設用這個 agent 自己的 `info.json` 的 `llm.model`；`--model ALIAS` 換別的代號。
- 設定讀不到、代號不在 `models` 裡＝`ConfigInvalid`／`UnknownModel` 退 1，**什麼都不動**（在拿到鎖之後、算之前查，dry-run 也查）。這是人的設定錯，不是模型壞了，所以不退回機械版。

## 3. 換什麼、不換什麼

- 只看**這次新生、有本體的**封存摘要（開頭是 `[aos 已封存較早的 N 輪（M 則），下面是機械摘要：`、結尾是「摘要以外的細節你看不到了…原文 … 第 i～j 則]」那種）。只剩一行的封存、記憶裡本來就有的舊封存，一律不送。一段都沒有＝不叫模型，印「這次沒有新的封存摘要，沒叫模型」。
- **開頭那行與結尾那句機械保留**，只換中間。開頭的「下面是機械摘要：」改成「下面是模型濃縮的摘要：」（代裁：不改就是說謊，讀的人分不出來）。
- 每段問一次模型（temperature 0、`max_tokens` 1024、不帶工具），系統提示要它：數字用阿拉伯數字照寫、檔名照寫、使用者交代要記的事寫成「使用者說……」、不編造、只回本文、一定比原文短。回的前後 ``` 圍欄會去掉。

## 4. 機械檢查（每段各自）

模型回的本文要**全部**過，不過＝那一段用機械摘要、印一行原因（`退回機械摘要：第 k 段：…`）：

1. 不是空的，也不含 `[aos`（免得跟封存標記混在一起）。
2. **比原摘要中間那段短**（UTF-8 bytes）。
3. **關鍵詞都還在**。關鍵詞＝從原摘要中間那段抽出來的：
   - **檔名**：「使用者：」與「呼叫 」那幾行裡像 `名字.副檔名`（副檔名英文字母開頭、1～8 字）的字，比對時只看最後一段（`/work/a/long.txt` 只要 `long.txt` 在）；結果內容行（常是一大串 `ls` 輸出）不算。
   - **「（N 行）」的 N**：每個工具結果的行數。
   - **使用者原話裡的數字**（`\d+` 或帶小數）；原話被截斷（`…` 結尾）時，緊貼 `…` 的那個數字可能是半截，不算。
   - 數字要以獨立的數出現（`40` 不能靠 `400` 過關）；檔名是子字串比對。

## 5. 模型失敗

模型出錯（`EngineFailed`、`Timeout` 等 `aos_llm_ask.ask` 丟的錯）＝**整次退回機械版**（已經濃縮好的前幾段也不用），**照樣完成壓縮**，印「模型出錯，整次退回機械摘要（照樣壓縮了）：<代號>：<原因>」，退 0。不重試。

## 6. 鎖、恢復、紀錄

- 叫模型的那幾秒**持著 tick 鎖**（人跑 compact 本來就持鎖）：這段時間 agent 的 tick 拿不到鎖、退 101，下一格再來；最久是 `llm.json` 那個代號的 `timeout_ms`（預設 120 秒）×段數。
- 崩潰恢復規則不變（[compact.md §3](compact.md)）：模型在**寫任何檔之前**叫，結果只影響新記憶的內容；archive 先寫、事件、記憶後換。崩在叫模型之後、換記憶之前，重跑會再叫一次模型（多花一次 token），結果可能不一樣，但記憶檔永遠是完整的舊版或新版。
- 每次模型有回（HTTP 2xx）就在那個家的 `log/usage.jsonl` 追加一行（`aos_llm_call.record_usage`），`batch` 是 `compact-summarize-<舊記憶 sha>`，跟 `compact` 事件的 `id` 對得起來。沒回（連不上、逾時）沒有用量可記。
- `compact` 事件多一格 `summarize`：`{"alias", "segments"（送了幾段）, "used"（用了模型版幾段）, "fallback"（每段退回的原因）, "error"（整次退回的原因或 null）, "prompt_tokens", "completion_tokens", "ms"}`；不放模型回的全文（全文在新記憶裡）。沒給 `--summarize` 就沒有這格。
- `aos-agent context` 的「上一次問模型，端點回報 prompt …」讀 `usage.jsonl` 最後一筆時**略過** batch 以 `compact-summarize` 開頭的（濃縮那一問送的不是這個 agent 的記憶）。

## 7. 真跑的數字

見 [notes/2026-09-24-tool-era/w3b/runs/compact/](../../notes/2026-09-24-tool-era/w3b/runs/compact/README.md)。
