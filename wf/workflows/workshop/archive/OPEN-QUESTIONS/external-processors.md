# 待答問題：外部處理器的交付與 ABI 一致性
← [待答問題](README.md)｜[workshop](../README.md)｜[BACKGROUND](../BACKGROUND.md)

第 33–34 題：不引用 aos lib 的外部處理器完成後要交什麼、怎麼證明它讀對磁碟 ABI。

## 可以慢慢想的

### 33. 外部處理器完成後要交什麼？

**問題｜**外部處理器完成一件工作後，是只 ack、寫 receipt，還是直接 Deliver 給下一顆 CPU？  
**為什麼卡著｜**這決定外部處理器只是 caller 的同步延伸，還是可串成 pipeline，也會影響共同 completion commit。  
**在哪問過｜**〈核心行程與子行程〉；1 位直接問了。  
**候選答案｜**

- **只 ack**——完成狀態回給原 caller，下一步由 caller 決定。
- **寫 receipt／result**——原子留下可查的結果與 correlation，之後由 driver 收割。
- **Deliver 下一顆 CPU**——外部處理器完成後直接投遞下一段 pipeline。

### 34. 怎麼證明外部處理器讀對 ABI？

**問題｜**不引用 aos lib 的外部處理器，要靠 golden files＋conformance CLI，還是統一透過同一 CLI／parser 驗證？  
**為什麼卡著｜**沒有一致性檢查，「不引用 lib 也接得上」只是一項宣稱；磁碟 ABI 改版時尤其無法判斷相容性。  
**在哪問過｜**〈核心行程與子行程〉、〈四個懸而未決的設計選擇〉、〈aos 與 coding agent、skills、MCP 的協作〉；兩批共 2 位直接問 conformance，後一場 4 位要求單一 parser 語意。  
**候選答案｜**

- **golden files＋conformance CLI**——外部實作用固定案例證明 parse、publish、receipt 與錯誤一致。
- **全部呼叫 aos CLI**——外部處理器不連 lib，但投遞與驗證統一經 Deliver。
- **共用 lib／parser**——CLI、MCP 與整合程式共用實作，不允許另寫一套契約。

