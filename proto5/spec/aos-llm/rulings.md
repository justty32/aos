← [aos-llm](README.md)｜[spec 總導航](../README.md)

# 調度者裁決（第 2～3 輪，實作層級）

1. llm.json 的 `_metainfo` 必填，`_type` 叫 `llm_config`、`_version` 只認整數 1。
2. 設定錯的代號用新的 `ConfigInvalid`（不是沿用舊名；舊 llm-cpu 叫 `EngineInvalid`）；讀檔、JSON、指示詞錯用各自原本的代號。
3. **執行時讀** agent 家：人格、記憶、工具、`info.llm` 在這支程式跑起來那一刻讀，不是 aos-agent 送件那一刻。
4. 模型回的 message 在印之前就照 [agent.md §3.2](../agent/info.md) 驗；不合＝`EngineFailed`，不印。
5. 印之前的正規化只做兩件、順序固定：先拿掉空的 `tool_calls`，再把「`content` 是 null 又沒 `tool_calls`」補成 `""`。
6. `api_key` 空字串＝不帶 `Authorization`，跟 null／沒寫一樣。
7. （第 3 輪）讀 agent 的 `info.json` **只解驗用得到的六格**（§3），其他格原樣不碰——agent 那邊只在自己 cpu 成立的 `$env` 不會讓這裡失敗。
