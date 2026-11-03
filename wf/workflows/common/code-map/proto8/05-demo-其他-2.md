← [入口](../proto8.md)｜涵蓋：`proto8/demo/` 的 pi-tools、file-tools（10-24 已遷進 lib；llm-kernel 11-03 封存到 proto8/archive/llm-kernel-demo/）｜上一份 [05-demo-其他](05-demo-其他.md)（talk）

> 2026-10-24 收尾補：這幾個 demo 各作者做的時候沒改 code map。怎麼跑、錯誤代號見 [demo README](../../../../../proto8/demo/README.md) 各節。

### `proto8/demo/pi-tools/`、`proto8/demo/file-tools/`（10-24 下午遷移進 lib，已刪）

仿 pi 的四個（read、write、edit、bash）與資料夾、檔案的漸進工具八個（ls、stat、view、json_edit、mkdir、move、copy、trash），10-24 下午照 [tool-lib 遷移清單](../../../../../proto8/thinking/2026-10-24-tool-lib.md)搬進 `proto8/lib/base/`（逐檔見 [06-周邊工具](06-周邊工具.md) 的 lib 節）：file-tools 的 `common.py` 攤回各工具、錯誤從 stdout `{"error"}` 改成跟 pi-tools 一樣「stdout 同一行」、`ls` 兩份併成一份、`json_edit` 用庫的介面改叫 aos-json 寫。兩個資料夾刪了（刪前最後一版 acd6c02c，見 git 歷史）；掛它們的 agent-pip、agent-kai、self-improve 的改進者、sandbox 的 bash-boxed 改指 `lib/base`。設計原本在 [thinking 2026-10-24-pi-tools](../../../../../proto8/thinking/2026-10-24-pi-tools.md)。
