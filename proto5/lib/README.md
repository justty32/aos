# proto5/lib — 146 支 Python 模組

← [proto5 README](../README.md)｜規範：[cpu](../spec/cpu/README.md)、[daemon](../spec/daemon/README.md)、[kernel](../spec/kernel/README.md)、[aos-agent](../spec/aos-agent/README.md)

Python 3.12 以上、只用標準庫（3.12.13 與 3.14.7 都實跑全綠，見 [notes/2026-09-24-py312-run.md](../notes/2026-09-24-py312-run.md)）。
由下往上：`aos_directives` → `aos_inst` → `aos_exec`（跑一次）；`aos_home` 共用檔案範式、`aos_client` 交件；
`aos_exec_cpu` 是長命的 cpu、`aos_daemon` 按池管孩子（09-24 one-boot 起也替 kernel 定時開 tick）、`aos_kernel` 用一格接一格的 tick 排程；agent 線（`aos_agent*`）
把模型與工具都交給 exec cpu 跑。

09-24 起 daemon／kernel 是 proto5-2 的**池式**版本（納入 commit 08dac8a）：daemon 手上是「每池要哪幾號」的宣告、
kernel 手上是「池 P 要 N 顆」，都不再逐顆 spawn／kill。三支指令的家一律 `--target`：`aos_home.resolve_target()`
照「`--target` → 環境變數（`AOS_DAEMON_HOME`／`AOS_KERNEL_HOME`）→ 目前資料夾」找。

模組按家族分七份說明（每份一張「一檔一行」表，新增模組就插在那一份），測試另一份：

| 家族 | 一句話 | 支數 | 說明 |
|---|---|---|---|
| 指示詞與 inst<a id="aos_directives--指示詞機制的純函式庫"></a><a id="aos_inst--instjson-的讀驗解"></a> | 指示詞（`$env`／`$fmt`／`$ref`／`$opt`）解析、`aos-directives` 人格分節編輯與 resolve／check、inst.json 讀驗、`aos-json` 人用改檔 | 6 | [docs/directives.md](docs/directives.md) |
| 執行與共用底層<a id="aos_exec--執行者三支aos_execaos_exec_runaos_exec_spawn"></a><a id="aos_home--共用家與信封"></a><a id="aos_client--交件者"></a><a id="aos_exec_cpu--exec-cpu-的主人"></a><a id="aos_llm_call--問模型一次"></a> | 跑一次（`aos_exec`）、共用家與信封、交件者、長命 exec cpu、`aos up／down`、`aos-jail`、量每一跳、問模型一次 | 11 | [docs/exec.md](docs/exec.md) |
| daemon<a id="aos_daemon--池的主人五支aos_daemonpoolslooprpccli"></a> | 池的主人：按池宣告的孩子、一圈的狀態機、收的單、替 kernel 開 tick、命令列 | 6 | [docs/daemon.md](docs/daemon.md) |
| kernel<a id="aos_kernel--池表sqlite-帳本與-tick十三支aos_kernelinfoledgerstoreenginepoolsbootcpurowshealthlscheckcli"></a> | 池表、sqlite 帳本與一格接一格的 tick：增減 cpu、boot／status、cpu 與 ls、健康、啟動前檢查、命令列 | 13 | [docs/kernel.md](docs/kernel.md) |
| agent<a id="aos_agent_home--agent-家共用內容讀驗"></a><a id="aos_agent_info--設定與進度讀驗"></a><a id="aos_agent--走格與-kernel-排程"></a> | agent 的 tick 三格、家與設定讀驗、批次與恢復、日常 CLI（init／say／listen／talk／status…）、工具（裝、造、wrap）、權限牆、記憶壓縮 | 44 | [docs/agent.md](docs/agent.md) |
| team | 團隊：共用格式、申請與任務單、郵差兼書記、驗收員、心跳、門房、固化建議、score、財務、HR、commons、lock／spawn／toolsmith | 54 | [docs/team.md](docs/team.md) |
| 公司與市場 | 公司（`company.json`、生一家、機械總機、人頭與 cpu、開關機）與市場層（排名、撥額度、倒閉、合併） | 12 | [docs/company.md](docs/company.md) |
| 測試<a id="測試"></a> | 101 個測試檔、2874 條；每檔驗什麼、共用測試工具 | — | [docs/tests.md](docs/tests.md) |

命令列入口在 [`../cli/`](../cli/)，每支都是薄殼：`aos-exec`→`aos_exec.main`、`aos-cpu`→`aos_exec_cpu.main`、
`aos`→`aos_up.main`、`aos-daemon`→`aos_daemon.main`、`aos-kernel`→`aos_kernel.main`、`aos-agent`→`aos_agent.main`、
`aos-jail`→`aos_jail.main`、`aos-llm`→`aos_llm_call.main`、`aos-directives`→`aos_directives_edit.main`、
`aos-json`→`aos_json_cli.main`、`aos-team`→`aos_team_cli.main`。

超過 300 行的模組按職責拆成 `aos_<原名>_<職責>.py`，母模組留原路徑當入口（對外 import 一個都不變），各份說明的表裡寫了「這支留什麼」。超過約 400 行但刻意不拆：`aos_agent_access.py`、`aos_agent_talk.py`（agent 線別隊正在改，拆了難合併）；`aos_kernel_ledger.py`（整支是一個 `KernelLedger` 類別本體）；`aos_kernel_check.py`（測試換掉的 `daemon_environment`／`probe_endpoint` 由 `Checks` 與 `kernel_checks` 直接叫，這兩塊就是檔的大半）。

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=proto5/lib python3 -m unittest discover -s proto5/lib/test  # 2874 條；repo 根目錄
```
