# astra-5 驗收分工

受測 HEAD：`392a1d645eceec98c41678ab2b685959e7ab0522`。依使用者委託只新增本證據目錄與指定報告；不改既有原碼、測試、文件，不 commit／push，不碰 scratchpad，不打 LLM。測試根只在各線自建 /tmp，依 PID 清理並核對 ps。

| 線 | 獨占可寫目錄 | 驗收 |
|---|---|---|
| subd | `subd/` | G3×10、回收邊界、各持久點 SIGKILL、自崩、allow-stop |
| budget_crash | `budget-crash/` | 並行、真 SIGKILL、unknown／取消／晚到、壞帳缺帳、供核帳快照 |
| budget_integration | `budget-integration/` | 時鐘／pause／重開、step、獨立核帳含負對照、五缺口來源與評估 |
| regression | `regression/` | 全套×3及耗時、A4-01～07／F47／§4.4、450回合、核心2757 |

各線不能再開子線；皆保留可重跑探針、機器可讀結果、摘要與清理證據。發現先逐案依 B／G／X／M 判定，由主線核對證據後統一編號。
