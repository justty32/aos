# 任務書：base 工具包唯讀審查（2026-09-24）

你是唯讀審查員（codex gpt-6-astra，`-s read-only`）。用繁體中文寫報告。**不要改任何檔**，只讀、只寫報告到 stdout。

## 背景

proto5 的 agent（`aos-agent`）靠「工具」做事：工具＝一支程式，cwd 是 agent 家，stdin 收模型給的 arguments JSON、stdout 印的東西原樣給模型看（規範 `proto5/spec/agent/info.md` §3.3、`proto5/spec/agent/essentials.md`；工具失敗時 aos-agent 怎麼包給模型看在 `proto5/spec/aos-agent/collect.md` §6.2）。
這一輪做了一組基礎工具包，仿 pi coding agent（Mario Zechner）的 read、write、edit、bash、grep、find、ls，目標是「一個 agent 一裝就能當 coding agent 用」：

- 工具本體：`proto5/tools/base/`（`base.json` 是給模型的 schema 與描述，`_common.py` 共用，七支可執行腳本，`config.json` 的 `root`＝工作根目錄）。
- 說明：`proto5/tools/README.md`。
- 裝法：`aos-agent tools add NAME|DIR [--target] [--root] [--force]`，規範 `proto5/spec/aos-agent/tools.md`，實作 `proto5/lib/aos_agent_tools.py`＋`proto5/lib/aos_agent_cli.py`。
- 測試：`proto5/lib/test/test_tools_base*.py`（工具單元）、`proto5/lib/test/test_agent_tools.py`（tools add＋真 daemon／kernel／agent 往返、假模型）。
- 真模型實跑過一次（deepseek-chat）：模型照順序叫了 write→bash→edit→bash，結果正確。

## 要審的（每條給：嚴重度〔必修／建議／可忽略〕、檔:行、現象、重現或推理、建議修法）

1. **schema 對模型友不友善**：`base.json` 的描述與參數名、必填、預設值、上限寫得夠不夠讓模型一次叫對？錯誤訊息（`{"ok": false, "error": …, "message": …}`）夠不夠讓模型自己改正下一次呼叫？有沒有會誤導模型的措辭（例如 "project directory" 與實際工作根目錄）？跟 pi 的工具比，缺了什麼模型常用的能力？
2. **安全邊界**：
   - read／write／edit／grep／find／ls 能不能逃出工作根目錄？看 `_common.resolve`（realpath＋前綴比對）、符號連結、`..`、絕對路徑、`~`、grep／find 走訪時跟著符號連結出去、write 經由「父資料夾是指向外面的符號連結」寫出去、TOCTOU。
   - bash：逾時真的會砍到整個行程群組嗎？孫行程 `setsid` 逃走？輸出巨大（例如 `yes`）會不會把記憶體或暫存檔撐爆？預設與上限合不合理？kernel 那層 `_timeout_ms`（630000）跟 bash 自己的上限配不配？
   - grep 的 30 秒限制：沒輸出時卡住的 rg／grep 誰來砍？
   - `tools add`：`--root` 指到 agent 家或家的上層、`--force` 重裝時的原子性、中途崩潰留下什麼、同名檢查漏了什麼、`info.json` 被整份重寫會不會丟東西。
3. **跟規範對不對得上**：`spec/aos-agent/tools.md` 寫的步驟順序、錯誤代號、輸出，跟 `aos_agent_tools.py` 實作逐條比；`tools/README.md` 的表格（參數、上限、錯誤代號）跟 `base.json` 與腳本逐條比；工具格式跟 `spec/agent/info.md` §3.3 合不合。
4. **測試漏什麼**：列出沒測到、但應該測的情況（尤其第 2 條的邊界）。

## 產出

報告開頭一段總結＋「必修 N 條、建議 M 條」，再逐條列。最後一段「我沒看的」。不要貼大段原始碼。
