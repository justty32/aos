# 2026-10-16 agent 的「擴張」與「當函數」：Lua 式繼承在 JSON inst 體系怎麼用、不造 args.json／ret.json

← [討論紀錄](README.md)｜前情：[inst-exec 第四版](2026-10-15-inst-exec-v4.md)（本稿改掉它「工具一律走 frame：args.json 進、ret.json 出」那段）、[意見 1～4](2026-10-15-opinions-1-4.md)（agent＝fsm＋inst、binding 用 json＋資料夾）、[topics/04 agent 當函數](2026-10-15-topics/04-agent當函數.md)、[同像性](2026-10-15-homoiconic.md)、[10-14 fsm 原話](2026-10-14-json-entry/06-fsm.md)（「像 C++ class 的繼承、函數可以被覆蓋」）｜概念：[C-46、C-50](../docs/CONCEPTS/05-agent.md)、[C-34、C-36、C-49](../docs/CONCEPTS/03-基礎設施.md)、[C-48、C-52、C-55、C-56](../docs/CONCEPTS/01-設計理念.md)｜規範：[N-12、N-43](../docs/NORMS/01-總則.md)、[N-27](../docs/NORMS/03-基礎設施-inst.md)、[N-28、N-44](../docs/NORMS/04-基礎設施-loop與daemon.md)、[N-36～N-40](../docs/NORMS/07-基礎設施-組合子.md)、[N-45](../docs/NORMS/06-基礎設施-命令列與指示詞.md)

> **決定在 [§ 四](2026-10-16-agent-inherit/02-四-使用者決定.md#四使用者決定10-16)。** 本稿這套（stdin 是正規入口、`.aos` 捷徑接食譜、門房 `aos exec WD TARGET`、工具地址寫在食譜的捷徑）10-19 作廢，現行是資料夾＝程式＋環境變數（見 [10-19 ideas](2026-10-19-ideas.md)、[proto8 README](../README.md)）；仍有效的是 agent 當函數是概念上的（C-46）、stack 與工作區分開、指標、stack 放哪由呼叫方自由（C-65～C-67，工作區與 stack 由環境變數 `AOS_WS`／`AOS_STACK` 給）。本稿各節照原樣用 frame 這個字（現稱 stack）。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../wf/STRUCTURE.md) 按 `##` 標題拆開（單段仍超標的再按 `###` 切）；本檔留前言與表，各段逐字在下列分檔（2026-10-31 tidy）。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-三分鐘看懂](2026-10-16-agent-inherit/01-三分鐘看懂.md) | 三分鐘看懂（五）：/ws 保持乾淨——一般工具站在工作區、agent 工具站在自己的 frame（10-16 夜重想）、一、使用者原話（10-16，整理版）、二之二、轉手鏈（shebang 式）vs 加 key（Lua 式）（10-16 晚）、二之三、`aos-exec WD TARGET`（10-16 晚）、三、要使用者拍板的點 |
| [02-四-使用者決定](2026-10-16-agent-inherit/02-四-使用者決定.md) | 四、使用者決定（10-16） |
| [03-五-自然組合的機制](2026-10-16-agent-inherit/03-五-自然組合的機制.md) | 五、自然組合的機制（10-16 夜）、六、捷徑：agent 當工具與推廣到一般函數（10-16 夜）、七、不用 PATH：地址放哪（10-16 夜）、八、工作區與 frame 分開（10-16 夜重想，AI 提案；「指標＝捷徑」「工具可直接 cwd: ws、風險設計者自管」已定） |

<a id="三分鐘看懂五ws-保持乾淨一般工具站在工作區agent-工具站在自己的-frame10-16-夜重想"></a>
<a id="一使用者原話10-16整理版"></a>
<a id="二之二轉手鏈shebang-式vs-加-keylua-式10-16-晚"></a>
<a id="二之三aos-exec-wd-target10-16-晚"></a>
<a id="三要使用者拍板的點"></a>
<a id="四使用者決定10-16"></a>
<a id="五自然組合的機制10-16-夜"></a>
<a id="六捷徑agent-當工具與推廣到一般函數10-16-夜"></a>
<a id="七不用-path地址放哪10-16-夜"></a>
<a id="八工作區與-frame-分開10-16-夜重想ai-提案指標捷徑工具可直接-cwd-ws風險設計者自管已定"></a>
<a id="0-使用者原話10-16-夜整理版"></a>
<a id="1-兩個東西兩條捷徑"></a>
<a id="3-兩種預設寫在哪才不是暗規則"></a>
<a id="3b-frame-指到哪是呼叫方的自由概念層的一句"></a>
