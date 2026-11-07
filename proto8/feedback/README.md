# feedback — 跨 session 留存 aos 指令與函數的使用意見，並提供評分者辨識規則。

人用的入口是 [aos-feedback](../cmd/aos-feedback/README.md)，agent 可用 [feedback 工具](../lib/aos/feedback/README.md)。每個指令 key 一份只追加的 `<key>.jsonl`，意見檔進 git。

`raters.json` 的 `rules` 依順序比對模型名子字串，第一條命中即採用；家族與階位可自由增列。測試一律設 `AOS_FEEDBACK` 指向暫存夾，不在這裡留下測試意見。
