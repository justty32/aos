# code map — core/llms/

← [code map 總圖](../code-map.md)｜[本資料夾導覽](README.md)

`core/llms/` 這個小專案的逐檔職責：公開 API、內部 nlohmann 邊界、content／params／transport／SSE／Reply／Bot 等實作檔、presets、CLI 與測試。
**新增／刪除 `core/llms/` 底下的原始碼或測試檔，就在這一份加／減那一列。**

---

## core/llms/ — OpenAI 相容端點 client（非串流 + SSE 串流）

公開介面不含 nlohmann 或 curl 型別；JSON 以字串進出。`Bot::ask()` 除
`std::bad_alloc` 外永遠回 `Reply`，錯誤放在分類化的 `reply.err`。HTTP 由
完整回應的 `Transport` 與 callback 式 `StreamTransport` 都可抽換，ctest 全部使用假端點。

| 檔案 | 負責 |
|------|------|
| `include/aos/llms.hpp` | 公開 API 的**傘狀標頭**：本身只 `#include` 底下 `aos/llms/` 的七份子標頭，`#include <aos/llms.hpp>` 拿到的宣告與拆檔前完全相同；外部引用一律走這條路徑 |
| `include/aos/llms/transport.hpp` | `ErrorKind`／`ReplyError` 與 `HttpRequest`／`HttpResponse`／`Transport`／`StreamByteSink`／`StreamTransport` |
| `include/aos/llms/caps.hpp` | `Capability`／`Caps`、`Usage` 與 `Params` |
| `include/aos/llms/tools.hpp` | `RawToolCall`／`ToolCall`／`ToolCallDelta`／`ToolCallAccumulator`、`ToolBundle`／`ToolSetState`／`ToolSet` 與 `normalize_tools` |
| `include/aos/llms/llm.hpp` | `ModelInfo` 與 `LLM` |
| `include/aos/llms/bot.hpp` | `Ask`、`ReplyPart` 與串流 sink、`Reply`、`Bot` |
| `include/aos/llms/presets.hpp` | `PresetState`、`load_preset` 兩式與 `preset_ids` |
| `include/aos/llms/content.hpp` | URL／key 正規化與 `encode_image_url`／`build_content_json` 純函式 |
| `src/llms_internal.hpp` | 唯一共用的內部 nlohmann 邊界與各 pimpl／測試不到的 access bridge；公開標頭不 include 它 |
| `src/content.cpp` | base／completion／root URL 正規化、API key fallback、本機圖片 MIME＋base64 data URL、圖片／文字 content parts |
| `src/params.cpp` | `Params` → request JSON；只送已設定欄位，再直接展開 `extra_json`；model／messages／stream 由 Bot 最後固定、不讓 extra 覆蓋 |
| `src/toolcalls.cpp` | raw call → 呼叫端 entry／API history；非法 arguments 保留 raw；串流碎片按 index 增量累積 |
| `src/toolset.cpp` | C++ 的 `(schemas_json, dispatch)` bundle 驗證與合併；名稱須完全配對且不可撞名，不做 Python callable 反射 |
| `src/transport.cpp` | 預設 libcurl 完整／串流 transport；curl 型別與 header 只停在本檔，串流以 `CURLOPT_WRITEFUNCTION` 即時推 2xx body，非 2xx body 留給錯誤訊息 |
| `src/sse.hpp`／`src/sse.cpp` | 內部增量 SSE parser；跨任意 transport callback 切割組 line／event，處理多個 `data:` 行與 `[DONE]` |
| `src/caps.cpp` | GET `<root>/model/info`，轉成七項 `optional<bool>`；失敗吞掉，以 `(root URL, key)` 快取且空表也快取 |
| `src/llm.cpp` | `LLM` 值與能力檢查；只有明確 `false` 擋請求，tool choice 沒 tools 直接回明確錯誤 |
| `src/reply.cpp` | 非串流整包吸收、同一 `Reply` 的結果投影與唯一 `finish()`；解構與 move assignment 都確定收尾，空且未完成的輪退回 checkpoint |
| `src/stream_reply.cpp` | 延遲啟動 push transport、逐 SSE event 防禦性拆 chunk、答案／思考 sink 分流、usage-only 尾片、tool-call accumulator 餵入與串流期錯誤收斂 |
| `src/bot.cpp` | 組 system＋history＋tool results＋user message、最後覆寫 model／messages／stream；非串流立即送出，串流建立延遲 Reply 並固定 include_usage，兩路都由 `Reply::finish()` 寫回或退回 history |
| `src/presets.cpp`／`src/presets_data.hpp.in`／`presets.json` | 嚴格驗證並載入內嵌 preset；每筆只准 endpoint／model／parameters／可省略 description，能力不放 preset |
| `src/run.hpp`／`src/run.cpp` | `aos llms ask`／`models` CLI 與 `aos_llms_cli_main`；成功路徑會連端點，配置失敗由 CLI 例外邊界收住 |
| `CMakeLists.txt` | 建 `aos::llms`、以 `PRIVATE_DEPS CURL::libcurl` 連 curl、內嵌 presets、登記 `llms` 子命令與離線測試；傘狀標頭與 `aos/llms/` 七份子標頭都列在 `HEADERS` 才會一起安裝 |
| `README.md` | 非串流／串流 API、push 資料流、Reply 收尾、與 Python 的解構差異、能力／toolset／presets 與 CLI 使用說明 |
| `proxy/` | 從 reference 原樣搬入的 LiteLLM yaml、Linux／PowerShell 啟動腳本與 README；不建置、不安裝 |

### core/llms/tests/ — 測試

| 檔案 | 涵蓋 |
|------|------|
| `test_support.hpp` | 假端點、HTTP 回應與暫存檔共用工具 |
| `test_content_params.cpp` | URL／root／key、本機與遠端圖片、image-only content、Params 只送設定值 |
| `test_toolcalls.cpp` | 交錯 index 碎片累積、非法 JSON arguments、tool-call history 與 null content |
| `test_toolset_presets.cpp` | schemas／dispatch 完整配對與撞名、內建 preset、缺鍵／多鍵拒絕 |
| `test_caps.cpp` | 能力 true／false／不知道、override、只擋明確 false、root＋key 快取、空表命中與清快取 |
| `test_reply_errors.cpp` | ask 全錯誤契約（transport／HTTP／JSON／回應形狀／例外）、checkpoint rollback、送出前後的 user message、finish 落空退回、tool_choice 缺 tools、remember false |
| `test_bot_turn.cpp` | 成功一輪：extra 不得覆蓋 model／messages／stream、image-only、text＋calls 與 tool history、非法 args 保留 raw、pending calls、system／reset、usage 缺值 |
| `test_stream_split.cpp` | 同份 SSE 的整包／不規則／逐 byte 切割等價：答案／思考分流與交錯 index tool-call 碎片在任何切法下結果一致 |
| `test_stream_reply.cpp` | 串流 Reply 行為：usage-only／防禦欄位、零位元組斷線、壞事件／transport 例外／sink 例外的收斂與 history 進退、解構與提前 finish、tool-only null content；全用假 transport |
| `test_run.cpp` | S4 CLI 接受 `--stream`，以未知 preset 驗到執行期而不連網 |
