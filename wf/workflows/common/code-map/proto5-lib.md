← [code map 總圖](../code-map.md)｜[各分冊導覽](README.md)

## proto5/lib 模組

一檔一句（跟 [proto5/lib/README.md](../../../../proto5/lib/README.md) 的模組表同步；新增模組兩邊各插一行）：

<!-- wf-nav -->
| 分檔 | 涵蓋 |
|------|------|
| [01-exec-daemon-kernel.md](proto5-lib/01-exec-daemon-kernel.md) | 指示詞、inst、exec、家與交件、cpu、daemon、kernel、`aos up`：`aos_directives` … `test/test_one_boot.py`（31 列） |
| [02-llm-agent.md](proto5-lib/02-llm-agent.md) | llm、agent、jail、json：`aos_llm_call` … `aos_json_cli`（31 列） |
| [03-team.md](proto5-lib/03-team.md) | team：`aos_team_format` … `aos_team_toolsmith`（18 列） |

## proto5 父子教學範例

[`proto5/examples/parent-child-demo/`](../../../../proto5/examples/parent-child-demo/README.md)：`install.py` 向既有 parent 安裝固定管理工具；`bridge.py` 建立唯一 child、配置掛載與基本工具並雙向投訊；`test_boundaries.py` 驗參數、路徑、既有 child 與重裝保護。不改 agent 核心協定。

## Linux 隔離實驗

[`proto5/notes/2026-09-28-linux-probes/`](../../../../proto5/notes/2026-09-28-linux-probes/README.md)：`run.py` 建自有 scratch 並編譯執行 `landlock-canary.c`，驗證無特權 Landlock 檔案讀寫限制與 fork 繼承；不是產品啟動器。

proto6 規劃交接保留相同探針於 [`proto6/notes/probes/`](../../../../proto6/notes/probes/README.md)；這是調查程式快照，不是新增產品 lib。完整來源對照見 [proto6 notes 封存索引](../../../../proto6/notes/archive/README.md)。
