# 2026-10-28 aos-hub 實作：say／listen 對 claude 說話（agent 對話協議）、每種 CLI 一張適配表、副產物留著

← [thinking](../../../README.md)｜月份表 [2026-10](../../README.md)｜前情：[10-28 hub-kernel](../hub-kernel/README.md)（今天定的 14 條決定）、[10-24 say／listen](../../24/say-listen.md)、[10-24 claude／codex 當工具](../../24/cli-tools.md)｜程式：[extras/cli_hub](../../../../extras/eca/README.md)，測試 `proto8/tests/test_hub.py`

> 10-30 起 aos-hub 改做 aos-eca-hub，見 [eca](../../30/eca/README.md)。

規矩見 [thinking/README](../../../README.md)：只留使用者原文、決定、結論。下面「結論」除了標明使用者定的，都是隊長照 CONCEPTS／NORMS 代定、**可翻案**。

## 分檔目錄

| 分檔 | 涵蓋的段 |
|---|---|
| [01-使用者原文](01-使用者原文.md) | 使用者原文（10-28，逐字）、結論一：agent 對話協議（從 aos-say／listen 抽出來的）、結論二：aos-hub 照 10-28 決定改完 |
| [02-結論三-每種現成程式一張適配表](02-結論三-每種現成程式一張適配表.md) | 結論三：每種現成程式一張適配表、結論四：副產物——確定都留著（使用者「反正就留著」）、代定（可翻案）、已知限制 |

<a id="使用者原文10-28逐字"></a>
<a id="結論一agent-對話協議從-aos-saylisten-抽出來的"></a>
<a id="結論二aos-hub-照-10-28-決定改完"></a>
<a id="結論三每種現成程式一張適配表"></a>
<a id="結論四副產物確定都留著使用者反正就留著"></a>
<a id="實跑wsl10-28"></a>
<a id="代定可翻案"></a>
<a id="跟原則的對照信箱放-stack10-28"></a>
<a id="已知限制"></a>
