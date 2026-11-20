# proto8 討論紀錄：2026-11-21

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 份 | 一句話 |
|---|---|
| [session_key 實測（session-key-實測-1121）](session-key-實測-1121.md) | 暫存樹實測 sol 加 "session_key": "litellm_session_id" 前後：不加 4 輪快取都是 0，加了第 2 輪起每輪 12,416 token 命中（約 99%），4 輪沒中快取的從 50,314 降到 13,066；工具順序、system、對話前綴都穩定，原因就是沒寫這個鍵；範本沒改，要不要改等使用者 |
