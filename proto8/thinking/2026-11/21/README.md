# proto8 討論紀錄：2026-11-21

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 份 | 一句話 |
|---|---|
| [session_key 實測（session-key-實測-1121）](session-key-實測-1121.md) | 暫存樹實測 sol 加 "session_key": "litellm_session_id" 前後：不加 4 輪快取都是 0，加了第 2 輪起每輪 12,416 token 命中（約 99%）；續量 luna、terra、astra（astra 在暫存樹新加一包）結果一樣；命中停在 12,416 是 128 一格、短句長不過下一格；範本沒改，建議四包都加、新增 astra，等使用者定 |
| [hook 第 5 刀後半（aos-hook-k5b-1121）](aos-hook-k5b-1121.md) | 範本 loop.json 接上 before_run／after_run、編譯寫四鍵、旗標檔由改清單的指令與 after_start 對、procs-kernel 接 loop 的四個點（清單 loop_hooks.json，kernel 程式沒改）；hook_fire 沒動；全套 79 夾跟基準相同另加 12 支；未決：起來時對旗標要等 hook_fire 換掉 |
