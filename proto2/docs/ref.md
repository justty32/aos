# ref 工具包

這包把太大的 JSON 工具結果收進本體的 `refs/`，讓模型先看短指標，需要時再展開。

- `ref_expand(ref, path?, max_chars?)`：展開指標。`path` 可寫 `#/choices/0`。一次最多 20000 字。
- `ref_collapse(message_index)`：手動收起一則 JSON 對話。序號從 0 開始。
- `ref_list()`：列最近 20 個指標。

工具結果轉成 JSON 後超過 6000 字，`on_act` 會立刻存檔，並把後面工具包與模型看到的結果換成 `ref://<id>`、短預覽與原字數。

只在需要原文時展開。截短的展開結果只是文字片段，不是完整 JSON。

`ref` 和長期記憶的差別見 [bigmem.md](bigmem.md)。掛勾順序見 [packs-api.md](packs-api.md)。
