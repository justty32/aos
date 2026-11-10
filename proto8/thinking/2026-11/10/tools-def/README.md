# tools-def：給腦造新工具的 tools_def＋寫工具的 Python 輔助 lib（11-10 深夜）

← [2026-11-10](../README.md)｜設計與驗收 [01](01-設計與驗收.md)｜對稱的 [agents-split](../agents-split/README.md)（agent_def）｜分包 [tool-packs](../tool-packs/README.md)

## 使用者原話（逐字）

1. （分包時）「1.不對，agent_def另外放。之後可能會有tools_def。」
2. 頂層問「tools def要做嗎？」並提粗版（照 agent_def：`new` 複製一份最小且合格能跑的工具骨架到指定位置、`check` 檢查一個工具資料夾合不合格；掛上去仍用 self_tools add），問四題：1 做不做；2 名字 tools_def 還是 tool_def；3 跟 agent_def 一起放「定義」包、預設開；4 骨架幾種（建議先只給 Python）。使用者：「1.做。2.tools_def 3.對。 4.給python一種，順便弄個好用的lib，方便AI弄json schema, metainfo啥的。」
3. 「啊，純json定義版感覺也方便，你覺得呢」（頂層答：適合包現成指令、傳參數能做到哪沒查、小模型寫不出 `$` 鍵）→「好像也不太需要。或者說，可能這個會是之後建立aos函數的時候的事情了，比如我可能會跟AI說：請把這個資料夾弄成aos函數，寫個_entry.json，旁邊放個小python腳本。然後再說，請弄個_metainfo.json，再弄個_tooldef.json。這些...」
4. 頂層複述成「建立 aos 函數是分階段的：①資料夾＋`_entry.json`＋旁邊一支小 Python＝能被 aos-exec 跑的函數 ②補 `_metainfo.json` ③補 `_tooldef.json`＝能被腦當工具叫」，問之後再說還是 tools_def 該改成這樣。使用者：「Hmmm，應該說，這些是我理想中的一個，然後tools_def之後應該要能配合這個流程」
5. 「可以的話，或許，你知道的，json跟資料夾很像，所以或許，也可以在指定json檔案，或指定json object中(透過路徑#/)。添加_entry,_metainfo,_tooldef這些key」
6. （寫明天驗收時的口徑）「小模型裝不下說明，那就是去把lm studio那邊調整一下」；「haiku隨便用」。

## 決定

- 做；名字 `tools_def`（複數）；跟 `agent_def` 同在「定義」包 `lib/packs/def.json`，兩個範本預設開（原話 2）。
- 骨架只給 Python 一種；不加純 JSON 骨架（原話 3，頂層轉述的意思）。
- 骨架的檔案形狀照原話 3：`_entry.json`（`["python3", "tool.py"]` 的 inst 單子）＋旁邊一支 `tool.py`＋看得見的 `_metainfo.json`、`_tooldef.json`。
- 「一個工具的所在」當成一個**位置**：資料夾（三個檔）或 JSON 檔／`檔.json#/指標`（三個鍵）；lib 的產出、`check` 的對象都收位置（原話 5）。分階段的專門動作今晚不做成 op，列在 [01](01-設計與驗收.md#之後可加分階段流程) 的「之後可加」（原話 4）。

## 結論

- **輔助 lib** `proto8/lib/tool_spec.py`：寫一支工具＝在 `tool.py` 寫 `DESCRIPTION`、`PARAMS`（`ts.param`）、`META`、`def run(args)`、最後一行 `ts.main(...)`；不用手寫 JSON Schema 與 metainfo。
- **骨架** `proto8/templates/tool-python/`（加法），測試在 `templates/tests/tool-python/`（範本夾不帶 tests）。
- **工具** `proto8/lib/agent/tools_def/`：`new`、`check`。
- 驗收：假腦（工作區內外）全過；gemma-4-e4b 四輪，前三輪各卡一處、每處都改了 lib／骨架／說明，第四輪從骨架做出乘法工具、下一輪叫到得 42；eca haiku 做得出，但 eca 範本沒有檔案工具（見 01）。細節與紅的照貼在 [01](01-設計與驗收.md)。
