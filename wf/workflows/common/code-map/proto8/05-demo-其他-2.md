← [入口](../proto8.md)｜涵蓋：`proto8/demo/` 的 kernel-llm 頂層（10-24；pi-tools、file-tools 已遷進 lib）｜上一份 [05-demo-其他](05-demo-其他.md)（talk、self-improve）

> 2026-10-24 收尾補：這幾個 demo 各作者做的時候沒改 code map。怎麼跑、錯誤代號見 [demo README](../../../../../proto8/demo/README.md) 各節。

### `proto8/demo/pi-tools/`、`proto8/demo/file-tools/`（10-24 下午遷移進 lib，已刪）

仿 pi 的四個（read、write、edit、bash）與資料夾、檔案的漸進工具八個（ls、stat、view、json_edit、mkdir、move、copy、trash），10-24 下午照 [tool-lib 遷移清單](../../../../../proto8/thinking/2026-10-24-tool-lib.md)搬進 `proto8/lib/base/`（逐檔見 [06-周邊工具](06-周邊工具.md) 的 lib 節）：file-tools 的 `common.py` 攤回各工具、錯誤從 stdout `{"error"}` 改成跟 pi-tools 一樣「stdout 同一行」、`ls` 兩份併成一份、`json_edit` 用庫的介面改叫 aos-json 寫。兩個資料夾刪了（刪前最後一版 acd6c02c，見 git 歷史）；掛它們的 agent-pip、agent-kai、self-improve 的改進者、sandbox 的 bash-boxed 改指 `lib/base`。設計原本在 [thinking 2026-10-24-pi-tools](../../../../../proto8/thinking/2026-10-24-pi-tools.md)。

### `proto8/demo/kernel-llm/`（問腦走 LLM kernel 排隊）

一個 daemon 管 kernel 與三隻走 kernel 的 agent，看服務順序（high 先、同級宣告短 `time_ms` 的先）。設計在 [thinking 2026-10-24-llm-kernel](../../../../../proto8/thinking/2026-10-24-llm-kernel.md)；程式見 [03-kernel-llm](03-kernel-llm.md)。

| 哪裡 | 負責什麼 |
|---|---|
| `_entry` | shell：`AOS_KERNEL=$AOS_STACK/mailbox` 並先建好（免得閘門 `MailboxMissing`）、`exec aos-daemon daemon.json` |
| `daemon.json` | max 25、每 200 毫秒；子項 kernel（`aos-kernel-llm kernel.json`，`interval_ms` 300）與 a、b、c（各跑一次 `agent-ivy`，工作區 `$AOS_WS/<名>`，`BRAIN` 選 `brains/plain.json`／`quick.json`／`urgent.json`） |
| `kernel.json` | `mailbox` 讀 `$AOS_KERNEL`、`slots` 1、`budget`（calls 100、tokens 100000、window day；10-24 下午加，demo 碰不到頂） |
| `agent-ivy/`（含 `brains/`） | 走 kernel 的 agent 與三張腦的單子，逐檔見 [04-demo-agents](04-demo-agents.md) |
