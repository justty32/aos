# aos 工具協作 — 未決問題與明顯的坑

← [本場索引](README.md)｜[workshop](../../README.md)

本場問出來但沒有答案的九題，以及四位點名不能踩的坑。

---

## 大家問出來的問題

1. **第一個產品體驗是哪一個：人在 coding agent 對話中呼叫 aos，還是 aos 無人值守地批次召喚
   coding agent？**工程師、架構師**兩位獨立地都問了**。兩者共用 CLI，但 session、批准與
   unknown 責任不同。

2. **第一個入口先做 pi skill，還是先做給其他 agent 的 MCP？**研究人員直接問。pi 不支援 MCP，
   所以這實際是在問第一個要驗證的宿主是 pi，還是 MCP ecosystem。

3. **可攜的 `--no-session` 重播，與快速續談的 session，哪個優先？**研究人員直接問；四位都把
   session 當 cache，但也都想過續談模式。

4. **pi 的 JSONL final event、RPC 與 session 格式是否有跨版本穩定承諾？實際支援的 session 定址
   旗標是什麼？**；**四位都標記格式不確定**，本場事實表沒有列參與者反覆使用的 `--session-dir`。

5. **coding agent 預設可呼叫 Exec，還是只准 Deliver、等人批准後再推？**開發者直接問；架構師、
   研究人員也要求 Deliver／Exec 分權。

6. **Deliver 是否接受單筆 object？`--key`／`--durable`／`--to` 哪些進第一版？**三位接受單筆，
   key 只有兩位，durable 只有一位，`--to` 只有研究人員；目前沒有 4／4。

7. **沒有耐久 ledger 時，key 的作用只是 correlation，還是仍要承諾 Already／Conflict？**工程師、
   開發者本輪放回冪等狀態；架構師、研究人員省略，且四位在回頭審視曾一起指出 ledger 缺口。

8. **成功 JSON、錯誤 JSON、退出碼要採哪一份；給人看的錯誤如何與模型 JSON 分開？**四位都給了
   machine JSON，但欄位與 code 不同，且沒有人完成 human-facing 半題。

9. **stdout→stdin 的上半段由誰產生穩定 context？**raw `aos exec` stdout 已被四位排除；主輪的
   prompt／emit 沒有在追問輪留下共同介面。

## 明顯的坑

- **為 pi 先做 MCP server。**pi 明確不做 MCP；它的自然路徑是 CLI＋skill，或 pi extension。

- **把 PATH 上的 `agy.exe` 當 pi。**使用者已澄清它是 Gemini；整合測試若用錯 executable，所有
  event／session 結論都會對錯產品。

- **把 raw `aos exec` stdout 當 agent protocol**。**四位獨立地都指出**子指令輸出任意且可能混流；
  沒有 turn／source／exit envelope，不能安全 pipe 給模型。

- **重新長回「自然語言→adapter 猜 JSON」**。**四位在追問輪 4／4 收回這層**；agent 應直接
  tool-call Deliver，錯誤作為 tool result 回去修。

- **讓 pi session 成為 world 真源**。**四位都只接受 session 作可丟快取**；遺失後必須能從 world
  request／history 重建。`--fork` 也不能偷偷定義 aos 子世界身分。

- **把未核對的 `--session-dir` 寫進 skill。**本場提供的 pi 介面沒有這個旗標；先驗實際 CLI，
  否則 skill 第一條 session 指令就可能不可用。

- **CLI、skill、MCP 各自實作一次 Deliver**。**四位都要求單一 parser／單一原子投遞語意**；入口
  可不同，receipt、錯誤與檔名契約不能分叉。

- **MCP 預設開 Exec，卻因為 server 有 `--root` 就以為安全。**Exec 可跑任意 POSIX 指令；path
  限界不是完整 sandbox，仍需 container／同權或降權執行。

- **正常驗證失敗也丟 `.bad`。**tool caller 應立即收到可修正的 JSON 錯誤；`.bad` 只處理繞過
  Deliver 的壞檔，否則模型得去掃磁碟才知道參數錯了。

- **看到 `--key` 就宣稱跨回合 exactly-once。**沒有 ledger，aggregate 刪檔後無從辨認舊 key；
  本輪兩位重新提出 key，沒有補掉這個前情缺口。

- **agent 直接 Deliver 後，就以為 workshop 的 raw response capture 也解決了。**Deliver 解的是
  instruction 入 queue；付費 agent 的 Markdown／JSONL 是否完整落盤，仍有另一個 unknown 視窗。
