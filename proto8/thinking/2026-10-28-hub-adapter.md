# 2026-10-28 aos-hub 實作：say／listen 對 claude 說話（agent 對話協議）、每種 CLI 一張適配表、副產物留著

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)｜前情：[10-28 hub-kernel](2026-10-28-hub-kernel.md)（今天定的 14 條決定）、[10-24 say／listen](2026-10-24-say-listen.md)、[10-24 claude／codex 當工具](2026-10-24-cli-tools.md)｜程式：[extras/cli_hub](../extras/eca_hub/README.md)，測試 `proto8/tests/test_hub.py`

> 10-30 起 aos-hub 改做 aos-eca-hub，見 [eca](2026-10-30-eca.md)。

規矩見 [thinking/README](README.md)：只留使用者原文、決定、結論。下面「結論」除了標明使用者定的，都是隊長照 CONCEPTS／NORMS 代定、**可翻案**。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../wf/STRUCTURE.md) 按 `##` 標題拆開（單段仍超標的再按 `###` 切）；本檔留前言與表，各段逐字在下列分檔（2026-10-31 tidy）。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-使用者原文](2026-10-28-hub-adapter/01-使用者原文.md) | 使用者原文（10-28，逐字）、結論一：agent 對話協議（從 aos-say／listen 抽出來的）、結論二：aos-hub 照 10-28 決定改完 |
| [02-結論三-每種現成程式一張適配表](2026-10-28-hub-adapter/02-結論三-每種現成程式一張適配表.md) | 結論三：每種現成程式一張適配表、結論四：副產物——確定都留著（使用者「反正就留著」）、實跑（WSL，10-28）、代定（可翻案）、跟原則的對照（信箱放 stack，10-28）、已知限制 |

<a id="使用者原文10-28逐字"></a>
<a id="結論一agent-對話協議從-aos-saylisten-抽出來的"></a>
<a id="結論二aos-hub-照-10-28-決定改完"></a>
<a id="結論三每種現成程式一張適配表"></a>
<a id="結論四副產物確定都留著使用者反正就留著"></a>
<a id="實跑wsl10-28"></a>
<a id="代定可翻案"></a>
<a id="跟原則的對照信箱放-stack10-28"></a>
<a id="已知限制"></a>
