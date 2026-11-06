# 2026-10-28 aos-tools：一份工具註冊檔，aos agent 直接吃、外部 agent 經 aos-mcp 吃

← [thinking](../../../README.md)｜月份表 [2026-10](../../README.md)｜前情：[10-28 aos-hub 常駐 kernel](../hub-kernel/README.md)（未決裡的「aos-tools 長什麼樣」）、[10-26 playground](../../26/playground.md)（aos-mcp 怎麼來的）、[10-24 工具＝函式庫](../../24/tool-lib/README.md)｜使用者筆記：[user-advice/20261027](../../../../user-advice/20261027.md)（使用者的資料夾，不改）｜實作：[proto8/bin/aos-tools](../../../../cmd/README.md)、[extras/ai_tools § aos-mcp](../../../../cmd/aos-mcp/README.md)

規矩見 [thinking/README](../../../README.md)：只留使用者原文、決定、結論。

## 分檔目錄

| 分檔 | 涵蓋的段 |
|---|---|
| [01-使用者原文](01-使用者原文.md) | 使用者原文、決定（10-28，使用者提的構想與回答，照實記）、未決 |
| [02-跟原則的對照](02-跟原則的對照.md) | 跟原則對不上的地方（10-28，結論裡已化解） |
| [03-結論](03-結論.md) | 結論（10-28 實作，照原則代定、可翻案） |
| [04-11-03-no-cache](04-11-03-no-cache.md) | 11-03 exe 快取的開關（`add --no-cache`） |

<a id="使用者原文"></a>
<a id="10-27-晚的筆記整理版全文見-user-advice20261027"></a>
<a id="10-28逐字"></a>
<a id="決定10-28使用者提的構想與回答照實記"></a>
<a id="未決"></a>
<a id="跟原則的對照10-28只列不裁定"></a>
<a id="對得上的"></a>
<a id="對不上要使用者看的"></a>
<a id="現行-aos-mcp-跟新方向的差異之後要改的"></a>
<a id="結論10-28-實作照原則代定可翻案"></a>
