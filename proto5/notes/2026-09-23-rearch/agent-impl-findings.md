# agent 線實作（T9）：實作發現

← [rearch README](README.md)｜規範：[agent.md](../../spec/agent.md)、[aos-agent.md](../../spec/aos-agent.md)、[aos-llm-call.md](../../spec/aos-llm-call.md)

2026-09-24。照三份定稿規範重寫 agent 線時碰到的歧義與實作層級的選擇；本次未修改 `spec/*.md`。方向性的列在最後「要使用者拍的」。

1. **頂層是指示詞物件的代號。** agent.md §2 要 info.json 頂層是字面物件，沒指定頂層整份是 `$ref` 時用哪個代號。
   選 `FieldTypeMismatch`（跟 kernel info 的同類情況一致）；頂層不是物件仍是 `NotAnObject`。llm.json 同樣處理。
2. **記憶頂層不是陣列用 `NotAnArray`。** agent.md §3.2 說「不合＝MessageInvalid」，§5 另列 `NotAnArray`。選：頂層型別錯 `NotAnArray`、陣列裡的壞訊息 `MessageInvalid`。
3. **message 缺 `content` 鍵不當 null。** §3.2 要 content 是字串或 null；§5 正規化只處理「null」。模型若整個省略 content（只給 tool_calls）會被判 `EngineFailed`。
   照字面實作；若真跑遇到省略 content 的端點再議（可能要把「缺」併進正規化第 ② 步）。
4. **六格與 llm.json 的 `$opt` 在實際求值的位置才報 `UnknownOption`。** 被指示詞優先序忽略的鍵不求值、不誤報。
5. **共用讀驗層另立 `aos_agent_home.py`。** 為了讓第 1 段不動舊 `aos_agent_info.py`（舊 llm／tool cpu 還在 import 它），message 驗證、工具檔、人格／記憶讀與六格 loader 放新模組；
   新版 `aos_agent_info.py`（完整 info＋state）建在它上面。
