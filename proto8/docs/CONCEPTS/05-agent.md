← [回入口 CONCEPTS.md](../CONCEPTS.md)｜主題：**agent**｜概念：本檔｜規範：agent 的一次一格與工具在 [NORMS 資料夾程式與執行](../NORMS/10-基礎設施-定義與工作區.md)（N-50、N-53）；慣例整套在 [CONVENTION](../CONVENTION.md)；agent 是用 fsm 組出來的（一個資料夾程式，C-50），fsm 的概念與規範在基礎設施——[CONCEPTS § fsm](03-基礎設施/01-inst至fsm.md#fsm)、[NORMS 組合子 § fsm](../NORMS/07-基礎設施-組合子/01-N-20～N-36.md#fsm)｜實作：[impls](../../impls/README.md)（C++ 是唯一實作）；agent 範本 eca-claude、agent-fsm 在 [templates](../../templates/README.md)，llm-kernel 在 kernel/；問腦＝寄信給 llm kernel、收回信（[P-23](../CONVENTION/02-題目stack停錯腦/05-P-23～P-26.md)）：基礎工具 [aos-llm](../../impls/aos-llm/README.md)、kernel 範本 [kernel/llm-kernel](../../kernel/docs/01-llm-kernel.md)；腦的工具呼叫（`tool_calls`）：慣例 [P-41](../CONVENTION/02-題目stack停錯腦/06-P-41.md)（相關待定見 [NORMS 待定](../NORMS/08-待定.md)）

# agent

使用者 10-15：「把 fsm 也跟 tasks 放一起」——agent 狀態機那幾條（C-18、C-25、C-39）跟著 fsm 移到[基礎設施](03-基礎設施/01-inst至fsm.md#fsm)。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../../wf/STRUCTURE.md) 按標題拆開；本檔留前言與表，各段逐字在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-腦-工具-可預測性與agent函數binding](05-agent/01-腦-工具-可預測性與agent函數binding.md) | 腦、工具、可預測性；agent＝函數＋binding |
| [01-續-C-22](05-agent/01-續-C-22.md) | 腦、工具、可預測性（續）：C-22（確定性與專精窄領域） |
| [01-續-C-42](05-agent/01-續-C-42.md) | 腦、工具、可預測性（續）：C-42（知識庫、`do_task`（save／load）與 `fork`、生子 agent、帳往上收） |
| [02-agent-的工具與agent-就是一台狀態機](05-agent/02-agent-的工具與agent-就是一台狀態機.md) | agent 的工具（C-61：工具收成函式庫）；agent 就是一台狀態機 |
| [03-C-84](05-agent/03-C-84.md) | 系統自己改進函數（C-84） |
| [04-C-88-記憶與index](05-agent/04-C-88-記憶與index.md) | 記憶與 index（C-88） |
| [05-C-89-不同質與族譜](05-agent/05-C-89-不同質與族譜.md) | 不同質 agent 與族譜（C-89） |
| [06-C-90～C-92-self一家與goal](05-agent/06-C-90～C-92-self一家與goal.md) | self 一家與 hook（C-90）、goal 與 todo（C-91）、小模型裝不下工具說明（C-92） |

<a id="腦工具可預測性"></a>
<a id="agent函數binding"></a>
<a id="agent-的工具10-16-使用者定10-19-改"></a>
<a id="agent-就是一台狀態機10-16-使用者定"></a>
