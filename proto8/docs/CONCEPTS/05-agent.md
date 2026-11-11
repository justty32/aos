← [回入口 CONCEPTS.md](../CONCEPTS.md)｜主題：**agent**｜概念：本檔｜規範：agent 的一次一格與工具在 [NORMS 資料夾程式與執行](../NORMS/10-基礎設施-定義與工作區.md)（N-50、N-53）；慣例整套在 [CONVENTION](../CONVENTION.md)；agent 是用 fsm 組出來的（一個資料夾程式，C-50），fsm 的概念與規範在基礎設施——[CONCEPTS § fsm](03-基礎設施/01-inst至fsm.md#fsm)、[NORMS 組合子 § fsm](../NORMS/07-基礎設施-組合子/01-N-20～N-36.md#fsm)｜實作：[impls](../../impls/README.md)（C++ 是唯一實作）、agent-bob（叫 cathy 叫 stamp）、agent-ann（11-04 前在 [demo](../../templates/README.md)；現有 eca-claude、agent-fsm 兩個範本在 [templates](../../templates/README.md)、llm-kernel 在 kernel/）；問腦＝寄信給 llm kernel、收回信（11-04 晚，[P-23](../CONVENTION/02-題目stack停錯腦/05-P-23～P-26.md)）：基礎工具 [aos-llm](../../impls/aos-llm/README.md)、kernel 範本 [kernel/llm-kernel](../../kernel/docs/01-llm-kernel.md)；腦的工具呼叫（`tool_calls`）：慣例 [P-41](../CONVENTION/02-題目stack停錯腦/06-P-41.md)、範本 agent-eve（11-04 隨 proto8/tests 刪了）（11-02 晚 agent-dan 刪除，原本指它；eve 是它的複本）（相關待定見 [NORMS 待定](../NORMS/08-待定.md)）

# agent

使用者 10-15：「把 fsm 也跟 tasks 放一起」——agent 狀態機那幾條（C-18、C-25、C-39）跟著 fsm 移到[基礎設施](03-基礎設施/01-inst至fsm.md#fsm)。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../../wf/STRUCTURE.md) 按標題拆開；本檔留前言與表，各段逐字在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-腦-工具-可預測性與agent函數binding](05-agent/01-腦-工具-可預測性與agent函數binding.md) | 腦、工具、可預測性；agent＝函數＋binding |
| [01-續-C-22](05-agent/01-續-C-22.md) | 腦、工具、可預測性（續）：C-22（11-07 確定性與專精窄領域加註） |
| [01-續-C-42](05-agent/01-續-C-42.md) | 腦、工具、可預測性（續）：C-42（11-06 從 01 逐字搬來，加知識庫、thought（11-11 改名 `do_task`，[do-task-rename](../../thinking/2026-11/11/do-task-rename.md)；**11-11 再註**：這支開小幫手的工具拿掉了，`do_task` 這個名字改給 save／load 版〔在自己的 history 留紀錄點、結束時換成總結〕，複製自己去做另成工具 `fork`，[fork-and-do-task](../../thinking/2026-11/11/fork-and-do-task/README.md)）、agents 註） |
| [02-agent-的工具與agent-就是一台狀態機](05-agent/02-agent-的工具與agent-就是一台狀態機.md) | agent 的工具（10-16 使用者定，10-19 改）；agent 就是一台狀態機（10-16 使用者定） |
| [03-C-84](05-agent/03-C-84.md) | 系統自己改進函數（11-07）（C-84） |

<a id="腦工具可預測性"></a>
<a id="agent函數binding"></a>
<a id="agent-的工具10-16-使用者定10-19-改"></a>
<a id="agent-就是一台狀態機10-16-使用者定"></a>
