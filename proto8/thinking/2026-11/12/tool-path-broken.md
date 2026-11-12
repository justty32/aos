# 工具登記一條壞掉不再拖垮整份清單：aos-tools ls 略過那支、提醒一行、self_tools 標 broken（11-12，公司 WSL）

← [11-12 日索引](README.md)

## 經過

試驗場裡 eca opus 把自己造的工具資料夾從 `ws/tools/aos_cache` 搬到 `ws/new_tools/aos_cache`，登記檔還記舊路徑，結果它自己的敘述是「所有 aos 工具一起壞掉，連 `self_tools` 本身也不能用」，最後用 shell 改登記檔救回來；它建議「改成跳過那一支、只發警告，其他工具照常能用」。使用者把這段貼給頂層、沒附別的話；同一天他對同類問題的裁定是「_metainfo.json 壞掉時，index_view 對那個資料夾不該直接報錯。」——一處壞不該擋住其他好的。

重現（`/tmp/toolpath-1112/`，臨時樹、假腦不用）：兩支登記、搬走一支後——

| 指令 | 修前 | 修後 |
|---|---|---|
| `aos-tools ls`／`ls -l`／`ls --json` | 整份 `PathMissing`、退 1 | 略過那支、stderr 一行 warning、退 0；短版與 `-l` 標 broken，`--json` 不列 |
| `aos-tools get 好的`／`call 好的` | 正常 | 正常 |
| `aos-tools get 壞的`／`call 壞的` | `PathMissing` | 不變（原錯） |
| `aos-tools rm 壞的`、`add 新路徑` | 正常 | 正常 |
| aos-mcp 啟動、`tools/list`、`tools/call` | 啟動就 `ToolsBad` 退 1；跑起來之後每則都 -32603 | 清單少那支，其他列得出、叫得到 |
| self_tools（經 aos-agent tools，假 daemon 表） | 直接 aos-exec 叫：`ls` 報錯、`rm`／`add` 其實能用；經 MCP 叫：整支叫不到 | `ls` 標 broken、`get` 報原錯、`rm`／`add` 照常；經 MCP 也叫得到 |

**哪一層判死**：只有一處——`aos-tools ls` 逐支 `describe()`（讀路徑、讀 `_tooldef`），任一支丟錯就整個 `ls` 退 1。aos-mcp（每次 `tools/list`、`tools/call` 前、每次 call 後都跑 `ls --json`）、agent-fsm 的 brain／act（每格 `ls --json`）、self_tools `ls`（aos-agent tools ls → aos-tools ls）全都吃這一支，所以一起倒。`add`／`rm`／`call 別支` 本來就只讀登記格、不讀工具內容，沒受影響；eca 那隻救不回來，是因為它的 self_tools 是經 aos-mcp 叫的，而 aos-mcp 叫任何工具之前都先列清單。

## 修法

只改 `proto8/cmd/aos-tools/bin/aos-tools` 的 `ls`（新 `listed()`）：逐支 describe，一支自己的問題（`PathMissing`、`ToolDefMissing`、`ToolDefBad`、`DirectiveBad`／`RegistryBad` 只在 inspect 那支時）＝略過它，stderr 一行

```
aos-tools: warning: tool aos_cache skipped: PathMissing (its path does not exist); correct its path or take it off the list with rm aos_cache (get aos_cache shows the full error)
```

- 短版 `ls`：那一列 `aos_cache<TAB>broken: PathMissing (its path does not exist); …`，跟其他列照名字排。
- `ls -l`：KIND 欄＝`broken`，PATH／FROM／STORED／ENV 照登記格（PATH 是解出來、指不到的那個）。
- `ls --json`：不列（這份是給 aos-mcp、brain／act 組「叫得到的工具」用的，不改它們）。
- 結束碼 0。aos-mcp、brain、act、self_tools、aos-agent 都沒動程式；self_tools 的 `_tooldef` description 多半句（壞的會標 broken、rm 再 add）。

測試：`cmd/aos-tools/tests/test_broken_entry.py`（7 支：一條壞其他照常、`-l`／`--json`、別支 get／call、壞的 get／call 報原錯、rm 再 add、`ToolDefMissing` 也略過、登記檔不是 JSON 照舊整份錯）、`cmd/aos-mcp/tests/test_broken_entry.py`（list 少那支、call 別支成功）、`lib/agent/self_tools/tests/test_broken_entry.py`（真 aos-agent＋aos-tools、假 daemon 表：ls 標 broken、get 報原錯、rm 再 add 修好）；`test_paths.py` 兩支原本斷言「ls 退 1」改成「ls 退 0＋提醒，get 報原錯」。

## 代定

1. **腦怎麼看得到**：選「self_tools `ls` 把壞的那支標成 broken」——最簡單：aos-tools 短版 `ls` 自己印那一列，aos-agent tools、self_tools 原樣轉，不用改它們；MCP 的 `tools/list` 沒有放提醒的欄位，硬塞（假工具、改 description）會把不能叫的東西給模型看。aos-mcp 只把 warning 轉印到 stderr（用戶端 log）。
2. **`aos-tools ls` 有壞的時退 0**：提醒行不是錯誤行（N-43「有錯誤行不准退 0」不碰）；「列清單」不因一支壞而失敗。
3. **warning 不帶絕對路徑**：只有登記名、代號、白話原因（`BROKEN_WHY` 對照表，認不得的代號＝`it cannot be read`）、怎麼修；完整原因（含路徑、來自哪份檔哪一格）用 `get 名` 看。訊息講 `rm 名`，不講 self_tools（aos-tools 不知道上層是誰）。
4. **`--json` 不列壞的**：叫不到的不給；所以經 MCP 或 fsm 硬叫壞的那支，回的是 `no such tool`／act 的 `ToolUnknown`，不是 `PathMissing`——原錯只在 `aos-tools get／call 名`、self_tools `get` 看得到。
5. **`CommandMissing`（aos-json 起不來）照舊整份報錯**：那是環境壞、不是那一支的問題。
6. **範圍外、照舊整份報錯**：登記檔不是 JSON、形狀不對、`$override` 指不到；還有**某一支 path 的指示詞解不開**（例如 `{"$env": "X"}` 而 X 沒設）——那是整格 `tools` 一起交 aos-json 解時就失敗（`DirectiveBad`，`blame()` 已說出是哪支），要逐支解才拆得開，這次不做；它也會擋 `rm`，self_tools 救不回（要人改檔或 `aos-agent tools reset`）。登記格自己形狀不對（沒 `path`、`env` 不是物件）也一樣整份 `RegistryBad`、擋 `rm`。

**要重建什麼**：沒有（不改任何持久檔格式）。

## 跟條文的衝突（沒改條文，待裁）

- [CONVENTION P-41](../../../docs/CONVENTION/02-題目stack停錯腦/06-P-41.md) 末句「登記了但壞掉的工具＝brain／act 自己這層的錯 `ToolsBad`（停、人修好再跑）」——現在只有登記檔本身壞才 `ToolsBad`；一支壞＝清單少那支、照跑。建議改成：「登記檔本身壞（不是 JSON、形狀不對、`$override` 指不到、指示詞解不開）＝brain／act 自己這層的錯 `ToolsBad`（停、人修好再跑）；登記了但那一支壞掉（路徑不在、定義缺或壞）＝aos-tools ls 略過、提醒一行，清單少那一支、照跑（11-12 tool-path-broken）。」
- 10-28 [aos-tools 決定 4「不猜、不跳過」](../../2026-10/28/aos-tools/01-使用者原文.md) 與 [03-結論 #7](../../2026-10/28/aos-tools/03-結論.md)「`ls`／`get` 碰到登記了但壞掉的工具也整個報錯」：決定 4 原本講的是 `add XXX`（照舊報錯），#7 把它延伸到 `ls`；11-10 [aos-tools-cli 丙6](../10/aos-tools-cli/02-改法.md)「一個工具壞掉整份清單不能用…要不要鬆」當時留著沒裁。這次照頂層指示鬆了 `ls`，`add`／`get`／`call` 照舊不猜。要使用者確認這算對「不跳過」的修正。
- 11-05 [edge-agent](../05/edge-agent/README.md) #5「壞覆蓋層／工具不見＝整隻停：不改成略過壞的工具」：「工具不見」那半改了，「覆蓋層壞」照舊；[aos-agent docs/03](../../../cmd/aos-agent/docs/03-tools覆蓋層.md) 已照現況拆成兩條。
- C-52 KISS「寫什麼就做什麼」：不衝突——登記的值照字面用、沒有猜新路徑，只是不讓一支的錯變成全部的錯（錯誤只處理自己的那支）。

說明跟上：aos-tools `--help`（ls 那段、exit codes）、[aos-tools README](../../../cmd/aos-tools/README.md)、[aos-mcp README](../../../cmd/aos-mcp/README.md)、[cmd/docs/01](../../../cmd/docs/01-逐支說明.md)、[aos-agent docs/03](../../../cmd/aos-agent/docs/03-tools覆蓋層.md)、knowledge `aos/me/self_tools.json#/rules`（broken 怎麼看、搬工具「先 rm、搬完再 add」）、`aos/cli/tools.json#/ls_rm_get`。
